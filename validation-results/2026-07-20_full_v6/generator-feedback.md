# 生成者向けフィードバック — 2026-07-20 v6 (session 59 14 chain merge 後)

対象: clinosim 側 (workspace:1)。次サイクルで clinosim が対応すべき事項を優先度順に整理。

## ⚠️ 総評

- **予想と真逆の結果**: v5 0.692% → v6 3.554% (+2.86pp regression)、error 5,048 → 15,148 (+200%)
- **主因**: Chain #292 / #301 の NOCODED fallback 実装ミスで **12,891 件の display mismatch** が発生 (総 error の 73%)
- **副因**: Chain #282 (tim-2 periodUnit) が tim-2 は解決したが UnitsOfTime binding で validator が 3,532 件で fail (21%)
- **良好**: Composition/Condition/AI/Encounter/Practitioner は Chain 通り 0 件到達、v5 の残 issue の多くが解消済み

## 【最優先 1 - CRITICAL】NOCODED display 実装ミス (12,891 件)

### 現象

```
http://jpfhir.jp/fhir/eCS/CodeSystem/MedicationCodeNocoded_CS#NOCODED の誤ったdisplay
'カルベジロール 2.5mg' - 1 の選択肢のうちの一つであるべきです: '標準コードなし' (言語 'ja' のため)
```

上位 display 種類 (各エラー件数):
- `カルベジロール 2.5mg`: 2,303 件
- `ビタミンD 1000IU`: 2,170 件
- `ランソプラゾール 15mg`: 2,026 件
- `チオトロピウム 18mcg 吸入薬`: 1,274 件
- `サルブタモール 100mcg 吸入薬 頓用`: 1,274 件
- `アレンドロネート 35mg`: 1,053 件
- `アンピシリン/スルバクタム`: 836 件
- `スライディングスケールインスリン`: 487 件
- `晶質液 30 mL/kg ボーラス 以内 3 時間`: 319 件
- `サルブタモール 吸入薬 頓用`: 300 件
- 他多数、合計 12,891 件

### 背景

`MedicationCodeNocoded_CS` CodeSystem は **`NOCODED` 1 code のみ定義**、`display` は **`'標準コードなし'`** の 1 通りに固定 (required binding、valid display list = 1 個)。

### clinosim v6 の誤実装 (推測)

```json
"medicationCodeableConcept": {
  "coding": [{
    "system": "http://jpfhir.jp/fhir/eCS/CodeSystem/MedicationCodeNocoded_CS",
    "code": "NOCODED",
    "display": "カルベジロール 2.5mg"  // ← 薬剤名を display に埋め込み。禁止
  }]
}
```

### 正しい実装

```json
"medicationCodeableConcept": {
  "coding": [{
    "system": "http://jpfhir.jp/fhir/eCS/CodeSystem/MedicationCodeNocoded_CS",
    "code": "NOCODED",
    "display": "標準コードなし"  // ← 固定
  }],
  "text": "カルベジロール 2.5mg"  // ← 薬剤名は CodeableConcept.text に
}
```

### 影響範囲

- **MedicationAdministration**: 64,821 中 12,565 (19.4%) に発火
- **MedicationRequest**: 一部
- Chain #292 (NOCODED for MR) と Chain #301 (YJ nocoded fallback) の両方が同じ実装パターンで悪化

### 対処

`clinosim` の NOCODED coding 生成箇所を全て:
1. `coding.display` を `"標準コードなし"` に固定
2. 薬剤名は `CodeableConcept.text` に移動
3. `MedicationRequest.medicationCodeableConcept` と `MedicationAdministration.medicationCodeableConcept` の両方に適用

### 期待効果

**-3.0pp (fail 率 3.554% → ~0.55%)** — v5 水準に回復

## 【最優先 2】 UnitsOfTime 'd' binding (3,532 件)

### 現象

```
The System URI could not be determined for the code 'd' in the ValueSet 'UnitsOfTime'
提供された値（'d'）は ValueSet 'UnitsOfTime' に含まれていません
```

