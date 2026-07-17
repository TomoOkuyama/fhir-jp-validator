# 生成者向けフィードバック — 2026-07-18 v3 (session 57 8 chain 後)

対象: clinosim 側 (workspace:1)。次サイクルで clinosim が修正すべき残 issue を優先度順に整理。

## 全体像

- **v2 → v3 で fail 率 11.9% → 4.24% (-7.66pp) 達成**。session 57 の 8 chain のうち #217/#220/#226/#228/#230 は完全解決、#215 追跡性 OK、#222 walker 部分成功、#224 SNOMED 差替は validator 側 terminology の穴で無効化。
- 残る error の 76% は既 issue (PR #192 未 merge の Condition eCS + PR #197 未 merge の MR eCS 残 sub-issue)。
- 新規診断済: **MAR mad-1** は base FHIR mad-1 (dose/rate 必須) が真因、statusReason は無関係。

## 最優先 1 — Condition eCS 必須 slice (6,242 件 = 100% fail)

**現象**: 全 Condition で 2 種のエラー同時発火

```
Slice 'Condition.identifier:resourceIdentifier': minimum required = 1, but only found 0
Slice 'Condition.code.coding:medisRecordNo': minimum required = 1, but only found 0
```

**対処**: **PR #192** の merge を先行。追加の生成側修正:
- `Condition.identifier` に `system=urn:oid:1.2.392.100495.20.3.61.1` 相当 (`http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier`) + value を持つ 1 entry を追加
- `Condition.code.coding[medisRecordNo]` slice に MEDIS 病名基本テーブル コード (`urn:oid:1.2.392.200119.4.101.6` 等) を追加

**期待効果**: -1.5pp (fail 率 4.24% → ~2.7%)

## 最優先 2 — CareTeam SNOMED 407484005 が validator 側 SNOMED に不在 (3,786 件 = 100% fail)

**現象**:
```
Unknown code '407484005' in the CodeSystem 'http://snomed.info/sct'
version 'http://snomed.info/sct/900000000000207008/version/20260601' (International Edition)
```

fhirserver がロードしている SNOMED CT International 2026-06-01 に 407484005 (Rehabilitation care team) は **含まれていない**。#224 で差替えた新コードも認識されない。

**対処案 (どれか 1)**:
1. **JP Core が指定する CareTeam.category の推奨 code** に差替 (JP Core CareTeam ValueSet を確認)。実務上 JP 環境で使う SNOMED subset に載っている code を使う
2. **独自 CodeSystem 化**: `http://clinosim.dev/fhir/CodeSystem/care-team-category` 等の独自 CS を発行し、display を明示。unknown-code エラーは消え warning に落ちる
3. **CareTeam.category を無くす** (0..* なので必須ではない): この場合他の識別手段で分類

**期待効果**: -0.9pp (fail 率 → ~1.8%)

## 最優先 3 — MedicationRequest_eCS 残 sub-issue (1,887 件 = 100% fail、各種)

**現象** (各 1,887 件、ほぼ同時発火):
```
MedicationRequest.identifier: 最小必要値 = 3、見つかった値 = 2
Slice 'MedicationRequest.identifier:requestIdentifier': minimum required = 1
Dosage.doseAndRate.type: 最小必要値 = 1
The System URI could not be determined for the code 'd' in ValueSet 'UnitsOfTime'
```

追加 (854 件):
```
Wrong display 'Continuous long-term therapy' - should be 'Continuous long term therapy'
```

**対処**: **PR #197** の merge を推進。生成側追加:
- `identifier` を 3 個以上に (最低: `resourceIdentifier` + `rpNumber` + `requestIdentifier`)
- `identifier:requestIdentifier` slice を追加
- `Dosage.doseAndRate.type` に `http://terminology.hl7.org/CodeSystem/dose-rate-type#calculated` 相当を追加
- UnitsOfTime `'d'` (期間の日) は `http://unitsofmeasure.org` の `'d'` として system を明示
- `courseOfTherapy` の display はハイフン無し正規表記に

**期待効果**: -0.5pp

## 最優先 4 — MedicationAdministration mad-1 真因判明 (3,005 件 = MAR の 4.7%)

**v2 feedback の diagnosis 誤り訂正**:
- 前回「statusReason 起因」と診断したが、**実データで statusReason は emit されていない**。
- 真因は **FHIR R4 base の mad-1**:
  ```
  MedicationAdministration.dosage:
    dose.exists() or rate.exists()
  ```
- 失敗ケース (`mar-ENC-POP-000051-598525354050-00018` 等) の `dosage`:
  ```json
  {"text": "Sliding scale insulin", "route": {"coding": [...]}, ...}
  ```
  → dose も rate も無い。text と route だけ。

**背景**: Sliding scale insulin (血糖値に応じ可変投与)、PRN (頓服)、輸液の間欠 bolus 等、臨床上「単一 dose を明記できない」ケースで発火。

**対処案 (どれか 1)**:
1. **dose を必ず埋める**: 典型量を dose.value に入れ、text で "sliding scale" と注釈。臨床精度は下がるが FHIR 準拠
2. **rateQuantity or rateRatio を使う**: 血糖依存でも標準的な rate を推定して入れる
3. **dosage 自体を出さない**: mad-1 は `MedicationAdministration.dosage` レベルの invariant なので、dosage 要素ごと空にすれば発火しない。text/route を別 element に移す (JP Core が許すなら)
4. **dosage を配列複数化して 1 個は dose 有**: mad-1 は各 dosage element ごとに評価される可能性あり (要確認)

**期待効果**: -0.7pp (fail 率 → ~3.5%)

## 中優先 5 — Patient BloodType extension URL 不明 + ja-JP language display (580 件 = 100% fail)

**現象**:
```
extension http://jpfhir.jp/fhir/core/Extension/StructureDefinition/JP_Patient_BloodTypeCode は未知
urn:ietf:bcp:47#ja-JP の誤ったdisplay '日本語(日本)' - should be 'Japanese(Japan)'
```

**対処**:
- BloodType extension URL を JP Core の正規 canonical URL に修正、または削除
- `communication.language.coding[system=urn:ietf:bcp:47, code=ja-JP]` の display を英語 "Japanese(Japan)" (ja binding required)

**期待効果**: -0.14pp

## 中優先 6 — ICD-10 display 残 700 件 (walker #222 の抜け)

E11 (458 件): `'Type 2 diabetes mellitus without complications'` → `'Type 2 diabetes mellitus : Without complications'` (コロン + スペース区切り)
Z23 (211 件): `'Need for immunization'` → `'Need for immunization against single bacterial diseases'`
その他: F00 (20), J44 (9), T54 (2)

**対処**: walker が特定 code の display 正規化を漏らしている。ICD-10 4 桁コード (E11, Z23 等) の base display の英語版を validator が持つ正規 display に合わせる (JP display を削って英語 display をそのまま使うのが確実)

**期待効果**: -0.16pp

## 中優先 7 — Composition eDischargeSummary / eReferral profile 制約 (計 ~410 件)

eDischargeSummary (129 件、各種):
```
Composition.extension:version min=1
Composition.category min=1
Composition.author min=2  (v3 は 1 のみ)
Composition.meta.lastUpdated min=1
Composition.type.coding max=1  (v3 は 2)
Composition.section:structuredSection.section min=10  (v3 は 5)
```

eReferral (151 件):
```
Composition.extension:version slice min=1
identifier system SHALL be 'http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier'
type.coding.system SHALL be 'http://jpfhir.jp/fhir/Common/CodeSystem/doc-typecodes'
section.code display: '構造情報セクション' → '構造情報'
```

**対処**: Composition の profile 別生成分岐を強化。eDS/eReferral 固有の必須要素を profile 差分に沿って埋める

**期待効果**: -0.13pp

## 中優先 8 — AllergyIntolerance の SNOMED code 誤選択 (75 件 = 100% fail)

75 全件で identifier slice 欠落は共通だが、それとは別に **SNOMED code の割当ミス** が多発:

| clinosim が使ってる code | 検証時 display | 実際の SNOMED display |
|---|---|---|
| 247472004 | "Rash" | 実際は **Weal** (蕁麻疹) |
| 21719001 | "Allergic rhinitis" | 実際は **Pollinosis** (花粉症) |
| 372687004 | "Aspirin" | 実際は **Amoxicillin (substance)** |
| 387207008 | "Penicillin" | 実際は **Ibuprofen (substance)** |
| 303408005 | (未知) | validator 側 SNOMED に不在 |

**対処**: clinosim の allergy substance 辞書で SNOMED code と display の対応を **JP Core AllergyIntolerance ValueSet** に載っている正規の組合せに置換。Rash なら 271807003、Aspirin なら 387458008、Penicillin なら 373270004 等

**期待効果**: -0.02pp (少数)

## 低優先 9 — ImagingStudy RadLexPlaybook (223 件)

`http://playbook.radlex.org/playbook/SearchRadlexAction|1.0.0` ValueSet の code が不在。JP 用の radiology procedure code に差替か、RadLex Playbook データを terminology 側で拡充

## 累計期待効果

上記 1-7 の対処で **fail 率 4.24% → 0.6% 程度** への到達見込み。obs 側は既に 0.07% でほぼ完璧、rest 側の残 issue が主戦場。

## 継続 backlog

- radiology DR profile 切替 (#218 起票済)
- fhirserver 側 SNOMED International のカバレッジ拡張 (validator 側課題、CareTeam / AllergyIntolerance の code 選択を制約)
- Patient extension URL の JP Core 準拠正規化
- mad-1 対策 (sliding scale insulin の dosage 表現方針決定)
