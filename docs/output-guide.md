# 検証結果の読み方

`scripts/parallel-validate.py` は 3 種のファイルを出力します:

| ファイル | 内容 | 1 行 = |
|---|---|---|
| `result.ndjson` | 検証結果 (OperationOutcome) の NDJSON ストリーム | 1 Bundle 分 (Bundle 内全リソースの issue が 1 OC に集約) |
| `result.meta.json` | run メタ (成功数、rps、port 別統計) | JSON 全体 |
| `result.failed.ndjson` | HTTP 失敗した Bundle 一覧 (timeout / 5xx / connection error) | 1 Bundle 分 (成功時は空) |

行数の目安: `result.ndjson` の行数 ≒ `meta.json` の `bundles` の値 (chunk_size=50 なら 50 リソースごとに 1 行)。各 OC の `issue[]` を展開して初めてリソース単位の判定ができます (§4 の recipe 参照)。

## 1. meta.json — まずはここを見る

サンプル (`chunk=50 parallel=32` で 343k res を 28 分検証した meta の例):

```json
{
  "input": "fhir_r4_sample",
  "resources_total": 343478,
  "resources_ok": 343478,
  "resources_failed": 0,
  "bundles": 6870,
  "chunk_size": 50,
  "parallel": 32,
  "timeout_sec": 60,
  "retries": 2,
  "circuit_threshold": 10,
  "servers": ["http://localhost:3001", "..."],
  "server_status_final": {
    "active_ports": 8,
    "total_ports": 8,
    "quarantined_ports": [],
    "port_ok_counts": {"3001": 859, "3002": 859, "...": "..."},
    "port_fail_counts": {}
  },
  "elapsed_sec": 1678.6,
  "throughput_res_per_sec": 204.62,
  "severity_summary": {
    "error": 1886172,
    "warning": 919953,
    "information": 1146544
  }
}
```

見どころ:

- **`resources_ok` == `resources_total`** かつ **`resources_failed` == 0** → HTTP レベルで全 Bundle が処理された (= 中身の validation 結果に関わらず、通信は成功)
- **`quarantined_ports` が空** → circuit breaker 発動なし、全 JVM 健康
- **`port_ok_counts` が均等** → 負荷が port 間で偏っていない (RR 分散が機能)
- **`severity_summary.error`** の絶対数だけで判断しない — 1 リソースあたり複数 issue が出るのが普通。**リソース単位の pass/fail は `result.ndjson` を集計する**

## 2. OperationOutcome NDJSON の構造

各行は `resourceType=OperationOutcome` の JSON で、`issue[]` に Bundle 内全リソースの検証結果が並びます:

```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "code-invalid",
      "details": {"text": "Unknown code 'LA27976-8' in the CodeSystem 'http://loinc.org' version '2.82'"},
      "expression": ["Bundle.entry[0].resource/*AllergyIntolerance/allergy-POP-000021-1*/.clinicalStatus.coding[0].display"],
      "diagnostics": "..."
    },
    ...
  ]
}
```

主なフィールド:

| フィールド | 値の例 | 意味 |
|---|---|---|
| `severity` | `fatal` / `error` / `warning` / `information` | 深刻度 |
| `code` | `code-invalid` / `invalid` / `not-supported` / `informational` | FHIR 標準の issue type |
| `details.text` | 人間可読メッセージ | grep 対象になる主要フィールド |
| `expression[]` | `Bundle.entry[N].resource/*ResourceType/id*/.<path>` | 違反箇所の FHIRPath (entry index + resource id 込みでリソースを一意特定できる) |
| `diagnostics` | 追加情報 | 出ない場合が多い |

Bundle は `chunk_size` 単位で構成され、`expression` は `Bundle.entry[0..chunk_size-1]` を取ります。**リソース単位に issue を分解するには `expression` の `Bundle.entry[N]` prefix と `resource/*ResourceType/id*/` パートで group by してください**。

## 3. 代表的な issue パターンと対処

