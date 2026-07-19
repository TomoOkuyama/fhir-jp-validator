# 生成者向けフィードバック — 2026-07-19 v5 (session 58 15 chain 後)

対象: clinosim 側 (workspace:1)。次サイクル (session 59) で clinosim が修正すべき残 issue を優先度順に整理。

## 全体像

- **v4 → v5 で fail 率 2.62% → 0.692% (-1.93pp) 達成**。v2 比 -11.2pp。error 総数 21k → 5k (-76%)
- 15 chain のうち 12 chain が期待通り完全解決 (Ch1/Ch3-Ch4/Ch6-Ch8/Ch10/Ph1/Ph3/Ph3-b/Ch263 + Ch2 base)
- Ch2 と Ch9 に副作用 or 部分効果あり → 下記詳細

## 最優先 1 — MR tim-2 副作用 (1,748 件、MR fail の 100% を占める)

**Chain #2 (#248 MR Dosage doseAndRate + boundsDuration) の副作用**。

**現象**:
```
ルール tim-2 が失敗しました
expression: MedicationRequest.dosageInstruction[0].timing.repeat
```

FHIR R4 tim-2 invariant: `repeat.period.exists() implies repeat.periodUnit.exists()`

**実データ例** (`ORD-ENC-POP-000004-103115176472-ED-T0`):
```json
"timing": {
  "repeat": {
    "frequency": 1,
    "period": 1,
    "boundsDuration": {"value":1,"unit":"日","system":"http://unitsofmeasure.org","code":"d"}
  }
}
```

`period=1` はあるが対応する `periodUnit` が無い → tim-2 fail。Chain #2 で boundsDuration を追加した際、既存の `period` に periodUnit を付ける対応が漏れた。

**対処**: Chain #2 の生成分岐で `period` を書く時に `periodUnit` (通常 `"d"` UnitsOfTime) を必ず含める:
```json
"repeat": {
  "frequency": 1,
  "period": 1,
  "periodUnit": "d",  // ← 追加
  "boundsDuration": {"value":1,"unit":"日","system":"http://unitsofmeasure.org","code":"d"}
}
```

**期待効果**: -0.42pp (MR fail 95.7% → 数 %)

## 最優先 2 — Composition txt-2 (630 件)

**現象**:
```
ルール txt-2 が失敗しました
expression: Composition.section[0].section[5].text.div
```

FHIR R4 txt-2 invariant: `The narrative SHALL have some non-whitespace content` (narrative は非空白 content 必須)

**実データ例** (`comp-ENC-POP-000065-879335694702-13`):
```json
"section": {"code":"333","display":"入院中経過セクション"},
"text": {"status":"additional","div":"<div xmlns=\"http://www.w3.org/1999/xhtml\"></div>"}
```

`div` 内が空 (`></div>` に何も無い)。

**対処案 (どちらか)**:
1. **空 section では text を出さない**: `text` field を無くす (0..1 なので削除で OK)
2. **最低限のテキストを入れる**: `<div>title 相当や"該当記録なし"を挿入</div>`

**期待効果**: -0.15pp

## 最優先 3 — Composition eDS/eReferral 内部要件 (計 ~250 件、Chain #9 部分反映)

Chain #9 (#268 eDS Composition slice compliance) は多くを解決したが、以下が残存:

### eDS (126 件):
```
Composition.section:structuredSection.section:hospitalCourseSection.entry: 最小必要値 = 1、見つかった値 = 0
```

`hospitalCourseSection` の内側で `entry` slice が min=1 だが 0。

**対処**: eDS 生成分岐で `structuredSection.section:hospitalCourseSection` に対応する Reference (Condition/Observation 等の入院経過リソース) を entry に含める

### eDS (126 件): doc-subtypecodes display 不一致
```
http://jpfhir.jp/fhir/Common/CodeSystem/doc-subtypecodes#DISCHARGE の誤ったdisplay '退院時サマリー' - 選択肢: '退院時文書'
```

**対処**: eDS の Composition.type.coding.display を `'退院時文書'` に修正

