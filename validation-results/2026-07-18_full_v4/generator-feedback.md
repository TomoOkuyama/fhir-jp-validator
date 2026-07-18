# 生成者向けフィードバック — 2026-07-18 v4 (session 57 v3→v4 7 chain 後)

対象: clinosim 側 (workspace:1)。次サイクルで clinosim が修正すべき残 issue を優先度順に整理。

## 全体像

- **v3 → v4 で fail 率 4.24% → 2.62% (-1.62pp) 達成**。v2 比では 11.9% → 2.62% で -9.28pp
- 7 chain のうち **Ch1 (CareTeam text-only)、Ch3 (MR identifier)、Ch6 (MAR mad-1)** は完全成功
- Ch2 は Condition の identifier slice を完全解決したが、**code.coding:medisRecordNo slice が同じ 6,242 件で残存**していたため Condition fail 率は 100% 継続
- Ch7 の AI SNOMED 差替は 5 code のうち 2 code が成功、3 code は validator 側の terminology 課題 (下記詳細)

## 最優先 1 — Condition medisRecordNo slice (6,242 件 = 100% fail)

**現象**:
```
Slice 'Condition.code.coding:medisRecordNo': minimum required = 1, but only found 0
(from http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Condition_eCS|1.12.0)
```

**背景**: v3 report で Condition 2 種 slice を提示 (`identifier:resourceIdentifier` と `code.coding:medisRecordNo`)。Ch2 は identifier slice のみ解決したが、code.coding slice は残っている。Chain B の scope 定義に含まれていなかった。

**対処**: `Condition.code.coding[]` に MEDIS 病名基本テーブル slice を追加:
```json
"code": {
  "coding": [
    {"system": "http://hl7.org/fhir/sid/icd-10", "code": "E11", "display": "..."},
    {"system": "urn:oid:1.2.392.200119.4.101.6", "code": "20050030", "display": "..."}
  ]
}
```

**期待効果**: -1.5pp (fail 率 2.62% → ~1.1%)

## 最優先 2 — MedicationRequest 残 sub-issue (1,806 件 = 95.7% fail)

Ch3 で MR identifier count 3 は解決。残る 3 種同時発火:
```
The System URI could not be determined for the code 'd' in ValueSet 'UnitsOfTime'
提供された値（'d'）は ValueSet 'UnitsOfTime' に含まれていません
Dosage.doseAndRate.type: 最小必要値 = 1、見つかった値 = 0
```

**対処**:
- `Dosage.timing.repeat.periodUnit = "d"` 相当の場所で system が付いていない箇所を修正。UnitsOfTime は `http://unitsofmeasure.org` 由来として明示
- `Dosage.doseAndRate` の各要素に `type` を追加:
  ```json
  "type": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/dose-rate-type",
      "code": "ordered",
      "display": "Ordered"
    }]
  }
  ```

**さらに 854 件別途**:
```
courseOfTherapy display 'Continuous long-term therapy' → 'Continuous long term therapy'
```
ハイフン除去のみ

**期待効果**: -0.6pp

## 最優先 3 — Patient ja-JP language display (580 件 = 100% fail)

**現象**:
```
urn:ietf:bcp:47#ja-JP の誤ったdisplay '日本語(日本)' - should be 'Japanese(Japan)' (ja binding)
```

Ch4 で BloodType extension は消えたが、`communication.language.coding[0].display` の `'日本語(日本)'` (JP 表記) が required binding 違反で残っている。

**対処**: display を英語文字列に統一:
```json
"communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": "ja-JP", "display": "Japanese(Japan)"}]}}]
```

**期待効果**: -0.14pp

## 最優先 4 — MAR display 正規化 (route + YJ-code 計 ~1,067 件 = 1.65% fail)

Ch6 で mad-1 完全解決。残る MAR error は全て display mismatch:

- **636 件**: `MAR.dosage.route.coding[system=snomed, code=447694001, display='Inhalation']` — 447694001 の真の default display は `'Respiratory tract route (qualifier)'`。display を空にするか英語正規表記に
- **383 件**: YJ-code `1149037F1020` display `'セレコキシブ（セレコックス）'` (正: `'セレコックス錠１００ｍｇ'`) — 医薬品 display を製剤名に統一
- **48 件**: YJ-code `1169101F1120` display `'レボドパ/カルビドパ（ネオドパストン/メネシット）'` (正: `'ネオドパストン配合錠Ｌ１００'`)

