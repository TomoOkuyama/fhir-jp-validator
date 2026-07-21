# 2026-07-21 v17 — clinosim enumerate mode (debug L3 coverage)

## 位置付け

session 63 PR #346 で新規追加された **enumerate subcommand** の初回検証。population-driven
生成では発火しにくい rare 組合せを 100% coverage で網羅する debug mode で、
`disease × severity × archetype`、`complication axis`、`encounter × severity` の 3 軸を
cartesian expansion する。

| axis | patient 数 | 意図 |
|---|---:|---|
| disease × severity × archetype | 486 (ENUM-JP-0001..0486) | 32 疾患 × 6 archetype |
| complication axis | 212 (ENUM-JP-0487..0698) | 32 疾患 × avg 6.6 合併症 |
| encounter × severity | 104 (ENUM-JP-0699..0802) | 46 encounter × severity |
| **total** | **802** | seed=42 deterministic |

期待動作: 従来 population 由来の fix (mimetype charset drop / clinicaldocument profile 等) が
rare 組合せでも維持され、加えて **cross-seed / cross-axis で新規 rare pattern が露出しないか**
の confirmatory test。

**master**: `cae630bec4`
**未適用 fix**: PR #348 (MedicationRequest.id 64-char length fix) は CI 進行中 → v17 は未適用状態

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- rest pass は `--include-file fhir_r4/Organization.ndjson` (sticky Reference、docs 4.3 推奨手順)
- Data: 345,497 rest + 511,003 obs = **856,500 res** (enumerate、`clinosim` v0.2.0, `country=JP`,
  `level=full`, `seed=42`, master `cae630be`, patients 802)

## Result

| pass | 件数 | 所要 | rps | error 数 | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 345,495 (−17 sticky) | 11.5 min | 500 | **431** | 119 | 0.034% | **0** |
| obs (tx=n/a) | 511,003 | 38.2 min | 223 | **0** | 0 | 0.000% | **0** |
| **合計** | **856,498** | **49.7 min** | 287 | **431** | **119** | **0.014%** | **0** |

- error は全て rest pass 側に集中、obs は完全 pass
- v14 (26,238) / v15 (0) / v16 (1) / v17 (431) の推移で、絶対 error 数は enumerate 特有の rare
  組合せで一時増加、fail 率としては 0.014% (低水準維持)

## 発掘された 3 pattern

### Pattern A: encounter-severity axis の Patient.name が空 (104 patients / 416 errors / 96%)

**現象**: `ENUM-JP-0699..0802` の 104 Patient すべてで:

```
Bundle.entry[N].resource/*Patient/ENUM-JP-0775*/.name[0].family
  Constraint failed: ele-1: 'All FHIR elements must have a @value or children'
  値は空にできません
```

**data 実態**:

```json
"name": [{
  "use": "official",
  "family": "",
  "given": [""],
  "extension": [{"url": "http://hl7.org/fhir/StructureDefinition/iso21090-EN-representation",
                 "valueCode": "IDE"}]
}]
```

`iso21090-EN-representation` の `IDE` (ideographic representation = 漢字表記) を付けているが、
family/given が **空文字列** で emit されている。

**enumerate 分類**:

| kind | 失敗 patient 数 |
|---|---:|
| disease (ENUM-JP-0001..0486) | 0 / 486 |
| complication (ENUM-JP-0487..0698) | 0 / 212 |
| **encounter (ENUM-JP-0699..0802)** | **104 / 104 (100%)** |

**generator-side fix 案**: encounter-severity axis の Patient builder が name populate step を
skip している。以下いずれか:
- name 全体を emit しない (`Patient.name` は cardinality 0..*、無くても structure valid)
- IDE representation なら kanji 文字列を populate、SYL/ABC なら phonetic を populate
- 空文字列を emit する分岐を削除

### Pattern B: ICD-10 コード `S67.2` (Crushing injury of hand) が fhirserver 未収録 (14 errors / 3%)

