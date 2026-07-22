# 2026-07-23 v25 — P=100 full-set tx=8181 sanity (obs 含む)

## 位置付け

v24 (`3d173857`, seed=300, P=1000) の obs 10 sample tx=8181 review で発掘した Pattern A/B
を **P=100 の全 resource で full-set 検証**、実際の発生件数と分布を把握する目的。
data は v24 と同 master、seed=300、population だけ 1000 → 100 に縮小 (iteration cycle 短縮)。

- 通常運用の `-tx n/a` 分割検証では **見えない issue** (v24 は fail 率 0.000% だった)
- Observation の tx=8181 検証は 700ms/code の fhirserver 律速で全体重い
  ([architecture.md 参照](../../docs/architecture.md))、P=100 で 26 分は許容範囲

## Setup

- `validator_cli.jar` 6.9.12
- **`-tx http://localhost:8181/r4`** (fhirserver、tx 完全有効)
- **単一 pass** (rest / obs 分割なし)、`--include-file` × 4
  (Organization / Patient / Practitioner / PractitionerRole)
- `--chunk 30 --parallel 24`、`timeout=120s, retries=4`
- Data: **35,062 res** (合成、seed=300, patients 434, master `3d173857`)

## Result

| 指標 | 値 |
|---|---:|
| 総 res | 35,062 (sticky 前置後 processed=34,810) |
| 所要 | **26.6 min** |
| 平均 rps | 21.6 |
| **error 総数** | **7,764** |
| warning 総数 | 50,859 (うち dom-6 narrative 大半) |
| information 総数 | 65,412 |
| **HTTP failed bundle** | **11 bundle (330 res)** — retry 4 でも解消せず、fhirserver 高負荷時の TimeoutError |
| timeouts (issue 内) | 0 |

## resource type 別 fail 分布 (sticky 除外)

| rt | fail res | 総数 | fail 率 |
|---|---:|---:|---:|
| **Observation** | **4,671** | 20,035 | **23.3%** |
| Condition | 736 | 736 | **100%** ⚠️ |
| MedicationRequest | 151 | ? | — |
| Composition | 11 | 490 | 2.2% |
| AllergyIntolerance | 5 | ? | — |

## 発掘 Pattern (v24 obs sample review の 2 pattern を full-set 実測)

### 🔴 Pattern A: LOINC display mismatch (4,657 error、rest/obs 横断)

Observation.code、Observation.component.code、その他 LOINC 参照個所で **canonical display 名と
不一致の short/simplified label emit**。上位 15 unique code:

| # | LOINC code | emit display | 備考 |
|---:|---|---|---|
| 1,252 | **80288-4** | `Level of consciousness AVPU` | canonical: `Level of consciousness AVPU score` |
| **1,165** | **8478-0** | **`Inhaled oxygen delivery system`** | ⚠️ **canonical: `Mean blood pressure` = code/display 意味的誤り疑い、`clinosim/modules/output/_fhir_observations.py:706` 既 clinosim 確認済** |
| 415 | 2160-0 | `Creatinine` | canonical: `Creatinine [Mass/volume] in Serum or Plasma` |
| 352 | 2345-7 | `Glucose` | canonical: `Glucose [Mass/volume] in Serum or Plasma` (推定) |
| 239 | 2823-3 | `Potassium` | canonical: `Potassium [Moles/volume] in Serum or Plasma` |
| 187 | 2951-2 | `Sodium` | canonical: `Sodium [Moles/volume] in Serum or Plasma` |
| 136 | 6690-2 | `White blood cell count` | canonical: `Leukocytes [#/volume] in Blood by Automated count` (推定) |
| 134 | 1920-8 | `Aspartate aminotransferase` | canonical: `Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma` |
| 127 | 1742-6 | `Alanine aminotransferase` | 同上パターン |
| 112 | 1988-5 | `C-reactive protein` | canonical: `C reactive protein [Mass/volume] in Serum or Plasma` |
| 101 | 718-7 | `Hemoglobin` | canonical: `Hemoglobin [Mass/volume] in Blood` |
| 61 | 11331-6 | `History of alcohol use` | canonical: 詳細形 |
| 53 | 3094-0 | `Blood urea nitrogen` | canonical: 詳細形 |
| 39 | 6301-6 | `PT-INR` | canonical: 詳細形 |
| 34 | 42637-9 | `B-type natriuretic peptide` | canonical: 詳細形 |

