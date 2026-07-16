# 検証まとめ — 2026-07-16 (1/20 sample)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- 元データ: JP EHR 由来 FHIR R4 (26 リソース種別、総 3.58M リソース)
- 本 run: **1/20 sample = 179,195 リソース**
- 分布: Observation 65% (115,718)、他 25 種 35% (63,477)

## 検証戦略 — 分割検証

Observation の LOINC 日本語 display 検証が fhirserver で per-code ~700ms かかり、単一 pass では完走しないため、以下 2 パス:

| pass | 対象 | tx 設定 | HAPI_EXTRA_ARGS |
|---|---|---|---|
| rest | 25 種 (非 Observation) | `-tx=http://localhost:8181/r4` | `-best-practice ignore -check-display Ignore` |
| obs | Observation | `-tx=n/a` (構造/slice のみ) | `-best-practice ignore` |

詳細と背景: [docs/real-world-validation.md](../../docs/real-world-validation.md)

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 63,477 | 3 分 27 秒 | 307 | 100% |
| obs | 115,718 | 7 分 21 秒 | 262 | 100% |
| **合計** | **179,195** | **10 分 48 秒** | **276** | **100%** |

- rest 側 quarantined port: なし
- obs 側 quarantined port: なし
- 全 Bundle で HTTP timeout ゼロ

## Issue 分布

| severity | rest | obs | 合計 |
|---|---:|---:|---:|
| error | 73,473 | 326,184 | **399,657** |
| warning | 116,433 | 86,094 | **202,527** |
| information | 52,709 | 164,163 | **216,872** |

**リソース単位 pass/fail**:
- rest: 63,477 中 35,674 (56.2%) に 1+ error
- obs: 115,718 中 80,778 (69.8%) に 1+ error
- **合計 179,195 中 116,452 (65.0%) に 1+ error**

## 種別ごと fail 率 (error あり率)

| 種別 | 検証数 | error あり | fail 率 |
|---|---:|---:|---:|
| MedicationAdministration | 26,626 | 26,626 | **100%** |
| Condition | 3,142 | 3,142 | **100%** |
| CareTeam | 1,913 | 1,913 | **100%** |
| MedicationRequest | 824 | 824 | **100%** |
| Patient | 294 | 294 | **100%** |
| AllergyIntolerance | 44 | 44 | **100%** |
| DiagnosticReport | 1,205 | 1,035 | 85.9% |
| ImagingStudy | 340 | 268 | 78.8% |
| Observation | 115,718 | 80,778 | 69.8% |
| Practitioner | 6 | 1 | 16.7% |
| Composition | 2,225 | 200 | 9.0% |
| ServiceRequest | 16,260 | 1,314 | 8.1% |
| Encounter | 1,967 | 13 | 0.7% |
| (他 12 種) | ~9,000 | 0 | 0% |

## 検出された主要 issue パターン (上位、実測 error 数)

### 構造・必須要素の欠落 (eCS プロファイル)

- Observation.specimen 必須欠落: 28,128
- Observation.meta.lastUpdated 欠落: 14,128
- Observation.identifier 欠落: 14,127
- Observation.status 欠落: 14,064
- Condition の identifier / meta.lastUpdated / clinicalStatus.coding.display / verificationStatus.coding.display: 各 3,142

### Slice / Constraint 違反

- Observation.category CodeSystem 不一致 (JP ↔ HL7 双方向): 111,623
- eCS Slice minimum required: 40,600 (obs) + 8,526 (rest)
- Observation.referenceRange.extension URL/型不正: 14,064 × 3
- MedicationAdministration.dosage.dose.Quantity.code 欠落: 24,780
- MedicationAdministration ルール mad-1: 1,846
- Condition ルール con-4: 1,292

### Code / ValueSet 違反

- CareTeam.category LOINC LA27976-8 (存在しない code): 1,913
- ICD-10 未登録 code (E11.65, S72.00 等): ~5,000
- MedicationRequest.periodUnit 日本語独自値 (`日` 等): 752
- ServiceRequest.code.coding.code 空文字: 1,251

### validator noise (data 側の問題ではない)

- dom-6 Best Practice narrative missing: 133,717
- SNOMED/LOINC 日本語 display なし: 30,000+
- 未知の CodeSystem `urn:oid:...1005` (日本の医療機関コード): 14,998

## caveat — 検証していないこと

- **Observation の LOINC / SNOMED terminology 検証**: 性能上スキップ (fhirserver 日本語 display 照合が per-code ~700ms、11 万件を通せない)。構造/slice/invariant のみ。code 妥当性は別途サンプリングで追試を推奨
- **業務ロジック**: 診療報酬点数、レセプト整合、医療的妥当性は対象外 (FHIR 準拠性のみ)
- **Bundle Type validation**: client が `collection` 化するため `transaction`/`document` の制約は非対象

## raw ファイル

- `raw/rest_result.meta.json` — rest pass のメタ (commit 対象)
- `raw/obs_result.meta.json` — obs pass のメタ (commit 対象)
- `raw/rest_result.ndjson` — 全 error/warning の生 OperationOutcome (~314 MB、gitignore)
- `raw/obs_result.ndjson` — 同上 (~758 MB、gitignore)

生 ndjson が必要な場合は別途連絡を。

## 次の run で改善すべき点

- (validator 側) fhirserver 日本語 display 照合の高速化、または `$validate-code` から display を落とす経路の実装
- (data 生成側) `generator-feedback.md` の【最優先 1〜5】対処 — 期待 fail 率 65% → 15% 以下
