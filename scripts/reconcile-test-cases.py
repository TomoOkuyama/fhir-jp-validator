#!/usr/bin/env python3
"""test-cases/**/*.ndjson を validation で回し、meta.tag の期待 issue が
検出されたかを突合する。

使い方:
    ./scripts/reconcile-test-cases.py

前提: fhirserver 起動中 + HAPI cluster 起動中 (validate-code 使用)
    docker compose up -d fhirserver
    HAPI_EXTRA_ARGS="-best-practice ignore" ./scripts/hapi-cluster.sh start

出力:
    - PASS: 期待 issue 全て検出
    - FAIL: 期待 issue の一部/全部が未検出 (regression)
    - EXTRA: 期待外の error あり (noise or 新たな検出、要人間判定)
    - 集計: category ごとの pass 率、未定義 slug の警告

exit code: 0 = 全 case PASS、1 = FAIL/EXTRA/未定義あり
"""

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TC_DIR = REPO_ROOT / "test-cases"
EXPECTED_MODULE_PATH = TC_DIR / "expected-issues.py"


def load_expected_issues():
    spec = importlib.util.spec_from_file_location(
        "expected_issues", EXPECTED_MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_cases(module):
    """test-cases/**/*.ndjson を走査し、resource id → 期待 slug 集合を返す。

    resource ごとに meta.tag の system=EXPECTED_ISSUE_SYSTEM を集める。
    未定義 slug は warning としてレポート。
    """
    cases = {}  # rid -> {file, category, expected_slugs, resource_type}
    unknown = []  # (rid, slug, file)
    for ndjson in sorted(TC_DIR.rglob("*.ndjson")):
        category = ndjson.relative_to(TC_DIR).parts[0]
        for line in ndjson.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            rid = r.get("id")
            if not rid:
                print(f"WARN: {ndjson} に id 無しリソースあり、スキップ", file=sys.stderr)
                continue
            slugs = []
            for tag in r.get("meta", {}).get("tag", []):
                if tag.get("system") == module.EXPECTED_ISSUE_SYSTEM:
                    slug = tag.get("code")
                    if slug and module.slug_exists(slug):
                        slugs.append(slug)
                    else:
                        unknown.append((rid, slug, str(ndjson)))
            cases[rid] = {
                "file": ndjson,
                "category": category,
                "expected_slugs": slugs,
                "resource_type": r.get("resourceType"),
            }
    return cases, unknown


def stage_and_validate(cases, tmpdir, chunk, parallel, timeout):
    """全 case を tmpdir/staged.ndjson にまとめて parallel-validate 実行。"""
    staged = Path(tmpdir) / "input"
    staged.mkdir(parents=True, exist_ok=True)
    # resource type ごとに分けて配置 (parallel-validate の慣行に沿う)
    by_type = {}
    for rid, meta in cases.items():
        text = None
        for line in meta["file"].read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("id") == rid:
                text = line
                break
        if text is None:
            continue
        rt = meta["resource_type"]
        by_type.setdefault(rt, []).append(text)
    for rt, lines in by_type.items():
        (staged / f"{rt}.ndjson").write_text("\n".join(lines) + "\n")

    output = Path(tmpdir) / "result.ndjson"
    stdout_log = Path(tmpdir) / "run.log"
    cmd = [
        str(REPO_ROOT / "scripts" / "parallel-validate.py"),
        str(staged),
        "--output", str(output),
        "--chunk", str(chunk),
        "--parallel", str(parallel),
        "--timeout", str(timeout),
    ]
    with stdout_log.open("w") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        print(f"parallel-validate 失敗 (exit {result.returncode})", file=sys.stderr)
        print(stdout_log.read_text()[-2000:], file=sys.stderr)
        sys.exit(1)
    return output


def parse_errors(output_path):
    """OperationOutcome NDJSON から resource id → [issue] を抽出。

    2 形式の expression をサポート:
      A. Bundle.entry[N].resource/*Type/id*/...  (structural / 構造レベル issue)
      B. Bundle.entry[N].resource               (parse-level issue、type/id 情報なし)

    形式 B は HAPI が resource parse 中に発火する issue (認識できない
    プロパティ、att-1/rat-1/rng-2/per-1 等の invariant fail、ele-1、多重
    value[x] 検出等) に典型。type/id が expression に含まれないため、以前の
    実装では silent に落ちていた (2026-07-24 発覚、Bucket 2 として HAPI gap と
    誤判定した根本原因)。

    fix: 各 OC 内で第 1 pass で形式 A の (entry_index → resource_id) map を
    作り、第 2 pass で形式 B の issue に entry_index から resource_id を
    lookup して attribute する。同 OC 内に形式 A の issue が全く無く形式 B
    のみの場合は、その OC の全 issue が同一 resource に対するものと仮定して
    (chunk=1 前提)、entry_id 情報を fallback として使う。
    """
    expr_full = re.compile(r"Bundle\.entry\[(\d+)\]\.resource/\*\w+/([^*]+)\*/")
    expr_short = re.compile(r"Bundle\.entry\[(\d+)\]\.resource(?!/)")
    per_resource = {}
    unattributed_count = 0
    for line in output_path.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("resourceType") != "OperationOutcome":
            continue
        issues = obj.get("issue", [])
        # Pass 1: entry_index → resource_id map (形式 A から作る)
        entry_to_id = {}
        for iss in issues:
            for e in iss.get("expression", []) or []:
                m = expr_full.search(e)
                if m:
                    entry_to_id[int(m.group(1))] = m.group(2)
        # OC 全体で唯一の resource_id を推定 (chunk=1 fallback 用)
        unique_id = None
        if len(set(entry_to_id.values())) == 1:
            unique_id = next(iter(entry_to_id.values()))
        # Pass 2: 全 issue を attribute
        for iss in issues:
            sev = iss.get("severity", "?")
            details = iss.get("details", {}).get("text", "")
            rid = None
            for e in iss.get("expression", []) or []:
                m_full = expr_full.search(e)
                if m_full:
                    rid = m_full.group(2)
                    break
                m_short = expr_short.search(e)
                if m_short:
                    idx = int(m_short.group(1))
                    if idx in entry_to_id:
                        rid = entry_to_id[idx]
                    elif unique_id:  # fallback: OC が 1 resource だけ扱っていた場合
                        rid = unique_id
                    break
            if rid is None:
                # 最後の fallback: OC 内で unique な resource_id があればそこへ
                if unique_id:
                    rid = unique_id
                else:
                    unattributed_count += 1
                    continue
            per_resource.setdefault(rid, []).append({"severity": sev, "text": details})
    if unattributed_count:
        print(f"WARN: {unattributed_count} 件の issue を resource に attribute "
              f"できませんでした (OC 内に resource 情報が無い parse-level issue)",
              file=sys.stderr)
    return per_resource


def match_case(expected_slugs, actual_issues, module):
    """1 case について、各期待 slug が actual issues にマッチするか判定。

    通常 slug: pattern match すれば PASS。
    record-only-* 系 slug: pattern match しないほうが PASS (逆判定)。
      HAPI/validator が検出しないことを assert する用途で、将来 fire
      するようになれば FAIL 化して alarm する仕組み。

    返り値: {slug: matched_bool} の dict
    """
    INVERTED = ("record-only-not-enforced", "record-only-spec-not-encoded")
    matched = {}
    for slug in expected_slugs:
        entry = module.EXPECTED_ISSUES.get(slug, {})
        expected_type = entry.get("expected_type", "error-warning")
        pattern = module.pattern_for(slug)
        if pattern is None:
            matched[slug] = False
            continue
        found = any(pattern.search(iss["text"]) for iss in actual_issues)
        if expected_type in INVERTED:
            # 逆判定: 検出されない (found=False) ことが PASS
            matched[slug] = not found
        else:
            matched[slug] = found
    return matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=10)
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="全 case の詳細 issue も表示")
    ap.add_argument("--keep-tmp", action="store_true",
                    help="tmp ディレクトリを削除しない (デバッグ用)")
    args = ap.parse_args()

    module = load_expected_issues()
    cases, unknown = discover_cases(module)

    if not cases:
        print("test-cases が空", file=sys.stderr)
        sys.exit(1)

    if unknown:
        print(f"WARN: expected-issues.py に未定義の slug が {len(unknown)} 件:",
              file=sys.stderr)
        for rid, slug, f in unknown:
            print(f"  {rid} in {f}: '{slug}'", file=sys.stderr)

    print(f"discovered: {len(cases)} case, "
          f"{sum(len(c['expected_slugs']) for c in cases.values())} expected slugs")

    tmpdir = tempfile.mkdtemp(prefix="tc-reconcile-")
    print(f"staging in {tmpdir}")
    try:
        output_path = stage_and_validate(
            cases, tmpdir, args.chunk, args.parallel, args.timeout)
        per_resource_issues = parse_errors(output_path)

        pass_ct = fail_ct = extra_ct = missing_ct = 0
        details = []
        for rid, meta in sorted(cases.items()):
            actual = per_resource_issues.get(rid, [])
            expected_slugs = meta["expected_slugs"]
            matched = match_case(expected_slugs, actual, module)
            all_matched = expected_slugs and all(matched.values())
            missing_slugs = [s for s, m in matched.items() if not m]

            # actual errors that no expected slug covers → 疑わしい noise
            covered_texts = set()
            for slug, m in matched.items():
                if m:
                    p = module.pattern_for(slug)
                    for iss in actual:
                        if p and p.search(iss["text"]):
                            covered_texts.add(iss["text"])
            unexplained = [
                iss for iss in actual
                if iss["severity"] == "error" and iss["text"] not in covered_texts
            ]

            status = "PASS"
            if missing_slugs:
                status = "FAIL"; fail_ct += 1
                missing_ct += len(missing_slugs)
            elif not expected_slugs:
                status = "SKIP"
            else:
                pass_ct += 1
            if unexplained:
                extra_ct += 1

            details.append((rid, meta, status, matched, unexplained, actual))

        # per-case output
        for rid, meta, status, matched, unexplained, actual in details:
            marker = {"PASS": "✓", "FAIL": "✗", "SKIP": "-"}[status]
            print(f"\n{marker} [{status}] {meta['category']}/{meta['resource_type']}/{rid}")
            for slug, m in matched.items():
                m_marker = "✓" if m else "✗ MISSING"
                print(f"      expected: {slug}  {m_marker}")
            if unexplained:
                print(f"      unexplained errors ({len(unexplained)}):")
                for iss in unexplained[:5]:
                    print(f"        - {iss['text'][:120]}")
                if len(unexplained) > 5:
                    print(f"        ... +{len(unexplained)-5} more")
            if args.verbose:
                print(f"      all actual issues ({len(actual)}):")
                for iss in actual[:10]:
                    print(f"        [{iss['severity'][:4]}] {iss['text'][:120]}")

        # summary
        total = len(cases)
        print(f"\n=== summary ===")
        print(f"total: {total}, PASS: {pass_ct}, FAIL: {fail_ct}, "
              f"missing slugs: {missing_ct}, cases with unexplained errors: {extra_ct}")
        if unknown:
            print(f"未定義 slug: {len(unknown)} 件 (WARN)")

        exit_code = 0 if (fail_ct == 0 and not unknown) else 1
        sys.exit(exit_code)
    finally:
        if not args.keep_tmp:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
