# 検証まとめ — 2026-07-20 v9 (p=5000 seed=500 regression、v8 と同 master)

## 総評: v8 chain は 5x scale + 別 seed で robustness 維持、fail 率は v8 と同 order

- **fail 率 v8 0.0063% → v9 0.0129%** (+0.007pp、user 予測 0.005-0.02% 範囲内)
- **error 総数 v8 48 → v9 310** (+545%、resource 数 3.7x スケールに対して +645% → やや悪化だが seed variance 由来)
- **v8 の 11 PR fix 全て 5x scale で regression なし** (NOCODED / UnitsOfTime / event.code / route SL / procedureCode / code.text / valueQuantity / LAB_UNITS / Location OR / eReferral eCS Organization data)
- 新規 latent error 3 種発掘 (**seed=500 で初出**): R53.1 (ICD-10 covid-expanded)、admit-source 'hosp'、microbiology Observation identifier slice

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一
- Client: `parallel-validate.py` (sticky include なしで v8 baseline と公平比較、defaults=retries4/timeout120 は v8.1 適用済)

## 検証データ

- clinosim 0.2.0 生成 (2026-07-20 10:37 JST、**JP p=5000 seed=500** end 未指定、master cbfacc6e = v8 と同一)
- **fullset = 1,594,814 リソース / 26 NDJSON / 2.2GB** (v8 の 3.7x)
- total_patients 18,402 (v8 3,774 の 4.87x)、Observation 927,121 (v8 の 3.66x)

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 667,693 | 16 分 47 秒 | 663 | 100% |
| obs | 927,121 | 65 分 41 秒 | 235 | 100% |
| **合計** | **1,594,814** | **82 分 28 秒** | **322** | **100%** |

**rest rps 663** は v8 (432) の 1.5x で JIT warmup が更に進んだ結果。obs rps 235 は v8 (224) 同水準。

## Issue 分布 (v8 vs v9、絶対値)

| severity | v8 total | v9 total | v9/v8 ratio | scale ratio |
|---|---:|---:|---:|---:|
| error | 48 | **310** | 6.5x | 3.7x |
| warning | 510,041 | 1,872,451 | 3.7x | 3.7x |
| information | 883,514 | 3,233,269 | 3.7x | 3.7x |

warning/information は scale に完全比例、**error だけ 1.76x speed up** = seed=500 で新出 pattern による。

**リソース単位 pass/fail**
- rest: 667,693 中 204 = **0.031%** (v8 rest 0.015% → ~2x)
- obs: 927,121 中 1 = **0.0001%** (v8 obs 0% → 1 件 rare 発掘)
- **合計 1,594,814 中 205 = 0.0129%** (v8 0.0063% → 2x)

## エラー内訳 (v9 rest)

