# 2026-07-21 v16 — clinosim seed=700 cross-seed robustness 検証

## 位置付け

v15 (seed=300) と **同 master `ef9d7706`** のまま seed だけ変えた run。
data 生成の pattern 変動で新規 issue が露出しないかを確認する目的。

precedent: session 62 で seed=500 → R53.1 / admit-source `hosp` / mb-org OID 系が発掘され、
それぞれ chain fix (PR #333/#335 等) の起点になった。

| run | master | seed | 目的 |
|---|---|---:|---|
| v15 | ef9d7706 | 300 | PR #344 (MimeType charset drop) 効果確認 |
| **v16** | ef9d7706 | **700** | **cross-seed で新規 pattern が出ないかの health check** |

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache 継承)
- `parallel-validate.py --chunk 30 --parallel 24 --include-file fhir_r4/Organization.ndjson`
  (docs 4.3 の推奨手順)
- Data: 156,597 rest (17 sticky 含む) + 221,432 obs = **378,029 res** (合成、`clinosim` v0.2.0, `country=JP`,
  `population=1000`, `seed=700`, 生成 patients 3,913)

## Result

| pass | 件数 | 所要 | rps | error | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 156,580 (−17 sticky) | 6.6 min | 395 | **1** | 1 | 0.0006% | **0** |
| obs (tx=n/a) | 221,432 | 12.7 min | 290 | **0** | 0 | 0.000% | **0** |
| **合計** | **378,012** | **19.3 min** | 326 | **1** | **1** | **0.000265%** | **0** |

## 新規 pattern (1 件): MedicationRequest.id が 64 文字超過

**唯一の error**:

```
Bundle.entry[N].resource/*MedicationRequest/req-abx-hai-ENC-POP-000905-266868769799-vap-0-ceftriaxone-narrowed*/.id
code: invalid
無効なリソースID：長すぎます (66 文字)
```

- FHIR R4 spec: `Resource.id` の [`type = id`](https://hl7.org/fhir/R4/datatypes.html#id) は
  `[A-Za-z0-9\-\.]{1,64}` — **max 64 文字**
- v16 では `-narrowed` suffix を持つ MR 1434 中 1 件のみ発火、id 長 = **66 文字**
- 中身: HAI (院内感染) VAP 治療の narrowing (empiric therapy → 起因菌 susceptibility 反映後の
  narrow-spectrum 切り替え) で、薬剤 `ceftriaxone-narrowed` の suffix が id builder に加わって越境

### 想定される generator-side fix

id builder の component 命名を短縮:

- `-ceftriaxone-narrowed` (21 chars) → `-cft-n` 等の abbreviation にすれば 51 → 46 chars
- あるいは prefix (`req-abx-hai-`, 12 chars) を短縮 (`req-hai-` = 8 chars) して 4 chars 余裕
- もしくは narrowing suffix を drug 名の後ではなく別 identifier system に切り出し

seed=700 では 1 件だが、薬剤名がさらに長い場合 (`piperacillin-tazobactam-narrowed` 等) は
seed 依存で複数件出る可能性あり。generator 側で fix する価値は高い。

## v15 (seed=300) vs v16 (seed=700) 比較

| 項目 | v15 sticky | v16 sticky | 差異解釈 |
|---|---:|---:|---|
| rest resource | 178,801 | 156,580 | seed による生成分布差 (v16 の方が -12%) |
| obs resource | 252,966 | 221,432 | 同上 (-12%) |
| rest error | 0 | 1 | **新規 pattern 1 件** (MR id length) |
| obs error | 0 | 0 | ↔ |
| timeouts | 0 | 0 | ↔ |
| **fail 率 (res)** | 0.000% | **0.000265%** | 極小維持、cross-seed robustness ほぼ達成 |

### 判定

- **regression 無し**: v15 で消えた 42 eReferral / MimeType 系は v16 でも 0 件、chain fix が
  seed 独立で有効なことを実測
- **新規 1 件**: cross-seed test の目的通り、seed=700 特有の rare pattern (HAI VAP narrowing の
  長 id) を発掘。session 62 の pattern と同種 (data 生成の稀な条件が id/code の validator 制約に
  抵触)
- fail 率 0.000265% は generator の実力値としては v15 (0%) と同水準、cross-seed で 1 件出るのは
  precedent 通り

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