### eReferral (24×5 = 120 件): 完全な profile 準拠残
```
Composition.extension:version min=1
Composition.category min=1
Composition.author min=2 (現状 1)
Composition.meta.lastUpdated min=1
```

**対処**: eReferral 生成分岐を eDS と同様に強化。特に author を 2 個以上に (作成者 + 認証者相当)

**期待効果**: -0.06pp

## 中優先 4 — YJ-code が JP_MedicationCodeYJ_VS binding 外 (~250 件、多数の code に散在)

**現象** (各 20-45 件、多数の YJ code):
```
提供された値（'2254001F1102'）は ValueSet 'JP Core Medication YJ ValueSet' に含まれていません
```

該当 code 上位: 2254001F1102, 2149032F1013, 3112001F1055, 2329023F1020, 2259709G1027, 2492403A4051 他多数

**背景**: JP_MedicationCodeYJ_VS は YJ code の subset のみ受容。clinosim が使用する code の一部が該当しない。

**対処案 (どれか)**:
1. **JP_MedicationCodeYJ_VS の code 一覧を確認** → clinosim 使用 code を VS 内の code に絞る
2. **VS を要求しない代替 profile** に切り替える (通常 MR_eCS ではなく別 profile)
3. **独自 CS を発行**: `http://clinosim.dev/fhir/CodeSystem/medication-yj-extra`

**期待効果**: -0.06pp

## 中優先 5 — ImagingStudy RadLexPlaybook VS 非包含 (499 件)

session 57 backlog より継続。JP profile が要求する RadLexPlaybook VS に該当 code が無い。

**対処**: session 57 の #218 (radiology DR profile 切替) と併せて対応

**期待効果**: -0.12pp

## 中優先 6 — AllergyIntolerance identifier slice + JFAGY related (76 件)

Ch263 で code fix したが、AI eCS profile の identifier:resourceIdentifier slice が 76 件で欠落 (v4 時点で発見済、Session 58 では未着手)。

**対処**: AI eCS で `identifier[system=http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier]` を必須追加

**期待効果**: -0.02pp

## 中優先 7 — MR.medication[x].coding min=1 (26 件)

**現象**:
```
MedicationRequest.medication[x].coding: 最小必要値 = 1、見つかった値 = 0
```

**対処**: `medicationCodeableConcept` に必ず `coding[]` を 1 以上含める (text だけの MR がある?)

**期待効果**: -0.006pp

## 中優先 8 — ICD-10 I84 in "2019-covid-expanded" version (64 件)

**現象**:
```
Unknown code 'I84' in the CodeSystem 'http://hl7.org/fhir/sid/icd-10' version '2019-covid-expanded'
```

I84 (結核関連) は "2019-covid-expanded" 版に含まれていない。Chain #6 の ICD-10 WHO sync が該当版を選定していないケース。

**対処**: I84 使用時は base ICD-10 (WHO 2016) を version に指定するか、code を差替

**期待効果**: -0.015pp

## Condition 残余 (75 件) - 要調査

Condition eCS Ch1 で 6,242 → 0 だが、75 件が残る。medisRecordNo slice の対応漏れ or 別 slice の可能性。**個別に error 内容確認要**

## Framework 導入 (v5 以降の drift 防止) の効果

- **Ph1 (#258 YJ template curated)**: YJ-code display mismatch **0 件** ✅
- **Ph3 (#271 LOINC substitution)**: 7 retired LOINC → active 差替 (retired 検出 0 件) ✅
- **Ph3-b (#277 LOINC display audit)**: 92 divergence 全 allowlist 化、Wrong Display Name.*loinc = **0 件** ✅

## 累計期待効果

上記 1-8 の対処で **fail 率 0.692% → ~0.1% (実質完全準拠)** への到達見込み。

## 継続 backlog (次サイクル以降)

- Composition eDS の hospitalCourseSection.entry 埋め込み (Ch9 follow-up)
- radiology DR profile Common → Radiology 切替 (session 57 #218 継続)
- ICD-10 base version 統一
- JP_MedicationCodeYJ_VS 適合 code 選定