**現象**: 14 の `ENC-FORCED-0001-*` Encounter の `reasonCode.coding[0].code = "S67.2"` が:

```
Unknown code 'S67.2' in the CodeSystem 'http://hl7.org/fhir/sid/icd-10' version '2019-covid-expanded'
```

**技術背景**: `S67.2` は WHO ICD-10 に有効に存在するコード (前腕・手の圧挫損傷)。
fhirserver に load している ICD-10 CodeSystem version `2019-covid-expanded` に含まれていない。

**precedent**: session 62 で発掘された `R53.1` (PR #335 で JP mapping で R53 に fold) と同種。

**generator-side fix 案**: `S67.2` → `S67` (親コード、上位分類、fhirserver 収録済み) にフォール
バック。または fhirserver 側の ICD-10 版を最新の WHO 版に upgrade。

### Pattern C: MedicationRequest.id が FHIR R4 max 64 文字超過 (1 error / 0.2%、既知)

**現象**: `req-abx-hai-ENC-FORCED-0001-660720751754-clabsi-0-ceftriaxone-narrowed` (70 文字)。

- v16 (seed=700) では 66 文字で 1 件発火、今回 70 文字で 1 件 (別 encounter, ENC-FORCED-0001 系)
- **PR #348 (id length fix) merge 済、v17 未適用**、v18 で再検証予定
- HAI (院内感染) の narrowing (empiric → 起因菌反映後の narrow-spectrum 切替) の id builder が
  長薬剤名 + suffix で越境

## enumerate mode の validation 意義 (実証)

v15/v16 population run では 42 / 42→1 errors だったのに対し、v17 enumerate で 431 errors 出た
のは、**population で偶然発火しない rare 組合せを網羅した効果**:

- Pattern A: encounter axis という population では 1 度も生成されない builder path
- Pattern B: enumerate 特有の `ENC-FORCED-*` encounter (severity 全網羅) で reasonCode に S67.2 が入る組合せが確定発火

つまり enumerate mode は「population run に無い builder path のカバレッジ」を担う、
regression suite として意味を持つことが実証された。generator 側の CI にも enumerate run を
組み込む価値は高い。

## HAPI cluster の JVM 挙動観察

初回 obs 実行 (~4 時間前) は 351k 到達時点で avg_rps=22 に劣化して kill されたが、cluster
fresh restart 後の 2 回目実行は 511k 完走で avg_rps 223 (v15/v16 相当) を維持。

- **同じ obs data + 同じ cluster 設定** で 1 回目 22 rps / 2 回目 223 rps
- 差分は cluster の JVM 世代 (fresh vs 累積)
- 仮説: **per-JVM heap 蓄積** が原因、~350k resource 処理あたりから GC 圧が支配的になる
- 対処案 (実装未): `HAPI_JVM_HEAP=6g` (heap 倍増) / `--chunk` を小さく / obs を 250k ずつ分割
  実行 + cluster 途中再起動

現状は fresh cluster で 500k までは安定という実測が取れた。

## v14 - v17 fail 率推移

| run | data | rest error | obs error | 総 res | fail 率 |
|---|---|---:|---:|---:|---:|
| v14 (cache wipe) | p=1000 s=300 | 26,238 | 0 | 431,784 | 3.04% |
| v14gen (+ PR #342) | p=1000 s=300 | 26,238 | 0 | 431,784 | 3.04% |
| v15 (+ PR #344, sticky) | p=1000 s=300 | 0 | 0 | 431,784 | **0.000%** |
| v16 (seed 変更) | p=1000 s=700 | 1 | 0 | 378,012 | 0.000265% |
| **v17 (enumerate)** | s=42 802pt | 431 | 0 | 856,498 | 0.014% |

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json` — clinosim 生成メタ
- `raw/enumeration_manifest.json` — patient_id → kind/scenario/severity/archetype 逆引き