Chain #282 で `periodUnit: "d"` を追加、tim-2 は解決 (実測 0 件) だが `code` 型の binding 検証で HAPI validator が system URI を決定できず fail。

### v6 の timing.repeat 実データ

```json
"repeat": {
  "frequency": 1,
  "period": 1,
  "periodUnit": "d",
  "boundsDuration": {"value":1,"unit":"日","system":"http://unitsofmeasure.org","code":"d"}
}
```

`period` + `periodUnit` が両方あるため、**両方を削除し boundsDuration のみに** すればどちらの検証も走らず綺麗になる:

```json
"repeat": {
  "frequency": 1,
  "boundsDuration": {"value":1,"unit":"日","system":"http://unitsofmeasure.org","code":"d"}
}
```

### 対処案

**推奨**: `period` + `periodUnit` を削除し `boundsDuration` のみを使う (session 58 Chain #2 の元の狙いに戻す)

### 期待効果

**-0.83pp (fail 率 → ~0.55% 到達後さらに -0.83pp)**

## 【中優先 3】ImagingStudy RadLexPlaybook (571 件、Chain #302 効果なし)

Chain #302 (JP radiology DR _Radiology profile) を反映したはずだが、実測で 571 件残 (v5 499 と同水準)。

**要確認**: #302 の適用範囲が想定通りか、それとも別 profile 経由で ImagingStudy 側に及んでいないか

## 【中優先 4】eReferral 残 issue (66 件)

Chain #297 (referralFrom/to Organizations sweep) の反映漏れ:
- `referralFromSection.entry:referralFromOrganization` slice 22 件
- `referralToSection.entry:referralToOrganization` slice 22 件
- eReferral type.coding display `他医療機関紹介` → `診療情報提供書発行` の 22 件

### 対処

Chain #297 の生成分岐で referralFromSection と referralToSection の entry Organization slice を必ず埋める + type.coding display を正規化

## 【中優先 5】MAR SNOMED 37161004 Sublingual display (13 件)

Chain #252 (route SNOMED display 正規化) の対象外だった `37161004 Sublingual` (真の default display は `Per rectum`)。

### 対処

MAR.route.coding の SNOMED code の default display walker に 37161004 を追加、または display を出さない

## 【中優先 6】Composition Provenance event.code 構造誤り (15 件)

**現象**:
```
プロパティcode は JSON 配列でなければならず、an Object ではありません
```

Provenance/Composition の `event.code` field が `Object` 型で出力されているが `Array` が期待される。

### 対処

`event.code` を `[{coding: [...]}]` 形式 (Array of CodeableConcept) に修正

## 【問題無し】完全解決した項目

Chain #280 (eDS category display)、#285 (ICD-10 swap)、#288 (eDS txt-2 修正)、#290 (eReferral extension:version)、#295 (eDS hospitalCourseSection.entry)、#300 (5 residual sweep)、#303 (LOINC 17 semantic-mismatch): **全て実測 0 件で完全解決** ✅✅

Ch294 で AllergyIntolerance も 100% fail → 0% fail に到達。

## 修正後の見込み

**最優先 1 (NOCODED display) 修正のみで**:
- error 15,148 → 2,257 (**-85%**)
- fail 率 3.554% → **~0.55%** (v5 とほぼ同水準に回復)

**最優先 1 + 2 (UnitsOfTime boundsDuration 化) で**:
- error → **~700**
- fail 率 → **~0.2%**

**上記 + 中優先 3-6 全対処で**:
- error → **~200**
- fail 率 → **~0.1%** (実質完全準拠に到達)

## Session 59 の教訓

- **Chain #292 / #301 は生成側実装ミス**: NOCODED fallback で display を固定値 `'標準コードなし'` にすべきところを薬剤名で埋めた
- **Chain #282 は要件充足だが validator 副作用が残る**: period+periodUnit の代替として boundsDuration only への移行が望ましい
- **多くの Chain は期待通り機能**: Composition/Condition/AI/Encounter は劇的改善