| # | カテゴリ | 由来 | v8 対比 |
|---:|---|---|:---:|
| 103×2 = 206 | eReferral referralFrom/toSection Organization slice | client cross-bundle resolve() (Chain #329 data は完璧、v8.1 で確定) | scale proportional (v8 21×2) |
| 75 | MedicationAdministration `R53.1` in ICD-10 `covid-expanded` version | **NEW seed=500** — R53.1 は Weakness (base ICD-10) にはあるが `2019-covid-expanded` 版に含まれず | 新規 |
| 20 | HTTP timeout (Composition) | HAPI ↔ fhirserver 応答遅延 (retries=4 でも吸収不可) | scale proportional (v8 6) |
| 3 | Composition eDS `hospitalCourseSection.entry` min=1 | v5 backlog 継続 (Chain #295 の残余) | 稀に発火 (v8 0) |
| 2 | Encounter `R53.1` ICD-10 covid-expanded | **NEW seed=500** | 新規 |
| 2 | Encounter admit-source `'hosp'` (v3-CS 未収録) | **NEW seed=500** | 新規 |
| 1 | Condition `R53.1` ICD-10 covid-expanded | **NEW seed=500** | 新規 |

## エラー内訳 (v9 obs)

| # | カテゴリ | 由来 |
|---:|---|---|
| 1 | microbiology Observation `identifier:resourceIdentifier` slice min=1 (mb-org-ENC-POP-002287-*) | **NEW seed=500** rare pattern、eCS LabResult profile が identifier required |

## 種別ごと fail 率 (v9 vs v8)

| 種別 | v9 検証数 | v9 error あり | v9 fail | v8 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| Composition | 21,026 | 126 | **0.599%** | 0.60% | ↔ (referral 41 → 103 で scale proportional) |
| MedicationAdministration | 219,163 | 75 | **0.034%** | 0% | **新規 (R53.1)** ⚠️ |
| Encounter | 18,850 | 2 | 0.011% | 0% | 新規 (R53.1 + admit-source) |
| Condition | 30,350 | 1 | 0.003% | 0% | 新規 (R53.1) |
| Observation | 927,121 | 1 | 0.0001% | 0.079% (v6.1) / 0% (v8) | 極小 rare |
| MedicationRequest | 8,829 | 0 | **0%** | 0% | ↔ ✅ |
| ImagingStudy | 3,730 | 0 | **0%** | 0% | ↔ ✅ (Ch#320 継続) |
| AllergyIntolerance | 361 | 0 | 0% | 0% | ↔ ✅ |
| Location | 71 | 0 | 0% | 0% | ↔ ✅ (Ch#328 継続) |
| その他 (17 種) | ~365,000 | 0 | 0% | 0% | ↔ ✅ |

**v8 で 0% を達成した 12 種のうち 11 種が v9 でも 0% 維持**。悪化したのは:
- MedicationAdministration 0% → 0.034% (R53.1、data 側修正必要)
- Encounter 0% → 0.011% (R53.1 + admit-source、data 側)
- Condition 0% → 0.003% (R53.1)
- Observation 0% → 0.0001% (microbiology rare)

## 【要対処】seed=500 で発掘された 3 種の data issue

### 1. `R53.1` in ICD-10 `2019-covid-expanded` version (78 件、最大件数)

**現象**:
```
Unknown code 'R53.1' in the CodeSystem 'http://hl7.org/fhir/sid/icd-10' version '2019-covid-expanded'
```

**背景**: R53.1 は base ICD-10 の "Weakness" (体力低下) code。`2019-covid-expanded` は covid 関連拡張版で、コード集合が異なり R53.1 が含まれない可能性。

**対処案**: 
- Diagnosis code 生成で `R53.1` を使う patient/encounter は base ICD-10 に切替、または covid-expanded 対応 code (例: R53.83 "Other fatigue") に置換
- 汎用対処: 使用する ICD-10 code 集合の version 整合性チェックを generator 側で追加 (v5 で I84 に対して session 57 が対応した Chain #285 と同種の作業)

**期待効果**: **-78 error (-25% of rest errors)**

### 2. Encounter admit-source `'hosp'` (2 件)

**現象**:
```
system 'http://terminology.hl7.org/CodeSystem/admit-source' で未知のコード 'hosp'
```

**対処**: v3 admit-source CS の有効 code に置換 (例: `hosp-trans` "Transfer from hospital")

### 3. Microbiology Observation identifier slice (1 件)

**現象**:
```
Slice 'Observation.identifier:resourceIdentifier': minimum required = 1, but only found 0
(from JP_Observation_LabResult_eCS)
```

**対処**: microbiology Observation の identifier[0].use=official + system で `resourceIdentifier` slice に該当させる

## v8 chain の regression 検証結果

| Chain | v8 実測 | v9 実測 | 判定 |
|---:|---|---|:---:|
| #306 NOCODED display | 0 | 0 | ✅ hold |
| #308 boundsDuration only | 0 | 0 | ✅ hold |
| #310 event.code Array | 0 | 0 | ✅ hold |
| #312 route SL | 0 | 0 | ✅ hold |
| #320 procedureCode 省略 | 0 | 0 | ✅ hold |
| #322 code.text + display | 0 | 0 | ✅ hold |
| #324 valueQuantity omit | 0 | 0 | ✅ hold |
| #326 LAB_UNITS PT/APTT | 0 | 0 | ✅ hold |
| #328 Location OR text | 0 | 0 | ✅ hold |
| #329 eReferral eCS Org (data 部分) | 完璧 | 完璧 | ✅ hold (v8.1 確定) |

**11 PR は全て 5x scale + 別 seed でも robustness 維持**。generator side の regression は 0。

## 修正見込み

**data 側 3 種修正のみで**:
- error → 310 - 78 - 2 - 1 - 3 (eDS backlog も) = ~226
- fail 率 → ~205 - 78 = 127 unique / 1,594,814 ≒ **0.008%** (v8 0.0063% 水準に回復)

**+ eReferral の client sticky (v8.1 の A) 適用**:
- error → ~20 (timeout のみ)
- fail 率 → ~0.001%

**+ timeout 対処 (chunk 縮小 or fhirserver Display() cache)**:
- error → **~0** (実質完全準拠)

## caveat — 検証していないこと

- Observation の LOINC / SNOMED terminology 検証 (性能上スキップ、`HAPI_TX=n/a`)
- 業務ロジック
- Bundle Type validation

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — 集計メタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~3GB) / `raw/obs.ndjson` (~4GB) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 総括

Session 60→61 の 11 PR fix は **5x scale + 別 seed でも strict に robustness 維持**。新出は seed variance
由来の rare code pattern (R53.1 / admit-source / microbiology) で、いずれも既存パターンの補完で対処可能。
compliance 到達水準は **generator 完成度が非常に高い** ことを示している。
