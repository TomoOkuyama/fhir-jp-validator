# 2026-07-23 v31 — Phase 3 (MHLW masterB/Z 完全版) 効果測定

## 位置付け

Phase 3 実装 (masterB 傷病名 27,684 concept + masterZ 修飾語 2,390 concept の complete 化)
の効果測定。v30b と同 dataset (clinosim master `0ef6edcf`) を fresh cache で再検証。

## Setup

- fhirserver: Phase 1 (MHLW ICD-10 15,586) + **Phase 3 追加 (masterB + masterZ)** = 8 packages
- **`.hapi-cache/tx-cache/*` 完全 wipe**
- HAPI cluster 6 JVM tx=8181 fresh start
- Data: 35,062 res (v29 と同一)

## Result

| 指標 | 値 | v30b 比 |
|---|---:|---:|
| 所要 | 24.0 min | +7.9 min (cache cold + package 増加) |
| 平均 rps | 24.1 | -33% (fresh cache 影響) |
| error 総数 | **5,115** | ±0 |
| warning 総数 | **51,757** | ±0 |
| information 総数 | **70,791** | ±0 |
| HTTP failed | 0 | ↔ |

## 結果解釈: 現 dataset では **効果ゼロ**、infrastructure は complete 化

v29 dataset (clinosim P=100 seed=300) の receipt code 系 emit 実態:

| system | emit 件数 |
|---|---:|
| `http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterB-disease` | **0** |
| `http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterZ-disease-modifier` | **0** |
| `http://medis.or.jp/CodeSystem/master-disease-keyNumber` | 736 |
| その他 | — |

**clinosim generator は receipt 電算用 masterB/Z code を全く emit していない**。実運用の JP EHR
data (実際にレセプト提出する) が入力された場合に効果を発揮するが、本 test dataset での
error/warning 数変化はゼロ。

## Phase 3 の意義 (measurement 上は静か、infrastructure 上は前進)

現在の効果:
- ✅ **validator infrastructure が真に complete** (masterB/Z code の実在確認と display 検証が可能)
- ✅ jpfhir-terminology の fragment CS (2,000 concept) → 27,684+2,390 concept に override
- ✅ 将来の実 EHR data 検証で fragment warning の発生を予防

Trade-off:
- 現 dataset では error/warning に変化なし
- 実運用データが入ってきたときの検証準備として意味を持つ

## MEDIS master-disease-keyNumber が唯一の receipt 系 emit (736 件)

MEDIS 系 (Phase 4-E) は依然 fragment (2,000 concept)、736 emit のうち fragment 外の code が
warning 化している可能性。**Phase 4-E (MEDIS-DC 会員登録要) が完了すればここも complete 化**、
現 dataset での効果測定が可能に。

## Phase 1 + Phase 3 累積 (v29 → v30b + v31 実測)

| category | v29 | v30b/v31 |
|---|---:|---:|
| MHLW ICD-10 fragment warning | 6,700 | 0 (Phase 1) |
| MHLW ICD-10 display mismatch error | 0 | 420 (Phase 1 で新可視化) |
| MHLW masterB fragment warning | 0 | 0 (data 側 emit 無し) |
| MHLW masterZ fragment warning | 0 | 0 (data 側 emit 無し) |
| **他 fragment warning (HOT13/YJ/MEDIS)** | ~10,378 | 10,378 (継続、Phase 4 対象) |
| Total error | 4,695 | 5,115 (+420 Pattern C 可視化) |

## 次段階

- Phase 4-B (JLAC11): 55x+38x binding、実運用 data で最大効果、licensing 交渉 (JCCLS)
- Phase 4-D/E (MEDIS HOT13/9/7 + master-disease): 会員登録要
- Phase 2 (LOINC JP translation): Regenstrief 通知後
- **本 dataset での効果測定は Phase 4-E 完了時に MEDIS master-disease-keyNumber 736 件で
  可視化見込み**

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