**分類**:
- **カテゴリ A1 (SHORTNAME emit vs canonical LONG_COMMON_NAME 不一致)**: 大半の code、
  実質 3,492 error。fix は display を LONG_COMMON_NAME に整合させるか display 省略
- **カテゴリ A2 (code/display 意味的誤り、深刻)**: LOINC 8478-0 の 1,165 error。
  code は "Mean blood pressure" を指すが display は "Inhaled oxygen delivery system" を emit、
  **clinosim 側で該当 code の割当 pattern 確認要**

### 🔴 Pattern B: JP_Patient_eCS profile 未 match (3,096 error、cross-type)

lab-* Observation、Condition、MedicationRequest 等の **subject reference が JP_Patient_eCS
profile 準拠 Patient を要求** するが、clinosim Patient は `JP_Patient` (core) 準拠のみ、
`meta.profile` に `JP_Patient_eCS` 宣言なし。

| rt | error 数 |
|---|---:|
| Observation.subject | 2,193 |
| Condition.subject | 736 |
| MedicationRequest.subject | 151 |
| その他 | 16 |
| 計 | **3,096** |

**Condition 100% fail** はこれで説明可能 (全 Condition の subject が eCS profile 要求)。

**fix**: Patient.ndjson の全 Patient に `meta.profile = [..., "http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Patient_eCS|1.12.0"]` を追加宣言 (multi-profile 宣言、core と併記可)

## 他 error (少数)

- Composition 11 error: eReferral cross-bundle slice (v15 以来の client-side infra 制約)
- AllergyIntolerance 5 error: SNOMED CT code 系の issue (詳細未確認)

## HTTP failed bundle 11 件 (330 res)

fhirserver 高負荷時の TimeoutError で、retry=4 でも解消せず。全て obs bundle
(`lab-ENC-*` 系)。以下の意味を持つ:

- 700ms/code × chunk 30 res × 平均 3-5 code = 60-100 秒/bundle、`timeout=120s` を超える bundle
  が発生
- fhirserver 側 CPU が 76% (single-core 飽和) に張り付いて処理捌けず
- retry でも fhirserver 状態が改善しないため同じ bundle が繰り返し失敗

**対処**: `--timeout 300` に増やす or `--chunk 15` に減らして bundle 単位を小さくすれば失敗
0 になる見込み (次 run で試す価値あり)。

## v24 (P=1000 tx=n/a) vs v25 (P=100 tx=8181) の意味

| 指標 | v24 (P=1000, tx=n/a 分割) | v25 (P=100, tx=8181 全 tx) |
|---|---:|---:|
| データ規模 | 428,509 res | 35,062 res (1/12) |
| 所要 | 23.5 min | 26.6 min |
| **fail 率** | **0.000%** | **22.3%** (7,764/34,810) |
| **意味** | 構造/slice 準拠、terminology skip | 完全 conformance |

**v24 の "0.000%" は terminology 未検証を含む structure conformance の意味だった** ことが
v25 で実証。同 dataset を tx=8181 で回すと 2 major pattern が大量発火する状態。

## 対応方針提案 (v24-v25 で確立)

1. **短期 (今週)**: clinosim 側で 2 pattern 修正
   - Pattern A: LOINC display の canonical 整合 (top 15 code から順に fix)、特に 8478-0 の
     code/display 意味的誤り最優先
   - Pattern B: Patient.meta.profile に `JP_Patient_eCS` 追加宣言
2. **中期 (1-2 週間)**: run cycle に **obs tx=8181 sanity check** を組み込む
   - P=100 全 tx (26 分) を merge 前 CI に、または obs 100 sample (~1 分) を各 chain merge 後
     の quick check に
3. **長期 (1-2 ヶ月)**: 恒久的に obs tx=8181 が現実的時間で回るための性能改善
   - AWS native amd64 (Rosetta 除去で +30-40%)
   - fhirserver Pascal `Display()` cache 化 or 日本語 translation 事前 index 化
     ([architecture.md の対処 B/C 参照](../../docs/architecture.md))

## 参考 (前 review)

- v24 obs 10 sample tx=8181 review: [`../2026-07-23_obs_sample_review_tx_enabled/`](../2026-07-23_obs_sample_review_tx_enabled/)
- v24 population run (tx=n/a): [`../2026-07-23_full_v24_p1000/`](../2026-07-23_full_v24_p1000/)

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/all.failed.ndjson` (git-ignored、11 bundle timeout)
- `raw/generator-metadata-snapshot.json`
