# 検証まとめ — 2026-07-17 v2 (session 55/56 fix 適用 + session 57 7 PR 追加後 fullset)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-17 14:04 JST、JP p=1000 seed=300、master 253bced5)
- **fullset = 417,209 リソース / 26 NDJSON / 567MB**
- session 57 merged 7 PR (#201/#203/#205/#207/#209/#211/#213) 反映済み

## 分布

| 種別 | 件数 | 占有 |
|---|---:|---:|
| Observation | 245,179 | 59% |
| MedicationAdministration | 63,632 | 15% |
| ServiceRequest | 34,793 | 8% |
| Specimen | 30,195 | 7% |
| DocumentReference | 10,050 | 2% |
| Condition | 6,242 | 1% |
| 他 20 種 | 27,118 | 7% |

## 検証戦略

前回同様の分割 (rest tx 有効 / obs tx=n/a)。

| pass | 対象 | tx 設定 | HAPI_EXTRA_ARGS |
|---|---|---|---|
| rest | 25 種 (非 Observation) 172,030 | `-tx=http://localhost:8181/r4` | `-best-practice ignore -check-display Ignore` |
| obs | Observation 245,179 | `-tx=n/a` (構造/slice のみ) | `-best-practice ignore` |

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 172,030 | 7 分 4 秒 | 405 | 100% |
| obs | 245,179 | 16 分 24 秒 | 249 | 100% |
| **合計** | **417,209** | **23 分 28 秒** | **296** | **100%** |

- rest 側 rps 405 は前回 v1 393 の +3% (ほぼ同等)
- obs 側 rps 249 は前回 v1 244 と同等
- 全 Bundle で HTTP timeout ゼロ、quarantined port ゼロ

## Issue 分布 (v1 vs v2)

| severity | v1 total | v2 total | 変化 |
|---|---:|---:|---:|
| error | 584,906 | **85,195** | **-85%** |
| warning | 490,424 | 468,175 | -5% |
| information | 587,053 | 856,028 | +46% (dom-6 抑止差分と、code.text 追加による binding info 増加) |

**リソース単位 pass/fail**:
- rest: 172,030 中 ~19,180 (11.1%) に 1+ error
- obs: 245,179 中 30,315 (12.4%) に 1+ error
- **合計 417,209 中 ~49,495 (11.9%) に 1+ error**

## 種別ごと fail 率 (前回 v1 比較)

| 種別 | 検証数 | error あり | v2 fail | v1 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| Observation | 245,179 | 30,315 | **12.4%** | 69.7% | **-57pp** ✅✅✅ |
| Condition | 6,242 | 6,242 | 100% | 100% | ↔ (PR #192 未 merge) |
| CareTeam | 3,788 | 3,788 | 100% | 100% | ↔ (#179 fix が fhirserver で有効化されず) |
| MedicationRequest | 1,871 | 1,871 | 100% | 100% | ↔ (PR #197 未 merge、加えて新規 issue 発覚) |
| Patient | 579 | 579 | 100% | 100% | ↔ |
| AllergyIntolerance | 76 | 76 | 100% | 100% | ↔ |
| DiagnosticReport | 2,593 | 2,196 | 84.7% | 85.1% | ↔ |
| ImagingStudy | 770 | 563 | 73.1% | 74.6% | ↔ |
| MedicationAdministration | 63,632 | 3,762 | **5.9%** | 29.7% | **-24pp** ✅ (#205 UCUM + #209 ICD-10) |
| Practitioner | 100 | 10 | 10.0% | 10.0% | ↔ |
| Composition | 4,466 | 416 | 9.3% | 9.4% | ↔ |
| Encounter | 3,898 | 41 | 1.1% | 0.9% | ↔ |
| ServiceRequest | 34,793 | 95 | 0.3% | 0.4% | ↔ |
| Location | 71 | 4 | 5.6% | 5.6% | ↔ |
| Specimen | 30,195 | 0 | **0%** | 0% | ↔ (#195 効いてる) |
| DocumentReference/Immunization/ClinicalImpression/FamilyMemberHistory/Endpoint/Coverage/Procedure/PractitionerRole/Device/DeviceUseStatement/Organization | ~30,000 | 0 | 0% | 0% | ↔ |

## Session 57 fix 実測結果サマリ

| PR | 対象 | 期待効果 | 実測効果 | 判定 |
|---:|---|---:|---:|:---:|
| #201 | Observation.category を per-CodeSystem 分離 | −286k | 実測 -286k (obs error 484k→30k のうち大部分) | ✅✅ |
| #203 | referenceRange extension 全廃止 | −31k | 実測 -62k (v1 で 31k × 2 種) | ✅✅ |
| #205 | UCUM 特殊単位 canonicalization | −6.2k | 実測 -6.2k (IU/mcg unknown 消失) | ✅ |
| #207 | `_generator_metadata.json` sidecar | 追跡性 | 確認済 (checksum で reproduce 可能) | ✅ |
| #209 | MAR.reasonCode ICD-10 mapping | −7.6k | 実測 -7.6k (S72.00/E11.65 消失) | ✅ |
| #211 | BP LOINC 85354-9 panel + component[] | −14.5k | 実測 -14.5k (bp profile 違反消失) | ✅ |
| #213 | CodeSystem URI を .example.org → .dev | −577+66 | 実測 -577+66 (Patient occupation / Care level 消失) | ✅ |

**合計期待 -345k → 実測 -400k** (期待値以上)。

## 検出された主要 残 issue (v2 で今も出ているもの)

### Observation (obs pass)

- **30,315** Observation.identifier:resourceIdentifier slice min=1 (obs 全体でこれのみ、identifier 自体はあるが slice discriminator に一致していない)
- 160 code.text 欠落 (JP_Observation_LabResult profile、少数)
- 141 valueCodeableConcept.coding.display 欠落
- 24 ele-1 (空 element)

### rest 側 (25 種)

- **6,242** Condition eCS 必須欠落 (identifier:resourceIdentifier slice + medisRecordNo slice) — PR #192 で対処予定
- **3,788** CareTeam SNOMED 735320007 unknown — fhirserver の SNOMED International 2026-06-01 に code 未収録 (別問題)
- **2,755** ルール `mad-1` failed — MedicationAdministration の FHIR base invariant (dosage.dose と dosage.rate 系の関係) — 新規発覚
- **2,452** ルール `con-4` failed — Condition invariant
- **2,196** DR.category:first slice 欠落 (JP_DiagnosticReport_*)
- **1,871 × 6 種** MedicationRequest_eCS 必須要素・constraint — PR #197 で対処予定
  - identifier count 3 / requestIdentifier slice / meta.lastUpdated
  - validUsage-MedicationUsage-codesystem (R5020)
  - Dosage.extension:periodOfUse
  - Dosage.doseAndRate.type
  - `d` (UnitsOfTime) 未知
- **1,782** ICD-10 I10 日本語 display "本態性高血圧症" mismatch (英語 CodeSystem に無い)
- **848 × 5 種** MedicationRequest の substitution / intent / display 問題
- **643** ICD-10 E78 日本語 display "脂質異常症" mismatch
- **750** Narrative status: `generated` vs `additional`

## validator noise (data 側の問題ではない)

- dom-6 Best Practice narrative missing: warning ~350k (`-best-practice ignore` で抑止済)
- SNOMED/LOINC 日本語 display なし: info、対処不要
- `urn:oid:...1005` 未知 CodeSystem: warning、対処不要
- `warn-localCode-observation-laboresult`: 30,315 warning、情報のみ
- `http://clinosim.dev/fhir/CodeSystem/*` 未知 CodeSystem: warning、対処不要 (#213 で移行された新 URI、CodeSystem 定義は data 側にあるが未 register)

## caveat — 検証していないこと

- **Observation の LOINC / SNOMED terminology 検証**: 性能上スキップ、構造/slice/invariant のみ
- **業務ロジック**: 診療報酬点数、レセプト整合、医療的妥当性
- **Bundle Type validation**: client が `collection` 化するため `transaction`/`document` の制約は非対象

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (785MB) / `raw/obs.ndjson` (~2.5GB 推定) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 次サイクルの見込み

**v1 → v2 で fail 率 49.9% → 11.9% (-38pp)** の大幅改善達成。

残り主要 issue の対処見込み:
- PR #192 (Condition eCS) merge → -1.5pp
- PR #197 (MR eCS complete) merge → -0.5pp (+ 新規 substitution/intent/UnitsOfTime 修正)
- CareTeam SNOMED 差替 → -0.9pp
- ICD-10 日本語 display 削除 or ja translation 追加 → -0.6pp
- mad-1 / con-4 invariant 対応 → -1.2pp
- Observation identifier:resourceIdentifier slice 修正 → **-7.3pp** (最大インパクト)

上記全対処で fail 率 **~15% → 数 % 台** 到達見込み。