**対処**: 医薬品と route の display を validator が持つ canonical display に統一 (JP display 独自定義を止める)

**期待効果**: -0.4pp

## 中優先 5 — ICD-10 walker 適用範囲拡大 (700 件)

Chain G (v3→v4 で ICD-10 JP display 復活を止める walker) は Condition 側で完全に効いた (実測 Condition の Wrong Display 0 件)。しかし 700 件は **DiagnosticReport / Encounter / MedicationAdministration 等の別 resource** に埋め込まれた ICD-10 code に付いた display から発火:

- E11.9 (448 件): `'Type 2 diabetes mellitus without complications'` → `'Type 2 diabetes mellitus : Without complications'`
- Z23 (211 件): `'Need for immunization'` → `'Need for immunization against single bacterial diseases'`
- F00 (20), J44 (9), T54 (2)

**対処**: walker の適用範囲を「全 resource の全 CodeableConcept.coding[system=http://hl7.org/fhir/sid/icd-10]」に拡大

**期待効果**: -0.16pp

## 中優先 6 — Composition eDS 残 profile 制約 (129 件)

Ch5 で type.coding max=1 は解決。eDS 内部で 7 種の要件が同時発火:
```
Composition.extension:version min=1
Composition.category min=1
Composition.author min=2 (現状 1)
Composition.meta.lastUpdated min=1
Composition.section:structuredSection.section min=10 (現状 5)
section:structuredSection.section:hospitalCourseSection min=1
section:structuredSection.section:detailsOnDischargeSection min=1
```

**対処**: eDS 生成分岐で必須要素を全て埋める。**セクション数を 10 個以上に増やす** (追加すべき slice の一覧は eDS profile snapshot 参照)

**期待効果**: -0.03pp

## 中優先 7 — Composition eReferral display 統一 (302 件 + 151 × 5)

```
section code display '構造情報' vs '構造情報セクション' の両方向誤り (302 件、両者間の一致不整合)
extension:version slice min=1
identifier system 'urn:clinosim:composition-id' → 'http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier'
type.coding.system 'http://loinc.org' → 'http://jpfhir.jp/fhir/Common/CodeSystem/doc-typecodes'
```

**対処**: eReferral 生成分岐でこれらを一括修正

**期待効果**: -0.11pp

## 中優先 8 — AllergyIntolerance SNOMED code 3 件の再選定 (40 件)

Ch7 で 5 code 差替、うち 3 code に validator 側課題:

| 差替後 code | 問題 |
|---|---|
| **115556009 Sulfonamide** | fhirserver の SNOMED International 2026-06-01 に **未収録** → Unknown code |
| **373270004 Substance with penicillin structure** | SNOMED International 2026-06-01 で **INACTIVE (廃止済)** 扱い + display に不整合 |
| **387458008 Aspirin (new)** | SNOMED に存在するが **JP Core AllergyIntolerance ValueSet に未包含** |

**対処案**:
- **JP Core AllergyIntolerance ValueSet に載っている substance code** を確認して再選定
  - Sulfonamide 相当: 別の active code を JP Core VS 内で探す
  - Penicillin: 373270004 (inactive) の後継 active code を SNOMED lookup で確認 (`Substance with penicillin structure and adjacent nitrogen-containing bicyclic ring system` 等)
  - Aspirin: JP Core VS に含まれる code (例えば `387458008` が VS 外なら別 code) を確認
- または **独自 CodeSystem 化** (`http://clinosim.dev/fhir/CodeSystem/allergy-substance` を発行)

**期待効果**: -0.01pp

## 中優先 9 — LOINC unknown code (283 件)

- **45391-8** (148 件)
- **42346-6** (135 件)

**対処**: 使用箇所と source を特定して、有効な LOINC code に置換または削除

## 継続 backlog (次サイクル以降)

- radiology DR profile Common → Radiology 切替 (Issue #218)
- Patient BloodType の代替: Observation LOINC 883-9 emit path 追加 (session 57 wrap-up にも記載あり)
- fhirserver 側 SNOMED International のカバレッジ拡張 (validator 側課題)
- ImagingStudy RadLexPlaybook VS の JP 相当への差替
