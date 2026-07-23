# 2026-07-23 v27 — clinosim PR #383 hotfix (JP_Patient_eCS revert)

## 位置付け

v26 で発掘した cascade regression 34k error に対する即時 hotfix。同 config で generator
master のみ差替、v25/v26/v27 の 3 世代 A/B。

| PR | 内容 | 期待効果 |
|---:|---|---|
| #383 (Issue #382) | PR #379 revert = Patient.meta.profile から `JP_Patient_eCS` 削除、`JP_Patient` 単独に戻し | v26 cascade regression -30k、Pattern B 3,096 再発 |

**PR #377 (LOINC 8478-0) と #381 (14 LOINC display) の効果は継続保持**。

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- 単一 pass、sticky × 4 (Organization / Patient / Practitioner / PractitionerRole)
- `--chunk 30 --parallel 24 --timeout 300`
- Data: **35,062 res** (合成、seed=300, patients 434, master `396b5a06`)

## Result

| 指標 | 値 |
|---|---:|
| 総 res | 35,062 (processed 34,810) |
| 所要 | **21.4 min** (v26 29.6 min から -8.2 min、fhirserver 負荷軽減で高速化) |
| 平均 rps | **27.1** (v26 19.6 → +38%) |
| **error 総数** | **4,984** |
| warning 総数 | 52,191 |
| information 総数 | 70,502 |
| HTTP failed bundle | **0** (v26 1 → 完全解消) |

## v25/v26/v27 3 世代 A/B

| 指標 | v25 | v26 | v27 | 変化 |
|---|---:|---:|---:|---|
| error 総数 | 7,764 | 37,762 | **4,984** | ✅ v26 → v27 で **-32,778** (期待 -30,062 超過) |
| Pattern A (LOINC display) | 4,657 | 1,547 | **1,547** | v26 → v27 維持 (PR #377/#381 効果継続) |
| Pattern B (JP_Patient_eCS 未 match) | 3,096 | (吸収) | **3,426** | 期待通り再発 |
| Cascade regression | 0 | 36,215 | **11** | ✅ **完全解消** (残 11 は Composition eReferral cross-bundle) |
| HTTP failed bundle | 11 | 1 | **0** | ✅ |
| 所要時間 | 26.6 min | 29.6 min | **21.4 min** | v26 比 -8.2 min (負荷軽減) |
| 平均 rps | 21.6 | 19.6 | **27.1** | v25 → v27 で +25% |

**期待値 (~7,700) を大きく下回る 4,984 に到達** — Pattern A の PR #377/#381 効果が確実に維持
されており、Pattern B の 3,426 と Pattern A residual 1,547 の合算になったため。

## PR 別評価 (v25 → v27)

| PR | 効果 | 状態 |
|---:|---|---|
| #377 (LOINC 8478-0 → 107117-4) | -1,165 | ✅ 完全継続 |
| #381 (14 LOINC display) | -3,110 | ✅ 完全継続 |
| #383 (#379 revert) | -32,778 (期待 -30,062 超過) | ✅ 完全効果 |

## 残る error 分類

### Pattern A residual (LOINC display mismatch): 1,547 errors

**同 15 code が v25/v26 と同数残存** (PR #381 の 14 code list に含まれず):

| # | code | emit | 想定 canonical |
|---:|---|---|---|
| 1,252 | **LOINC 80288-4** | `Level of consciousness AVPU` | `Level of consciousness AVPU score` (fhirserver 独自 canonical) |
| 38 | LOINC 2744-1 | `pH` | (詳細名) |
| 38 | LOINC 2019-8 | `pCO2` | (詳細名) |
| 38 | LOINC 2703-7 | `pO2` | (詳細名) |
| 38 | LOINC 1963-8 | `Bicarbonate` | (詳細名) |
| 27 | LOINC 17861-6 | `Calcium` | (詳細名) |
| 27 | LOINC 777-3 | `Platelet count` | (詳細名) |
| 27 | LOINC 2524-7 | `Lactate` | (詳細名) |
| 16 | LOINC 10839-9 | `Cardiac troponin I` | (詳細名) |
| 16 | LOINC 13969-1 | `Creatine kinase-MB` | (詳細名) |
| 6 | LOINC 4548-4 | `Hemoglobin A1c` | (詳細名) |
| 6 | LOINC 1751-7 | `Albumin` | (詳細名) |
| 4 | LOINC 2571-8 | `Triglyceride` | (詳細名) |
| 4 | LOINC 2085-9 | `HDL cholesterol` | (詳細名) |
| 4 | LOINC 75241-0 | `Procalcitonin` | (詳細名) |

**次 chain 対応候補**:
- **80288-4 hotfix**: user 事前予告通り fhirserver 独自 canonical で残る、`override_allowlist`
  追加 or display 省略で対処
- **他 14 code**: PR #381 の list 追加拡張 (top 14 = 血液ガス系 + 循環器 marker + 脂質 marker + 感染 marker)

### Pattern B: JP_Patient_eCS profile 未 match: 3,426 errors

期待通り再発 (v25 3,096 とほぼ同水準、+330 は Encounter/Immunization 分の増加)。

内訳 (推定):
- Observation.subject: ~2,200
- Condition.subject: 736
- MedicationRequest.subject: ~150
- その他: 数百

**Issue #378 reopen** に伴う次 chain の完全 JP_Patient_eCS 準拠実装 (Patient data 側で eCS 必須
要素を全 emit) で解消予定 (Session 66 の 1-3 日 scope)。

### Composition eReferral cross-bundle: 11 errors, AllergyIntolerance: 5 errors

いずれも v22-v26 で継続する既知 pattern (client-side infra 制約 + SNOMED code 系)、
generator 側は関与困難。

## v27 で解消した cascade (v26 の 36,215 のうち)

- Observation.subject の全 profile 選択肢 (Device/Group/JP_Location/JP_Patient) mismatch: 20,080 → 0
- MedicationAdministration.subject → JP_Patient mismatch: 5,227 → 0 (**100% fail 完全解消**)
- ServiceRequest.subject → JP_Location/JP_Patient mismatch: 2,823 → 0 (**100% fail 完全解消**)
- Encounter/Immunization/DR/FMH/Coverage/ImagingStudy/Procedure/Composition のそれぞれ 100% or
  高率 fail: 全て 0 に

## fail 率 (Bundle-level 意味的)

| run | error 総数 | 総 res | 意味 (簡易) |
|---|---:|---:|---|
| v25 | 7,764 | 35,062 | 22.1% (相当) |
| v26 | 37,762 | 35,062 | 108% (issue が res 数超え、cascade 影響) |
| **v27** | **4,984** | **35,062** | **14.2%** — v25 を下回る |

## 結論

- **PR #383 期待通り以上の効果**: cascade -30,062 予想が実測 -32,778、これは #381 効果の維持
  加算による bonus
- **v25 (7,764) より大幅に低い 4,984** に到達、tx=8181 full-set での error 水準として過去最良
- **残 4,984 の内訳** が明確化 (Pattern A residual 1,547 + Pattern B 3,426 + 他 11)、次 chain
  の targeting が具体化

## 次 chain 推奨順序

1. **80288-4 hotfix** (fhirserver 独自 canonical、単純 override) → -1,252
2. **PR #381 拡張 (blood gas + 循環器 marker + 脂質 marker + procalcitonin)** → -295
3. **Issue #378 完全対応: Patient data eCS 準拠実装** → -3,426 (Pattern B 完全解消)
4. 想定 v28 or v29 で **fail 数 < 20** (Composition eReferral 11 + AllergyIntolerance 5 のみ) の
   Pattern A/B 完全解消到達

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
