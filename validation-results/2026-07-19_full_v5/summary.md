# 検証まとめ — 2026-07-19 v5 (session 58 15 chain merge 後)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-19 16:10 JST、JP p=1000 seed=300 end=2026-06-30、master c2b33dfe)
- **fullset = 417,209 リソース / 28 NDJSON / 627MB**
- session 58 merged 15 PR + Framework Phase 1/3/3-b 反映済み

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 172,030 | 8 分 13 秒 | 349 | 100% |
| obs | 245,179 | 18 分 23 秒 | 222 | 100% |
| **合計** | **417,209** | **26 分 36 秒** | **261** | **100%** |

## Issue 分布 (v4 vs v5)

| severity | v4 total | v5 total | 変化 |
|---|---:|---:|---:|
| error | 21,296 | **5,048** | **-76%** |
| warning | 477,551 | 502,605 | +5% |
| information | 865,120 | 854,559 | ~0% |

**リソース単位 pass/fail** (1+ error あり)
- rest: 172,030 中 2,715 = **1.578%**
- obs: 245,179 中 172 = **0.070%** (v4 176 → -2%)
- **合計 417,209 中 2,887 = 0.692%**

**v4 → v5 で fail 率 2.62% → 0.692% (-1.93pp)**、目標 0.6% にほぼ到達。

## 種別ごと fail 率 (v4 比較)

