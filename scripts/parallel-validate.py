#!/usr/bin/env python3
"""
HAPI Validator クラスタに NDJSON を並列投入して JP Core 検証する client (streaming + health-check 版)。

設計:
  - Bundle 生成は generator で lazy (全部メモリに載せない)
  - ThreadPoolExecutor.submit() + wait() で back-pressure (in-flight 数を制限)
  - OperationOutcome は 1 行 1 件で NDJSON に逐次書き出し (メモリ節約)
  - 各リクエストに retry + 指数バックオフ、timeout 短め (60s)
  - **JVM ヘルスチェック + サーキットブレーカ**: 連続失敗する port を検出して除外
    (ローテーションを健康な JVM に絞ることでスループット回復)
  - 進捗を stderr に定期出力、失敗 bundle は failed.ndjson に別途記録

前提: scripts/hapi-cluster.sh 又は EC2 user-data で HAPI server クラスタが起動していること

Usage:
  scripts/parallel-validate.py <fhir_r4_dir> --output result.json
"""

from __future__ import annotations
import argparse, concurrent.futures as cf, json, os, sys, time, urllib.error, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from threading import Lock

DEFAULT_PORTS = list(range(3001, 3009))
DEFAULT_CHUNK = 50
DEFAULT_PARALLEL = 64
DEFAULT_TIMEOUT = 60                # Bundle 検証は数秒で終わるべき。長すぎる timeout は詰まりの原因
DEFAULT_RETRIES = 2
DEFAULT_INFLIGHT_MULT = 2
DEFAULT_CIRCUIT_THRESHOLD = 10      # 連続失敗 N 回で port を quarantine
DEFAULT_HEALTHCHECK_INTERVAL = 60   # quarantine 済み port の復活チェック間隔 (秒)


def make_bundle(rs: list[dict]) -> bytes:
    entries = [{"fullUrl": f"http://x/{r.get('resourceType','?')}/{r.get('id','')}",
                "resource": r} for r in rs]
    return json.dumps({"resourceType": "Bundle", "type": "collection",
                       "entry": entries}, ensure_ascii=False).encode("utf-8")


def post_one_with_retry(url: str, payload: bytes, retries: int, timeout: int):
    """指数バックオフで retry。最終的な OperationOutcome list を返す。"""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/fhir+json",
                         "Connection": "close"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            d = json.loads(body)
            outcomes: list[dict] = []
            if d.get("resourceType") == "Bundle":
                for e in d.get("entry", []):
                    r = e.get("resource", {})
                    if r.get("resourceType") == "OperationOutcome":
                        outcomes.append(r)
            elif d.get("resourceType") == "OperationOutcome":
                outcomes.append(d)
            return outcomes
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError,
                TimeoutError, json.JSONDecodeError) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(0.5 * (2 ** attempt))    # 0.5s, 1s
            continue
    raise RuntimeError(f"{type(last_exc).__name__}: {last_exc}")


def iter_resources(path: Path, limit: int | None):
    files = sorted(path.glob("*.ndjson")) if path.is_dir() else [path]
    files = [f for f in files if not f.name.startswith("._")]
    n = 0
    for fp in files:
        with fp.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                    n += 1
                    if limit and n >= limit:
                        return
                except json.JSONDecodeError:
                    continue


def bundle_generator(path: Path, chunk_size: int, limit: int | None):
    buf: list[dict] = []
    ids: list[str] = []
    idx = 0
    for r in iter_resources(path, limit):
        buf.append(r)
        ids.append(f"{r.get('resourceType','?')}/{r.get('id','')}")
        if len(buf) >= chunk_size:
            yield idx, make_bundle(buf), ids
            idx += 1
            buf = []
            ids = []
    if buf:
        yield idx, make_bundle(buf), ids


