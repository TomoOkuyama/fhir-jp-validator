# 検証まとめ — 2026-07-18 v4 (session 57 v3→v4 7 追加 chain merge 後)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-18 21:29 JST、JP p=1000 seed=300、master fd5c352b)
- **fullset = 424,395 リソース / 28 NDJSON**
- session 57 追加 merged 7 chain (#232/#234/#236/#238/#240/#242/#244) 反映済み

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 175,413 | 5 分 59 秒 | 489 | 100% |
| obs | 248,982 | 15 分 45 秒 | 263 | 100% |
| **合計** | **424,395** | **21 分 44 秒** | **326** | **100%** |

## Issue 分布 (v3 vs v4)

| severity | v3 total | v4 total | 変化 |
|---|---:|---:|---:|
| error | 38,835 | **21,296** | **-45%** |
| warning | 477,616 | 477,551 | ~0% |
| information | 868,628 | 865,120 | ~0% |

**リソース単位 pass/fail** (1+ error あり)
- rest: 175,413 中 10,954 = **6.245%**
- obs: 248,982 中 176 = **0.071%** (v3 と同一、Chain は Obs 対象外)
- **合計 424,395 中 11,130 = 2.62%**

**v3 → v4 で fail 率 4.24% → 2.62% (-1.62pp)**。期待 -3.4pp との差 -1.78pp は主に Condition の medisRecordNo slice が Chain B の scope 外だったため (下記)。

## 種別ごと fail 率 (v3 比較)

| 種別 | 検証数 | error あり | v4 fail | v3 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| Condition | 6,242 | 6,242 | 100% | 100% | ↔ (Ch2 が identifier slice のみ、medisRecordNo slice は残る) |
| MedicationRequest | 1,887 | 1,806 | **95.7%** | 100% | -4.3pp (Ch3 で identifier slice 解決、残 sub-issue のみ) |
| MedicationAdministration | 64,510 | 1,067 | **1.65%** | 6.3% | **-4.65pp** ✅ (Ch6 mad-1 完全解決、残は display noise) |
| Patient | 580 | 580 | 100% | 100% | ↔ (Ch4 で BloodType 解消したが ja-JP display が残存) |
| ImagingStudy | 760 | 567 | 74.6% | 74.6% | ↔ (RadLexPlaybook VS、既存) |
| Composition | 4,474 | 422 | 9.4% | 9.4% | ↔ (Ch5 は type.coding max のみ解決、eDS 内他要件残る) |
| ServiceRequest | 35,922 | 133 | 0.4% | 0.3% | ↔ |
| AllergyIntolerance | 75 | 75 | 100% | 100% | ↔ (Ch7 で 5 code 差替済だが 3 code に validator 側課題、下記) |
| CareTeam | 3,786 | **0** | **0%** | 100% | **-100pp** ✅✅✅ (Ch1 text-only 完全成功) |
| Encounter | 3,898 | 36 | 0.9% | 0.9% | ↔ |
| DiagnosticReport | 2,286 | 12 | 0.5% | 0.5% | ↔ |
| Practitioner | 100 | 10 | 10.0% | 10.0% | ↔ |
| Location | 71 | 4 | 5.6% | 5.6% | ↔ |
| Specimen/DocumentReference/Immunization/ClinicalImpression/FamilyMemberHistory/Endpoint/Coverage/Procedure/PractitionerRole/Device/DeviceUseStatement/Organization | ~90,000 | 0 | 0% | 0% | ↔ |

## Session 57 v3→v4 chain 実測結果サマリ

| PR | 対象 | 期待効果 | 実測効果 | 判定 |
|---:|---|---:|---|:---:|
| #232 (Ch1) | CareTeam.category text-only | -3,786 | **実測 -3,786 (0 件)** | ✅✅ |
| #234 (Ch2) | Condition/AI eCS identifier:resourceIdentifier slice | -6,242 相当 | 実測 Cond identifier slice 0 件 ✅ + AI identifier slice 0 件 ✅ (**medisRecordNo slice 6,242 は Ch2 の scope 外で残る**) | ⚠️ |
| #236 (Ch3) | JP MR eCS identifier count=3 + requestIdentifier | -3,742 | 実測 -3,742 (0 件)、MR fail 100%→95.7% (残 sub-issue のみ) | ✅✅ |
| #238 (Ch4) | Patient BloodType 捏造 URL 削除 | -580 | 実測 BloodType URL 0 件 ✅ (Patient は ja-JP display 580 件で 100% fail 継続) | ⚠️ |
| #240 (Ch5) | Composition eDS/eReferral type.coding max=1 + section 300 display | -129 | 実測 type.coding max 0 件 ✅ (残 eDS 内部要件と section '構造情報' 302 件は別) | ⚠️ |
| #242 (Ch6) | MAR mad-1 対応: dose/rate 不在 dosage を drop | -3,005 | **実測 -3,005 (0 件)、MAR fail 6.3%→1.65%** | ✅✅ |
| #244 (Ch7) | AI SNOMED 5 code 差替 | -75 | 実測 2 code (271807003, 61582004) ✅、3 code (115556009, 373270004, 387458008) に validator 側課題 (下記) | ⚠️ |

**期待合計 -17,559 → 実測 -17,539** (期待通り件数減、ただし Condition と Patient は他要因で 100% fail 継続)。

## 特に確認したい 5 項目の回答

1. 【Ch1】**CareTeam 3,786 件 → 0** ✅ (text-only CodeableConcept で validator 通過。fhirserver の SNOMED カバレッジ問題を回避)
2. 【Ch2】**Condition 6,242 件 identifier slice → 0** ✅ (resourceInstance-identifier URI 反映)、ただし **code.coding:medisRecordNo slice が別途 6,242 件残存** — この slice は Ch2 scope 外だったため。Condition の fail 率は 100% 継続
3. 【Ch3】**MR eCS identifier count 3 到達 → 0** ✅ (rpNumber + orderInRp + requestIdentifier の 3 slice 認識)、MR fail 100%→95.7%
4. 【Ch6】**MAR mad-1 3,005 件 → 0** ✅ (dosage element ごと drop で spec-compliant)、MAR fail 6.3%→1.65%
5. 【Ch7】**AI SNOMED 5 code 差替**:
   - **271807003 Eruption of skin** ✅ validator 通過
   - **61582004 Allergic rhinitis** ✅ validator 通過
   - **373270004 Substance with penicillin structure** ❌ **INACTIVE (deprecated) 扱い + display mismatch** (正: `'Substance with penicillin structure and ...'` のように後方継続がある) — 12 件
   - **387458008 Aspirin (new)** ❌ SNOMED には存在するが **JP Core AllergyIntolerance ValueSet に未包含** — 12 件
   - **115556009 Sulfonamide** ❌ **fhirserver の SNOMED International 2026-06-01 に未収録** — 16 件
   合計 40 件は上記 3 code 由来。AllergyIntolerance 75 件のうち残る 35 件は `Rash` (`Wrong Display Name 'Rash' for #247472004`) 等 (Ch7 が変換対象外の code) と identifier slice (今回 0 に減少) 以外の少数 issue。要 code 選定の再検討

## v3 から明示的に確認した ICD-10 walker 状態

- **rest 全体で `Wrong Display Name.*icd-10` = 700 件**、v3 と同数
- v3 report で提示した E11.9 (458), Z23 (211), F00 (20), J44 (9), T54 (2) の分布と一致
- Chain G は Condition の ICD-10 display 復活を止める walker で、対象は Condition 側だった (実測 Condition の Wrong Display Name は 0 件)
- 残 700 件は **DiagnosticReport / Encounter / MedicationAdministration 等の別 resource** に埋め込まれた ICD-10 code に付いた display から発火。次サイクルで walker の適用範囲拡大が必要

## v4 で残る主要 issue (対処要否)

### rest 側の error text 頻度 (top 15)

| # | 内容 | 対応方針 |
|---:|---|---|
| **6,242** | Condition.code.coding:medisRecordNo slice missing | Ch2 に続く Chain。medisRecordNo slice の追加 |
| **1,760 × 3** | MR eCS: UnitsOfTime 'd' system 未特定 + Dosage.doseAndRate.type 欠落 + `'d'` binding 違反 (実質同一 root) | `duration_unit` の code に `http://unitsofmeasure.org` system 付与、`doseAndRate.type` を dose-rate-type CodeSystem から設定 |
| **854** | MR courseOfTherapy display `'Continuous long-term therapy'` → `'Continuous long term therapy'` (ハイフン無) | 表記正規化 |
| **667** | MAR route display `'Inhalation'` for SNOMED 447694001 (真の default display は `'Respiratory tract route (qualifier)'`) | SNOMED 447694001 の display 削除 (SNOMED は display フィールドを付けない or 英語 default に統一) |
| **580** | Patient ja-JP language display `'日本語(日本)'` (正: `'Japanese(Japan)'` in ja binding) | `communication.language.coding.display` を英語文字列に |
| **448** | ICD-10 E11.9 display `'Type 2 diabetes mellitus without complications'` (正: `'Type 2 diabetes mellitus : Without complications'` コロン区切り) | walker で正規化 (Condition 以外の resource に適用) |
| **389** | YJ-code 1149037F1020 display `'セレコキシブ（セレコックス）'` (正: `'セレコックス錠１００ｍｇ'`) | 医薬品 display を製剤名に正規化 |
| **302** | Composition section '構造情報' display 不一致 (`'構造情報'` vs `'構造情報セクション'` の両方向誤り、eReferral のみ) | eReferral 固有の section code display に統一 |
| **223** | ImagingStudy RadLexPlaybook VS 非包含 | RadLex code 収録 or JP 用差替 |
| **211** | ICD-10 Z23 display 不一致 | 同上 walker 拡大 |
| **151 × 5** | Composition eReferral profile 制約 (extension:version, id system URL, doc-typecodes CS URL, section display) | eReferral 生成分岐修正 |
| **148/135** | LOINC 未知 code `45391-8`, `42346-6` | 使用箇所と data source 確認 |
| **129 × 7** | Composition eDS 内部要件 (extension:version, category, author≥2, meta.lastUpdated, type.coding max, section.section≥10, hospitalCourseSection slice) | eDS 生成分岐強化 |

### obs 側 (176 件、v3 と同一)

| # | 内容 |
|---:|---|
| 166 | Observation.code.text 欠落 |
| 147 | value.coding.display 欠落 |
| 20 | ele-1 空要素 |
| 10 × 2 | referenceRange units invariant |

## caveat — 検証していないこと

- **Observation の LOINC / SNOMED terminology 検証**: 性能上スキップ、構造/slice/invariant のみ
- **業務ロジック**: 診療報酬点数、レセプト整合、医療的妥当性
- **Bundle Type validation**: client が `collection` 化するため `transaction`/`document` の制約は非対象

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~800MB) / `raw/obs.ndjson` (~1.1GB) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 次サイクルの見込み

**v3 → v4 で fail 率 4.24% → 2.62% (-1.62pp)** 達成、v2 比 -9.28pp。

残り主要 issue の対処見込み:
- Condition medisRecordNo slice → -1.5pp (Cond fail 100% → 0%)
- MR eCS 残 UnitsOfTime + doseAndRate.type + courseOfTherapy display → -0.6pp
- Patient ja-JP display → -0.14pp
- MAR route/YJ display 正規化 → -0.4pp
- ICD-10 walker 適用範囲拡大 (Condition 以外) → -0.16pp
- Composition eDS/eReferral 分岐修正 → -0.14pp
- ImagingStudy RadLex → -0.05pp
- AI SNOMED 3 code 差替再検討 → -0.01pp

上記全対処で fail 率 **~0.2% (obs 176 + rest 少量 noise 程度)** 到達見込み。