| 種別 | 検証数 | error あり | v5 fail | v4 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| Observation | 245,179 | 172 | 0.07% | 0.07% | ↔ (Chain 対象外) |
| Condition | 6,242 | 75 | **1.2%** | 100% | **-98.8pp** ✅✅✅ (Ch1) |
| MedicationRequest | 1,871 | 1,790 | **95.7%** | 95.7% | ↔ (Ch2/#236 で修正済 base issue、残 tim-2 が主) |
| MedicationAdministration | 63,632 | 0 | **0%** | 1.65% | **-1.65pp** ✅ (Ch4 完全解決) |
| Patient | 579 | 0 | **0%** | 100% | **-100pp** ✅✅✅ (Ch7) |
| ImagingStudy | 770 | 563 | 73.1% | 74.6% | ↔ (RadLexPlaybook 未対処) |
| Composition | 4,466 | 156 | **3.5%** | 9.4% | -5.9pp ✅ (Ch8/9/10、残 eDS/eReferral 内部) |
| AllergyIntolerance | 76 | 76 | 100% | 100% | ↔ (Ch263 code fix したが identifier slice 別途残) |
| CareTeam | 3,788 | 0 | **0%** | 0% | ↔ ✅ (v4 の text-only 継続) |
| Encounter | 3,898 | 41 | 1.1% | 0.9% | ↔ |
| ServiceRequest | 34,793 | 0 | 0% | 0.4% | -0.4pp ✅ |
| DiagnosticReport | 2,593 | 0 | 0% | 0.5% | -0.5pp ✅ |
| Practitioner | 100 | 10 | 10.0% | 10.0% | ↔ |
| Location | 71 | 4 | 5.6% | 5.6% | ↔ |
| Specimen/DocumentReference/Immunization/ClinicalImpression/FamilyMemberHistory/Endpoint/Coverage/Procedure/PractitionerRole/Device/DeviceUseStatement/Organization | ~85,000 | 0 | 0% | 0% | ↔ |

## Session 58 15 chain 実測結果サマリ

| PR | Chain | 対象 | 期待効果 | 実測効果 | 判定 |
|---:|:---:|---|---:|---|:---:|
| #246 | Ch1 | MEDIS Condition slice (identifier + medisRecordNo) | -6,242 | **0 件** | ✅✅ |
| #248 | Ch2 | MR Dosage doseAndRate + boundsDuration | -5,280 | 0 件 (base 側)、tim-2 副作用 1,748 件発生 | ⚠️ |
| #250 | Ch3 | courseOfTherapy display | -854 | **0 件** | ✅✅ |
| #252 | Ch4 | MAR route SNOMED 447694001 | -667 | **0 件** | ✅✅ |
| #254 | Ch7 | BCP-47 language display | -580 | **0 件** | ✅✅ |
| #260 | Ch6 | ICD-10 WHO sync | -700 | **0 件** (Wrong Display 全消滅) | ✅✅ |
| #262 | Ch8 | Composition section title/display | -302 | **0 件** | ✅✅ |
| #266 | Ch10 | LOINC + Composition.identifier URI | -434 | **0 件** (45391-8/42346-6 + composition URI 共に消滅) | ✅✅ |
| #268 | Ch9 | eDS Composition slice compliance | -~1,806 | 部分 (structuredSection.section 126 件、eDS/eReferral 内部残 24×5 種) | ⚠️ |
| #275 | Ch263 | AI JFAGY primary coding | -40 | **0 件** (SNOMED unknown 消滅) | ✅ (AI identifier slice は別途残 76) |
| #258 | Ph1 | Framework YJ template | drift 防止 | YJ-code display mismatch 0 件 | ✅ |
| #271 | Ph3 | LOINC retired 7 code 置換 | -172 | **0 件** (retired 検出無し) | ✅ |
| #277 | Ph3-b | LOINC display audit + verify_mode=display | drift 防止 | LOINC Wrong Display 0 件 | ✅ |
| #273 | -   | eDS entry refs (Ch9 follow-up) | -~500 | 部分反映、hospitalCourseSection.entry min=1 が 126 件残 | ⚠️ |
| #274 | -   | NEWS2 → clinosim custom nursing-scores | (info 化) | Obs 側 tx=n/a のため直接判定不可 | — |

**期待合計 -17,000+ → 実測 -16,248** (error 21,296→5,048)、期待に -750 差、主に Ch9 の Composition eDS 内部要件の残余分。

## v5 で新たに検出された issue (Chain 副作用 or 発掘)

### 【副作用 1】 tim-2 invariant 失敗 (1,748 件、MedicationRequest 100% fail の主因)

**現象**:
```
ルール tim-2 が失敗しました
expression: MedicationRequest.dosageInstruction[0].timing.repeat
```

**背景**: FHIR R4 の tim-2: `period.exists() implies periodUnit.exists()`。Chain #2 で boundsDuration を追加した際に `timing.repeat.period=1` を書いたが対応する `periodUnit` を含めていない。

**実データ例** (`ORD-ENC-POP-000004-103115176472-ED-T0`):
```json
"repeat": {
  "frequency": 1,
  "period": 1,
  "boundsDuration": {"value": 1, "unit": "日", "system": "http://unitsofmeasure.org", "code": "d"}
}
```

`period=1` があるが `periodUnit` が無い。tim-2 で fail。

**対処**: `periodUnit: "d"` (unitsofmeasure) を追加

### 【副作用 2】 txt-2 invariant 失敗 (630 件、Composition の section 内 narrative)

**現象**:
```
ルール txt-2 が失敗しました
expression: Composition.section[0].section[5].text.div
```

**背景**: FHIR R4 txt-2: `The narrative SHALL have some non-whitespace content` (narrative は非空白 content を必ず含む)。

**実データ例** (`comp-ENC-POP-000065-879335694702-13`):
```json
"section": {"code": "333", "display": "入院中経過セクション"},
"text": {"status": "additional", "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\"></div>"}
```

`div` 中身が空 (`</div>` の前にコンテンツ無し)。

**対処**: 空 section の場合は section.text 全体を出さないか、`div` 内に最低限のテキスト (title 相当) を入れる

## v5 で残る主要 issue (対処要否)

### rest 側 top 頻度

| # | 内容 | 対応方針 |
|---:|---|---|
| **1,748** | MR tim-2 (period に periodUnit 欠落) | Chain #2 の生成分岐で periodUnit を追加 |
| **630** | Composition txt-2 (section.text.div 空) | 空 section は text を出さない or 最低限テキスト挿入 |
| **499** | ImagingStudy RadLexPlaybook VS 非包含 | RadLex 収録 or JP 用差替 (session 57 backlog) |
| **250 (44+44+41+35+31+26+多数)** | YJ-code 各 code (2254001F1102/2149032F1013/3112001F1055/etc.) が JP_MedicationCodeYJ_VS 未包含 | YJ_VS の code 一覧確認 → clinosim 使用 code を VS 内に絞る、または独自 CS 使用 |
| **126×3** | Composition eDS internal (hospitalCourseSection.entry min=1 + doc-subtypecodes display '退院時サマリー' vs '退院時文書' + VS non-inclusion) | Ch9 の生成分岐残余、doc-subtypecodes display を '退院時文書' に |
| **76×3** | AllergyIntolerance identifier + resourceIdentifier slice + JFAGY related | AI eCS 対応 (session 57 の Ch2 に相当する対処) |
| **75** | Condition 系少数残 (medisRecordNo で対応漏れ or 別 slice) | 個別確認 |
| **64** | ICD-10 I84 code in "2019-covid-expanded" version 未知 | I84 は結核関連。covid-expanded 版に含まれず。使用時に base ICD-10 に切替 |
| **26** | MR.medication[x].coding min=1 (JP_MedicationRequest_eCS) | medicationCodeableConcept に coding を必ず含める |
| **24×5** | Composition eReferral: extension:version / category / author≥2 / meta.lastUpdated 各種 | eReferral 生成分岐強化 (eDS と同様) |

### obs 側 (172 件、v4 とほぼ同じ)

| # | 内容 |
|---:|---|
| 160 | Observation.code.text 欠落 (JP_Observation_LabResult) |
| 141 | value.coding.display 欠落 (qualitative) |
| 24 | ele-1 (空要素) |
| 12 × 2 | referenceRange units invariant |

## Session 58 特筆すべき成果

- **15 chain のうち 12 chain が期待通り完全解決** (Ch1/3/4/6/7/8/10/Ph1/Ph3/Ph3-b/Ch263 + Ch2 の base 部分)
- **v3→v4→v5 で 3 サイクル連続大幅改善**: fail 率 11.9% → 4.24% → 2.62% → 0.692% (v2 比 -94%)
- **Framework 導入** (Phase 1/3/3-b) で今後の drift 検知が可能に

## caveat — 検証していないこと

- **Observation の LOINC / SNOMED terminology 検証**: 性能上スキップ、構造/slice/invariant のみ
- **業務ロジック**: 診療報酬点数、レセプト整合、医療的妥当性
- **Bundle Type validation**: client が `collection` 化するため `transaction`/`document` の制約は非対象

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~750MB) / `raw/obs.ndjson` (~1.1GB) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 次サイクルの見込み

**v4 → v5 で fail 率 2.62% → 0.692% (-1.93pp)** 達成、v2 比 -11.2pp (11.9% → 0.692%)。

残 error 5,048 の内訳と対処見込み:
- tim-2 (1,748): -0.42pp (Chain #2 生成分岐に periodUnit 追加)
- txt-2 (630): -0.15pp
- RadLexPlaybook (499): -0.12pp
- YJ-code VS binding (250): -0.06pp
- Composition eDS/eReferral 内部 (126+120): -0.06pp
- AI identifier slice (76): -0.02pp
- MR.medication[x].coding (26): -0.006pp
- ICD-10 I84 (64): -0.015pp

上記全対処で fail 率 **~0.1% (obs 172 件 + 小残 300 件相当)** 到達見込み、実質完全準拠に到達。