### 3.1 `Unknown code 'X' in the CodeSystem 'http://loinc.org' version 'V'`

- **原因**: リソース側の code が使用中の LOINC version に存在しない (deprecated / typo / 未来 release)
- **対処**:
  - 正しい code に修正 (LOINC search で確認)
  - LOINC を最新版に更新 → `docs/terminology-setup.md` の LOINC import を再実行、新 cache を差し替えて `docker compose restart fhirserver`

### 3.2 `Wrong Display Name '医師' for http://snomed.info/sct#309343006 ... language(s) 'ja'. Default display is 'Physician'`

- **原因**: SNOMED CT International Edition には日本語 translation が含まれない (SNOMED CT Japan Edition は現在存在しない)
- **対処**:
  - display に英語を入れる (validator は spec 上 display 一致を要求)
  - もしくは `coding.userSelected=true` で表示名を意図的な選択と明示 (warning に格下げされる場合あり)
  - 業務上どうしても日本語が必要なら、jpfhir-terminology の JP CodeSystem (`http://jpfhir.jp/fhir/...`) 側に日本語 translation がある場合はそちらを併記 (`coding[]` に 2 要素)

### 3.3 `Constraint failed: dom-6: 'A resource should have narrative for robust management'`

- **原因**: FHIR Best Practice recommendation。`Resource.text` (Narrative) の欠如
- **対処**: severity が warning + `Best Practice Recommendation` 明記なら **意図的に無視可**。CI で除外したい場合は `details.text` に `dom-6` を含む issue を filter

### 3.4 `Constraint failed: <sliceName>: 'identifier.where(system=...) exists()'`

- **原因**: JP Core / JP-CLINS が要求する識別子 slice (患者 ID、保険者番号、eCS 診療科 code 等) が欠如
- **対処**: データ生成側で該当 slice を必須で埋める。slice 名は IG spec (JP Core `StructureDefinition-JP_Patient.html` 等) を参照

### 3.5 `Terminology_TX_NoValid_X_MSG` / `Terminology server is not available`

- **原因**: tx server (fhirserver) 側でコード解決失敗、または一時的な応答遅延で validator が `unknown` 扱い
- **対処**:
  - `curl http://localhost:8181/r4/metadata` で fhirserver が生きているか確認
  - cache warm 化不足の可能性 (初回起動直後は on-demand DL で stall) → 再実行で解消することが多い
  - fhirserver の logs で該当 CodeSystem が load 済か確認

### 3.6 `URL value 'urn:oid:1.2.392.200119.4.xxx' does not resolve`

- **原因**: 日本固有の OID CodeSystem が jpfhir-terminology に未登録、または該当版に含まれない
- **対処**:
  - jpfhir-terminology を最新版に更新
  - 該当 OID を含む CodeSystem リソースを自作で `-ig` に追加 load

### 3.7 `[information] この要素はどの既知のスライスとも一致しません` (silent-pass)

英語版: `This element does not match any known slice defined in the profile ...`

**severity = information** で **error / warning は一切出ない**。Open slicing
(`rules=open`) を持つ CodeableConcept / identifier / Quantity 系要素で、profile が
定義する各 slice の discriminator (Fixed Value / Pattern) に **一つも match
しなかった** 場合に発火する。

重要な性質:

- **slice に match しなかった時点で、その slice 内の required binding /
  Fixed display / cardinality の check は全て skip される**。data が profile の
  意図から外れていても error にならず、information issue が残るだけ
- HAPI validator の欠陥ではなく、Open slicing の spec 上の当然の挙動
- OperationOutcome には information issue として **確実に記録される** ため、
  集計すれば発生分布を計測可能

**この issue には 2 つの本質的に異なる原因がある** (混同注意):

- **原因 A: 意図的多重 coding × Open slicing の副作用** (data 設計として正しい)。
  data が「JP profile 用 coding + HL7 base 用 coding」の両方を並置している場合、
  片方の profile 視点からもう片方の coding が余剰 unmatched と評価される。
  data 変更で消すには片方の coding を捨てる必要があり、それは別の非準拠を招く。
  例: `Observation.category` の HL7 base + JP_SimpleObservationCategory 併記