class ServerPool:
    """port ローテーション + ヘルスチェック / サーキットブレーカ."""

    def __init__(self, host: str, ports: list[int], threshold: int, recovery_check_interval: int):
        self.host = host
        self.threshold = threshold
        self.recovery_check_interval = recovery_check_interval
        self.lock = Lock()
        self.consecutive_fails: dict[int, int] = {p: 0 for p in ports}
        self.total_fails: Counter = Counter()
        self.total_ok: Counter = Counter()
        self.quarantined_at: dict[int, float] = {}
        self.rr_index = 0                          # round-robin

    def url_of(self, port: int) -> str:
        return f"http://{self.host}:{port}/validateResource"

    def pick_url(self) -> tuple[str, int]:
        """健康な port を round-robin で選ぶ."""
        with self.lock:
            active = [p for p in self.consecutive_fails.keys() if p not in self.quarantined_at]
            if not active:
                # 全 quarantined 状態: 復活チェック時刻に近い port を返す (fallback)
                p = min(self.quarantined_at, key=self.quarantined_at.get)
                return self.url_of(p), p
            port = active[self.rr_index % len(active)]
            self.rr_index += 1
            return self.url_of(port), port

    def report_success(self, port: int):
        with self.lock:
            self.consecutive_fails[port] = 0
            self.total_ok[port] += 1
            if port in self.quarantined_at:
                del self.quarantined_at[port]

    def report_failure(self, port: int):
        with self.lock:
            self.consecutive_fails[port] += 1
            self.total_fails[port] += 1
            if self.consecutive_fails[port] >= self.threshold and port not in self.quarantined_at:
                self.quarantined_at[port] = time.time()

    def try_recover(self):
        """quarantine された port を一定時間経過後、復活候補に戻す (次の pick で試される)."""
        now = time.time()
        with self.lock:
            for p, t in list(self.quarantined_at.items()):
                if now - t >= self.recovery_check_interval:
                    del self.quarantined_at[p]
                    self.consecutive_fails[p] = 0   # リセット、再チャンス

    def status_snapshot(self) -> dict:
        with self.lock:
            active = sum(1 for p in self.consecutive_fails if p not in self.quarantined_at)
            return {
                "active_ports": active,
                "total_ports": len(self.consecutive_fails),
                "quarantined": list(self.quarantined_at.keys()),
                "top_failed": self.total_fails.most_common(5),
            }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="NDJSON dir or single file")
    ap.add_argument("--output", "-o", type=Path, required=True)
    ap.add_argument("--ports", type=lambda s: [int(x) for x in s.split(",")], default=DEFAULT_PORTS)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--chunk", type=int, default=DEFAULT_CHUNK)
    ap.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--circuit-threshold", type=int, default=DEFAULT_CIRCUIT_THRESHOLD,
                    help=f"連続失敗数がこれを超えたら port を quarantine (default: {DEFAULT_CIRCUIT_THRESHOLD})")
    ap.add_argument("--recovery-interval", type=int, default=DEFAULT_HEALTHCHECK_INTERVAL,
                    help=f"quarantine 後の復活チェック間隔 秒 (default: {DEFAULT_HEALTHCHECK_INTERVAL})")
    args = ap.parse_args()

    output_base = args.output.parent / args.output.stem
    output_base.parent.mkdir(parents=True, exist_ok=True)
    outcome_path = output_base.with_suffix(".ndjson")
    meta_path    = output_base.with_suffix(".meta.json")
    failed_path  = output_base.with_suffix(".failed.ndjson")

    pool = ServerPool(args.host, args.ports, args.circuit_threshold, args.recovery_interval)

    print(f"input:      {args.input}", file=sys.stderr)
    print(f"servers:    {len(args.ports)} ({args.host}:{','.join(map(str, args.ports))})", file=sys.stderr)
    print(f"chunk:      {args.chunk} resources/Bundle", file=sys.stderr)
    print(f"parallel:   {args.parallel} in-flight workers", file=sys.stderr)
    print(f"timeout:    {args.timeout}s, retries: {args.retries}", file=sys.stderr)
    print(f"circuit:    quarantine after {args.circuit_threshold} consecutive fails, recover after {args.recovery_interval}s", file=sys.stderr)
    print(f"outputs:    {outcome_path}, {meta_path}, {failed_path}", file=sys.stderr)

    t0 = time.time()
    total_resources = 0
    total_bundles = 0
    outcome_count = 0
    sev_c: Counter = Counter()
    failed_count = 0
    inflight_max = args.parallel * DEFAULT_INFLIGHT_MULT

    def wrapped_post(job):
        idx, payload, ids = job
        url, port = pool.pick_url()
        try:
            outcomes = post_one_with_retry(url, payload, args.retries, args.timeout)
            pool.report_success(port)
            return ("ok", idx, port, ids, outcomes)
        except Exception as e:
            pool.report_failure(port)
            return ("fail", idx, port, ids, str(e))

    gen = bundle_generator(args.input, args.chunk, args.limit)
    last_log_t = t0
    last_log_res = 0
    last_recovery_t = t0

    with outcome_path.open("w") as f_out, \
         failed_path.open("w") as f_fail, \
         cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:

        pending: set = set()

        for _ in range(inflight_max):
            try:
                job = next(gen)
                total_bundles += 1
                total_resources += len(job[2])
                pending.add(ex.submit(wrapped_post, job))
            except StopIteration:
                break

        while pending:
            done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED, timeout=30)
            if not done:
                snap = pool.status_snapshot()
                print(f"  [idle 30s] in-flight={len(pending)} processed={outcome_count} "
                      f"active_ports={snap['active_ports']}/{snap['total_ports']} "
                      f"quarantined={snap['quarantined']}", file=sys.stderr)
                pool.try_recover()
                continue

            for fut in done:
                status, idx, port, ids, payload = fut.result()
                if status == "ok":
                    for oc in payload:
                        f_out.write(json.dumps(oc, ensure_ascii=False) + "\n")
                        for iss in oc.get("issue", []):
                            sev_c[iss.get("severity", "?")] += 1
                    outcome_count += len(ids)
                else:
                    f_fail.write(json.dumps({"bundle_index": idx, "port": port,
                                             "error": payload, "resource_ids": ids},
                                            ensure_ascii=False) + "\n")
                    failed_count += len(ids)

                try:
                    job = next(gen)
                    total_bundles += 1
                    total_resources += len(job[2])
                    pending.add(ex.submit(wrapped_post, job))
                except StopIteration:
                    pass

            # flush stream files (S3 snapshot upload に効くように)
            f_out.flush()
            f_fail.flush()

            # 5 秒毎に進捗ログ
            now = time.time()
            if now - last_log_t >= 5:
                dt = now - t0
                rps = outcome_count / max(dt, 0.001)
                delta = outcome_count - last_log_res
                delta_rps = delta / max(now - last_log_t, 0.001)
                snap = pool.status_snapshot()
                q_info = f" quarantined={snap['quarantined']}" if snap['quarantined'] else ""
                print(f"  [{time.strftime('%H:%M:%S')}] processed={outcome_count} res, "
                      f"bundles_sent={total_bundles}, "
                      f"avg_rps={rps:.1f}, recent_rps={delta_rps:.1f}, "
                      f"in-flight={len(pending)}, failed={failed_count}, "
                      f"active_ports={snap['active_ports']}/{snap['total_ports']}{q_info}",
                      file=sys.stderr, flush=True)
                last_log_t = now
                last_log_res = outcome_count

            # 30 秒毎に quarantine 復活試行
            if now - last_recovery_t >= 30:
                pool.try_recover()
                last_recovery_t = now

    dt = time.time() - t0
    rps = outcome_count / max(dt, 0.001)

    # meta 書き出し (port 別統計も含める)
    snap = pool.status_snapshot()
    meta = {
        "input": str(args.input),
        "resources_total": total_resources,
        "resources_ok": outcome_count,
        "resources_failed": failed_count,
        "bundles": total_bundles,
        "chunk_size": args.chunk,
        "parallel": args.parallel,
        "timeout_sec": args.timeout,
        "retries": args.retries,
        "circuit_threshold": args.circuit_threshold,
        "servers": [f"http://{args.host}:{p}" for p in args.ports],
        "server_status_final": {
            "active_ports": snap["active_ports"],
            "total_ports": snap["total_ports"],
            "quarantined_ports": snap["quarantined"],
            "port_ok_counts":   dict(pool.total_ok),
            "port_fail_counts": dict(pool.total_fails),
        },
        "elapsed_sec": round(dt, 2),
        "throughput_res_per_sec": round(rps, 2),
        "severity_summary": dict(sev_c),
        "outcome_ndjson": str(outcome_path),
        "failed_ndjson": str(failed_path) if failed_count > 0 else None,
    }
    with meta_path.open("w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完了 ===", file=sys.stderr)
    print(f"elapsed:      {dt:.1f}s ({dt/60:.1f} min)", file=sys.stderr)
    print(f"throughput:   {rps:.1f} res/sec", file=sys.stderr)
    print(f"resources:    {total_resources} total, {outcome_count} ok, {failed_count} failed", file=sys.stderr)
    print(f"severity:     {dict(sev_c)}", file=sys.stderr)
    print(f"ports:        active {snap['active_ports']}/{snap['total_ports']}, quarantined {snap['quarantined']}", file=sys.stderr)
    print(f"outcomes ->   {outcome_path}", file=sys.stderr)
    print(f"meta     ->   {meta_path}", file=sys.stderr)
    if failed_count > 0:
        print(f"failed   ->   {failed_path}  ({failed_count} resources)", file=sys.stderr)


if __name__ == "__main__":
    main()
