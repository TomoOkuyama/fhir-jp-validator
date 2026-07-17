# 検証まとめ — 2026-07-18 v3 (session 57 8 chain PR 追加 merge 後 fullset)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-18 04:41 JST、JP p=1000 seed=300、master 57f2c09b)
- **fullset = 424,395 リソース / 28 NDJSON**
- session 57 merged 8 chain (#215/#217/#220/#222/#224/#226/#228/#230) 反映済み

## 分布

| 種別 | 件数 | 占有 |
|---|---:|---:|
| Observation | 248,982 | 58.7% |
| MedicationAdministration | 64,510 | 15.2% |
| ServiceRequest | 35,922 | 8.5% |
| Specimen | 31,162 | 7.3% |
| DocumentReference | 10,299 | 2.4% |
| Condition | 6,242 | 1.5% |
| Composition | 4,474 | 1.1% |
| Encounter | 3,898 | 0.9% |
| CareTeam | 3,786 | 0.9% |
| Immunization | 2,966 | 0.7% |
| ClinicalImpression | 2,497 | 0.6% |
| DiagnosticReport | 2,286 | 0.5% |
| MedicationRequest | 1,887 | 0.4% |
| 他 15 種 | 5,488 | 1.3% |

## 検証戦略

前回同様の分割 (rest tx 有効 / obs tx=n/a)。

| pass | 対象 | tx 設定 | HAPI_EXTRA_ARGS |
|---|---|---|---|
| rest | 25 種 (非 Observation) 175,413 | `-tx=http://localhost:8181/r4` | `-best-practice ignore -check-display Ignore` |
| obs | Observation 248,982 | `-tx=n/a` (構造/slice のみ) | `-best-practice ignore` |

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 175,413 | 5 分 56 秒 | 493 | 100% |
| obs | 248,982 | 15 分 23 秒 | 270 | 100% |
| **合計** | **424,395** | **21 分 19 秒** | **332** | **100%** |

- rest 側 rps 493 は前回 v2 405 の +22% (JIT warm と data 分布差)
- obs 側 rps 270 は前回 v2 249 の +8%
- 全 Bundle で HTTP timeout ゼロ、quarantined port ゼロ

## Issue 分布 (v2 vs v3)

| severity | v2 total | v3 total | 変化 |
|---|---:|---:|---:|
| error | 85,195 | **38,835** | **-54%** |
| warning | 468,175 | 477,616 | +2% |
| information | 856,028 | 868,628 | +1.5% |

**リソース単位 pass/fail** (1+ error あり)
- rest: 175,413 中 17,826 = **10.16%**
- obs: 248,982 中 176 = **0.07%**
- **合計 424,395 中 18,002 = 4.24%**

**v2 → v3 で fail 率 11.9% → 4.24% (-7.66pp)** の大幅改善達成。

## 種別ごと fail 率 (v2 比較)

| 種別 | 検証数 | error あり | v3 fail | v2 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| Observation | 248,982 | 176 | **0.07%** | 12.4% | **-12.3pp** ✅✅✅ |
| Condition | 6,242 | 6,242 | 100% | 100% | ↔ (PR #192 未 merge) |
| CareTeam | 3,786 | 3,786 | 100% | 100% | ↔ (SNOMED code 差替済だが 407484005 も未収録) |
| MedicationRequest | 1,887 | 1,887 | 100% | 100% | ↔ (PR #197 未 merge、残 sub-issue 継続) |
| Patient | 580 | 580 | 100% | 100% | ↔ (JP_Patient_BloodTypeCode ext 未認識) |
| AllergyIntolerance | 75 | 75 | 100% | 100% | ↔ |
| ImagingStudy | 760 | 567 | 74.6% | 73.1% | ↔ |
| Composition | 4,474 | 422 | 9.4% | 9.3% | ↔ (eDischargeSummary profile 制約) |
| MedicationAdministration | 64,510 | 4,072 | **6.3%** | 5.9% | +0.4pp (mad-1 微増) |
| Practitioner | 100 | 10 | 10.0% | 10.0% | ↔ |
| Location | 71 | 4 | 5.6% | 5.6% | ↔ |
| Encounter | 3,898 | 36 | 0.9% | 1.1% | ↔ |
| DiagnosticReport | 2,286 | 12 | **0.5%** | 84.7% | **-84.2pp** ✅✅✅ (PR #217) |
| ServiceRequest | 35,922 | 133 | 0.3% | 0.3% | ↔ |
| Specimen | 31,162 | 0 | **0%** | 0% | ↔ |
| DocumentReference/Immunization/ClinicalImpression/FamilyMemberHistory/Endpoint/Coverage/Procedure/PractitionerRole/Device/DeviceUseStatement/Organization | ~30,000 | 0 | 0% | 0% | ↔ |

## Session 57 chain 実測結果サマリ

| PR | 対象 | 期待効果 | 実測効果 | 判定 |
|---:|---|---:|---:|:---:|
| #215 | CIF metadata clinosim_version | 追跡性 | `_generator_metadata.json` に版・commit・recent_merges 含む | ✅ |
| #217 | DR category:first slice (labresult + microbiology) | -2,196 | 実測 -2,184 (2,196→12) | ✅✅ |
| #220 | Obs.identifier:resourceIdentifier slice | -30,315 | **実測 -30,315 (0 件)** | ✅✅ |
| #222 | English-only CS への JA display 復活停止 walker | ~-2,500 | 実測 -1,800 (2,500→700)、部分成功 | ⚠️ |
| #224 | CareTeam SNOMED 735320007 → 407484005 | -3,788 | 実測 0pp 改善 (旧 code は消滅、新 code もローカル SNOMED に不在) | ❌ |
| #226 | Condition con-4 (chronic-primary abatement) | -2,452 | **実測 -2,452 (0 件)** | ✅✅ |
| #228 | Composition.section.text.status generated → additional | -750 | **実測 -750 (0 件)** | ✅✅ |
| #230 | MR status/intent/substitution codeable | -3,236 | **実測 -3,236 (0 件)** | ✅✅ |

**期待合計 -45,237 → 実測 -38,745** (期待の 86%)。#222 と #224 が想定以下、他は完全解決。

## 確認したい 6 項目 + 保留の回答

1. 【最優先 1】**Obs.identifier:resourceIdentifier slice**: v2 30,315件 → **v3 0 件** ✅
2. 【最優先 2】**CareTeam SNOMED 407484005 (新) は認識されない**: 3,786 件が unknown-code エラー (`Unknown code '407484005' in the CodeSystem 'http://snomed.info/sct' version '.../20260601' (International Edition)`)。fhirserver の SNOMED International 2026-06-01 に 407484005 は **収録されていない** ← IG バグではなくローカル terminology のカバレッジ問題
4. 【最優先 4】**Condition con-4**: v2 2,452件 → **v3 0 件** ✅
5. 【最優先 5】**MR status/intent/substitution**: 3 種すべて **v3 0 件** ✅
7. 【中優先 7】**ICD-10 日本語 display "Wrong Display Name"**: v2 2,500件 → **v3 700 件 (-72%)**、部分改善。残 codes: E11 (458), Z23 (211), F00 (20), J44 (9), T54 (2)
8. 【中優先 8】**Composition.section.text.status generated**: v2 750件 → **v3 0 件** ✅

【保留 3】**MAR mad-1 (2,755→3,005)** 原因判明:
- fhirserver 独自 invariant ではなく **FHIR R4 base の mad-1** = `MedicationAdministration.dosage.dose.exists() or MedicationAdministration.dosage.rate.exists()`
- 実データ (`mar-ENC-POP-000051-598525354050-00018` 等) の `dosage` 内容: `text="Sliding scale insulin"`, `route=SC` のみで **dose も rate も無い**
- Sliding scale (血糖に応じて可変量) や PRN 投薬など、臨床上「単一 dose を書けない」ケースで発火。statusReason は無関係

## v3 で残る主要 issue (対処要否)

### rest 側 (要修正)

| # | 対象 | 対処案 |
|---:|---|---|
| **6,242 × 2** | Condition eCS 必須欠落 (identifier + medisRecordNo slice) | PR #192 (既 issue) merge |
| **3,786** | CareTeam SNOMED 407484005 unknown | ローカル SNOMED CT に含まれる別コードへ差替 or 独自 CS 化 (下記詳細) |
| **3,005** | MedicationAdministration mad-1 (dose/rate 不在) | dosage の型設計見直し (下記詳細) |
| **1,887 × 各種** | MedicationRequest_eCS: identifier count 3、requestIdentifier slice、UnitsOfTime 'd'、Dosage.doseAndRate.type、course-of-therapy display | PR #197 (既 issue) merge |
| **580 × 2** | Patient: `JP_Patient_BloodTypeCode` extension URL 未認識 + `ja-JP` language display "日本語(日本)" | extension URL の正規 canonical 化 or 削除、language display は英語 "Japanese(Japan)" 使用 |
| **458** | ICD-10 E11 "Type 2 diabetes mellitus without complications" 誤 display | 正しい表記 `Type 2 diabetes mellitus : Without complications` に修正 (walker #222 の抜け) |
| **422** | Composition eDischargeSummary profile 制約 (extension:version, category, author≥2, section.section≥10) | eDischargeSummary 用の生成分岐で必須要素を満たす |
| **223** | ImagingStudy RadLexPlaybook ValueSet 非包含 | RadLex codebook 追加 or JP 用 CS へ差替 |
| **211** | ICD-10 Z23 display 不一致 | 正しい表記 `Need for immunization against single bacterial diseases` へ |
| **151 × 4** | Composition eReferral profile 制約 (extension:version, id system URL, doc-typecodes CS URL) | eReferral 生成分岐修正 |
| **148/135** | LOINC 未知 code `45391-8`, `42346-6` | 使用箇所と data source 確認 |
| **75** | AllergyIntolerance 詳細未調査 (少数、要 dive) | — |

### obs 側 (残 176 件)

| # | 対象 | 対処案 |
|---:|---|---|
| **166** | Observation.code.text 欠落 (JP_Observation_LabResult) | Obs の code.text 必須化 |
| **147** | Observation.value[x]:valueCodeableConcept.coding.display 欠落 | qualitative Obs で display 追加 |
| **20** | ele-1 空要素 | 空 element 削除 |
| **10 × 2** | referenceRangeLow/HighUnits-isSameAs-resultValueUnits invariant | 基準値 unit と結果値 unit を完全一致に |

## validator noise (data 側の問題ではない)

- SNOMED/LOINC 日本語 display なし: info、対処不要 (`-check-display Ignore` で抑止済)
- `urn:oid:...1005` 未知 CodeSystem: warning、対処不要
- `warn-localCode-observation-laboresult`: warning、情報のみ
- `http://clinosim.dev/fhir/CodeSystem/*` 未知 CodeSystem: warning、対処不要

## caveat — 検証していないこと

- **Observation の LOINC / SNOMED terminology 検証**: 性能上スキップ、構造/slice/invariant のみ
- **業務ロジック**: 診療報酬点数、レセプト整合、医療的妥当性
- **Bundle Type validation**: client が `collection` 化するため `transaction`/`document` の制約は非対象

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~800MB 推定) / `raw/obs.ndjson` (~2.5GB 推定) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 次サイクルの見込み

**v2 → v3 で fail 率 11.9% → 4.24% (-7.66pp)** 達成。

残り主要 issue の対処見込み:
- PR #192 (Condition eCS) merge → -1.5pp
- PR #197 (MR eCS 完全対処) merge → -0.4pp (+ sub-issue 修正)
- CareTeam SNOMED 別コード差替 → -0.9pp
- MAR mad-1 対応 (sliding scale 対策) → -0.7pp
- Patient BloodType ext + ja-JP display → -0.14pp
- Composition eDischargeSummary/eReferral 分岐 → -0.13pp
- ICD-10 display walker 補完 (E11/Z23 主) → -0.16pp

上記全対処で fail 率 **~0.3% (残 obs 側 176件 + 小 noise)** 到達見込み。