- **原因 B: 真の silent-pass** (data missing required slice match)。
  data が profile の期待する slice の discriminator に一致していない。
  この場合、slice 内の required binding / Fixed display / cardinality は
  全て skip されるため、実質的な非準拠が silent で見逃される。
  例: `Observation.code.coding` の JP-CLINS 検体検査 slice に data の
  system/display が match していない

**対処方針**:

- **原因 B (真の silent-pass) を優先**: data 側で各 slice の discriminator
  (Fixed Value / Pattern) に正確に match させる。例えば `Observation.code.coding`
  に JP-CLINS の CoreLabo slice を期待するなら、slice が要求する `system` +
  `display` (英語 abbrev) を strict に emit
- **原因 A (Tier 2-noise) は data 設計として受容**: 生 count に含まれるが
  データ非準拠の指標ではない。集計時は path/profile で切り分けて除外
- validator 運用側: この issue を集計して A/B を分離し、真の silent-pass を
  可視化する ([§4.5](#45-tier-2-slice-unmatched-の集計-open-slicing-silent-pass)
  の recipe と切り分け方法参照)

**分布の実測例と切り分け結果** (母数条件込み):
[`validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md`](../validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md)。
clinosim v31 合成 EHR data (1,161 Bundle) を HAPI 6.9.12 + JP Core/JP-CLINS/
MHLW ICD-10/receipt-master load 済 fhirserver で validate した特定条件下の
測定値のため、条件セットで参照すること。

## 4. 集計 recipe

前提: `RES=result.ndjson`

### severity 別集計

```bash
jq -c '.issue[] | {severity}' "$RES" \
  | sort | uniq -c | sort -rn
```

### エラー内容 top 20 (details.text ベース)

```bash
jq -r '.issue[] | select(.severity=="error") | .details.text' "$RES" \
  | sed -E "s/'[^']+'/'X'/g; s/[0-9]+/N/g" \
  | sort | uniq -c | sort -rn | head -20
```

`sed` で code や数値を正規化して同種の issue を集約しています。

### リソース種別 × severity のクロス集計 (Python)

```bash
python3 <<'PY'
import json, sys
from collections import Counter
c = Counter()
with open("result.ndjson") as f:
    for line in f:
        oc = json.loads(line)
        for i in oc.get("issue", []):
            expr = (i.get("expression") or [""])[0]
            # Bundle.entry[N].resource/*ResourceType/id*/... から ResourceType 抽出
            rt = "?"
            if "resource/*" in expr:
                rt = expr.split("resource/*",1)[1].split("/",1)[0]
            c[(rt, i.get("severity","?"))] += 1
for (rt, sev), n in c.most_common(30):
    print(f"{n:>8}  {rt:<20} {sev}")
PY
```

### リソース単位の pass/fail 判定 (error が 1 件でもあれば fail)

`result.ndjson` は Bundle 単位なので、Python で `expression` の `Bundle.entry[N]` を key に group by してリソース単位に展開します:

```bash
python3 <<'PY'
import json, re
from collections import defaultdict
per_res = defaultdict(lambda: {"error":0, "warning":0, "information":0})
pat = re.compile(r'Bundle\.entry\[(\d+)\]\.resource/\*([^/]+)/([^*]+)\*/')
with open("result.ndjson") as f:
    for bundle_idx, line in enumerate(f):
        oc = json.loads(line)
        for i in oc.get("issue", []):
            for expr in (i.get("expression") or []):
                m = pat.search(expr)
                if m:
                    key = (bundle_idx, m.group(2), m.group(3))  # (bundle, ResourceType, id)
                    per_res[key][i.get("severity","information")] += 1
                    break
total = len(per_res)
failed = sum(1 for v in per_res.values() if v["error"] > 0)
print(f"resources_seen={total}, failed={failed}, pass={total-failed}")
PY
```

注: リソースに一切 issue が付かなかった場合はカウント対象外になります (完全 pass の判定には入力側の総リソース数 = `meta.json` の `resources_total` と比較)。

### 4.5 Tier 2 (slice unmatched) の集計 — Open slicing silent-pass

[§3.7](#37-information-この要素はどの既知のスライスとも一致しません-silent-pass)
で説明した silent-pass (Open slicing で slice に match せず、slice 内の制約
check が skip される) は severity = information として OperationOutcome に記録
されるため、集計可能。**error / warning に現れない準拠性の実態**を可視化する。

対象要素は `code.coding` に限定せず、`identifier` / `category` /
`bodySite.coding` / `medication.ofType(...)` / `dosage.rate.ofType(...)` 等、
JP-CLINS / JP Core の任意の Open slicing 要素で発生する。以下は汎用形の recipe:

```bash
python3 <<'PY'
import json, re, collections

RES = "result.ndjson"
# 日本語版 + 英語版の両方を対象
MSG_PATTERNS = [
    "この要素はどの既知のスライスとも一致しません",
    "This element does not match any known slice",
]
EXPR_RE    = re.compile(r'resource/\*([A-Za-z]+)/([^*]+)\*/(.*)$')
PROFILE_RE = re.compile(r'defined in the profile (\S+)')
# element path 正規化: [N] (array index) と :sliceName を除去
NORM_RE    = re.compile(r'\[\d+\]|:[^.\[]+')

by_res_path = collections.Counter()
by_res      = collections.Counter()
by_profile  = collections.Counter()
affected    = collections.defaultdict(set)  # (rt, path) -> {resource_id}
n_bundle = n_issue_total = n_unmatched = 0

with open(RES) as f:
    for line in f:
        n_bundle += 1
        oo = json.loads(line)
        for i in oo.get("issue", []):
            n_issue_total += 1
            det = (i.get("details") or {}).get("text", "") or ""
            if not any(p in det for p in MSG_PATTERNS):
                continue
            n_unmatched += 1
            m = PROFILE_RE.search(det)
            by_profile[m.group(1) if m else "(no profile)"] += 1
            for expr in i.get("expression") or []:
                em = EXPR_RE.search(expr)
                if not em: continue
                rt, rid, inner = em.groups()
                inner_norm = NORM_RE.sub("", inner.lstrip("."))
                by_res_path[(rt, inner_norm)] += 1
                by_res[rt] += 1
                affected[(rt, inner_norm)].add(rid)

print(f"bundles={n_bundle} issues={n_issue_total:,} "
      f"unmatched={n_unmatched:,} share={n_unmatched/max(n_issue_total,1)*100:.2f}%")
print("\n-- by resourceType --")
for rt, c in by_res.most_common():
    uniq = len({rid for (r, _), ids in affected.items() if r == rt for rid in ids})
    print(f"  {rt:30s} {c:>8,}  unique_res={uniq:,}")
print("\n-- by profile --")
for p, c in by_profile.most_common():
    print(f"  {c:>8,}  {p}")
print("\n-- top (resourceType, element path) --")
for (rt, p), c in by_res_path.most_common(30):
    print(f"  {c:>8,}  {rt:26s}  .{p:44s}  unique_res={len(affected[(rt, p)])}")
PY
```

- **正規化 (`[N]` と `:sliceName` を除去)** により `code.coding[0]` と
  `code.coding[1]:CoreLabo` を同じ path `code.coding` として集計する。array の
  何番目に付いたかや、profile が名前付き slice を持っているかは Open slicing
  silent-pass の集計軸としては本質でない
- **英語版 message** にも対応 (validator の locale が en の場合)
- **profile 別集計**は HAPI が meta.profile + base R4 + JP IG + HL7 vital-signs
  自動 profile を全て評価するため、**同じ要素 path でも複数 profile 由来の
  unmatched が計上されることがある**

#### 生 count は Tier 2-noise と Tier 2-real の混合 (重要)

上記 recipe の生 count には 2 種類が混在する:

- **Tier 2-noise (意図的多重 coding の副作用)**: data が「JP profile 用 +
  HL7 base 用」の両 coding を並置している要素で、各 profile 視点から相手側の
  coding が余剰 unmatched と評価される。data 設計として正しい
- **Tier 2-real (真の silent-pass)**: data が profile の期待する slice に
  match していない、実質的な非準拠

**切り分け方法**: (resourceType, element path) 別 count を profile と併記し、
「同一 element path が複数 profile から独立して報告されているか」を確認する。
特に `Observation.category` は複数 profile から一斉に unmatched になりやすい
Tier 2-noise の典型。data 側の non-compliance を追うなら Tier 2-real 分
(通常 `code.coding` / `identifier` / `bodySite.coding` / `medication.coding`
等 個別 slice) に絞る。

具体的な切り分け例と背景解説は tier2-distribution-v31.md 参照。

- **移行効果測定**: **Tier 2-real** の `unmatched / (対象要素の total)` を追えば、
  「エラーが減った」とは別軸の **slice 適合率** を数値化できる。分母 (対象要素の
  total 出現数) は入力 NDJSON 側から別途集計。Tier 2-noise は data の多重 coding
  設計に依存する constant で、移行効果とは無関係のため除外

**実測分布 (母数条件込み)**:
[`validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md`](../validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md)。
clinosim v31 合成 EHR (1,161 Bundle) × HAPI 6.9.12 + JP Core / JP-CLINS /
MHLW ICD-10 / receipt-master load 済 fhirserver 構成下:

- 生 unmatched 28,334 件 = 全 issue の 22.19%
- 内訳: **Tier 2-noise 19,583 件 (69%)** = data 設計上の副作用、
  **Tier 2-real 8,751 件 (31%) = 全 issue の 6.86%** = 真の silent-pass
- 数値は特定 data + 特定 validator 構成でのみ有効、外部引用時は条件セットで示す

## 5. failed.ndjson の意味

`result.failed.ndjson` には HTTP レベルで失敗した Bundle が入ります (validator が起動していない、timeout、connection reset 等)。**空 = OK**。

1 行の構造:

```json
{
  "bundle_index": 3421,
  "port": 3004,
  "error": "TimeoutError: The read operation timed out",
  "resource_ids": ["Patient/pat-001", "Observation/obs-002", ...]
}
```

対処:

- **timeout 中心** → `--parallel` を下げる (32 → 24)、または `--timeout` を延ばす (60 → 120)
- **特定 port 集中** → その JVM の logs (`.hapi-cache/logs/<port>.log`) で OOM / freeze を確認、`scripts/hapi-cluster.sh stop && start` で再起動
- **`quarantined_ports` に頻出** → circuit breaker が発動、`--circuit-threshold` 調整 or JVM 数を減らす

再実行時は `resource_ids` の Patient/Observation を元 NDJSON から抽出して部分再検証すると効率的です。

## 6. CI での使い方

`severity=error` が閾値を超えたら exit code 1 で fail する例:

```bash
#!/usr/bin/env bash
set -euo pipefail
THRESHOLD="${THRESHOLD:-0}"

./scripts/hapi-cluster.sh start
trap './scripts/hapi-cluster.sh stop' EXIT

./scripts/parallel-validate.py "$INPUT_DIR" --output ci-result.json \
  --parallel 16 --chunk 50

ERR=$(jq '.severity_summary.error // 0' ci-result.meta.json)
FAIL=$(jq '.resources_failed // 0' ci-result.meta.json)

echo "errors=$ERR failed_http=$FAIL threshold=$THRESHOLD"
if [ "$ERR" -gt "$THRESHOLD" ] || [ "$FAIL" -gt 0 ]; then
  echo "FAIL: too many issues"
  exit 1
fi
```

より厳密には「リソース単位の fail 率が X% 以下」で判定するのが実務的です (Best Practice warning が noise になるため)。§4 の Python snippet を CI に組込んでください。
