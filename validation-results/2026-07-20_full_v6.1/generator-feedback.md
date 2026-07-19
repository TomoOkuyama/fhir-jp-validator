# 生成者向けフィードバック — 2026-07-20 v6.1 (session 60 5 chain merge 後)

対象: clinosim 側 (workspace:1)。次サイクル (v7) で対応すべき事項を優先度順に整理。

## 🎉 総評

- **v6 の regression から完全回復し v5 を超過達成**: v5 0.692% → v6 3.554% → v6.1 **0.190%**
- **judgment recovery 3 chain (#306/#308/#310) は完璧に機能**: NOCODED / UnitsOfTime / eReferral event.code の 3 大 issue が全て完全消滅
- **MedicationRequest / MedicationAdministration が 0 errored に到達** (v6 で 95.4% / 19.4% fail → v6.1 0% / 0%)
- **Chain #315 のみ approach を変更する必要あり**: text-only では required binding を回避できず、procedureCode 省略または RadLex code 選定が必要

## 【最優先 1】Chain #315 見直し: ImagingStudy.procedureCode 省略 (589 件)

### 現象

```
Bundle.entry[N].resource/*ImagingStudy/.../.procedureCode[0]
コードが提供されていません。ValueSet 'JP ImagingStudy RadLexPlaybook CodeDev VS'
(http://playbook.radlex.org/playbook/SearchRadlexAction|1.0.0) のコードが必須です
```

### v6.1 の実データ (Chain #315 適用後)

```json
{
  "procedureCode": [{"text": "胸部単純X線撮影 正面"}]
}
```

### なぜ text-only では駄目か

`procedureCode` の binding は **required strength**。required binding は「element を出すなら VS の code を coding に必ず 1 個入れる」ことを要求し、`text` は充足条件に含まれない。text は補助表示のためのフィールドで、required binding VS が空でよい唯一の方法は **要素自体を省略する** こと。

### 推奨対処

**`procedureCode` 要素を出力しない (省略)**。cardinality は `0..*` なので合法。検査内容は以下いずれかに移す:
- `ImagingStudy.description` (人間可読テキスト)
- `ImagingStudy.reasonCode` (適応理由、緩い binding)
- (要件次第) `ServiceRequest.code` に集約し ImagingStudy → SR 参照

### 代替案 (時間があれば)

- **RadLexPlaybook VS 内の code mapping table を整備**: 検査種別 (胸部単純X線正面、CT、MRI 等) → RadLex code の変換テーブル。ただし RadLex code の実体は playbook.radlex.org VS で取得性に課題がある可能性 (v3-v6 で継続 backlog)
- **JP Core への binding 緩和 PR**: strength を required → extensible に。upstream 相談が必要で時間軸長い

### 期待効果

**-0.14pp (fail 率 0.190% → ~0.05%)**

## 【最優先 2】eReferral referralFrom/toSection Organization slice (42 件、#313 backlog)

Session 60 では「継続 backlog」として issue file 済み。中〜大工数 (eCS profile Organization 新設 + 8 required fields)。

v6.1 では依然 22+22-2 = 42 件残 (v6 の 44 件から微減、Composition レベルで unique 21 件)。

**対処**: eCS profile Organization を新規 emit し referralFromSection/referralToSection の Organization slice を埋める。8 required fields (identifier[insurance-institution-num], name, telecom.system + value, address.text) が必要。

**期待効果**: -0.005pp (fail 率 → 0.185%)

## 【中優先 3】Observation.code.text 欠落 (190 件、v5 継続)

**現象**:
```
Observation.code.text: 最小必要値 = 1、見つかった値 = 0
(from JP_Observation_LabResult / JP_Observation_LabResult_eCS)
```

JP_Observation_LabResult profile は `code.text` を required (min=1) にしている。LOINC coding の display 相当を text にも入れる必要がある。

### 対処

Observation 生成時 `code.text = code.coding[0].display` を必ずセット (LOINC 名称 or 日本語検査名)。

### 期待効果

**-0.044pp (fail 率 → ~0.14pp)**

## 【中優先 4】Observation valueCodeableConcept.coding.display 欠落 (162 件)

**現象**:
```
Observation.value[x]:valueCodeableConcept.coding.display: 最小必要値 = 1、見つかった値 = 0
(from JP_Observation_LabResult_eCS)
```

qualitative Observation (value が CodeableConcept 型、例: 陽性/陰性、+/-) で `coding.display` が空。

### 対処

qualitative code に必ず display を設定 (SNOMED code や JLAC10 に対応する日本語表現)。

### 期待効果

**-0.038pp (fail 率 → ~0.10pp)**

## 【中優先 5】Observation value.Quantity ele-1 (22×2 = 44 件)

**現象**:
```
Observation.value.ofType(Quantity).unit — ele-1 empty
Observation.value.ofType(Quantity).code — ele-1 empty
```

Quantity の `unit` / `code` が空文字列で emit されている (11 件の Observation で 2 field × 2 (ele-1 + "値は空にできません") = 44 error instances)。

### 対処

Quantity の unit / code が無い場合は field ごと省略。空文字列で埋めない。

### 期待効果

**-0.010pp**

## 【中優先 6】Observation referenceRange units invariant (22 件)

**現象**:
```
Constraint failed: referenceRangeLowUnits-isSameAs-resultValueUnits (11 件)
Constraint failed: referenceRangeHighUnits-isSameAs-resultValueUnits (11 件)
```

JP_Observation_eCS の invariant: reference range の unit が value の unit と完全一致していない (例: value=`mg/dL`, refRange low=`mg/L`)。

### 対処

referenceRange.low.unit と referenceRange.high.unit を value のそれと同一化する。

### 期待効果

**-0.005pp**

## 【低優先 7】Location v3-RoleCode 'OR' unknown (2 件)

**現象**:
```
system 'http://terminology.hl7.org/CodeSystem/v3-RoleCode' で未知のコード 'OR'
```

`OR` (Operating Room?) は v3-RoleCode に含まれていない。正しい code は例えば `ICU`, `ER` 等。

### 対処

正しい v3-RoleCode に置換 (該当 CS の code list を確認)。

## 【問題無し】完全解決した項目

Chain #306 (NOCODED display) / #308 (timing.repeat) / #310 (event.code) / #312 (route SL): **全て実測 0 件で完全解決** ✅✅✅

特に:
- **NOCODED display 12,891 件 → 0 件** — display 固定 + text へ薬剤名移動が正しく動作
- **UnitsOfTime binding 3,532 件 → 0 件、tim-2 も 0 件** — boundsDuration only 化が両方を回避
- **eReferral event.code Array wrap + display 正規化 37 件 → 0 件**
- **MAR route SL Sublingual 13 件 → 0 件**

## 修正後の見込み

**優先度 1 のみ (procedureCode 省略)**:
- error 1,247 → 658 (**-47%**)
- fail 率 0.190% → **~0.05%**

**優先度 1 + 3 + 4 + 5 + 6 (procedureCode 省略 + Observation 系)**:
- error → **~200**
- fail 率 → **~0.02%** (実質完全準拠)

**優先度 1-7 全対処**:
- error → **~40** (backlog #313 の 42 件と infra timeout 6 件のみ)
- fail 率 → **~0.01%** (完全準拠水準)

## Session 60 の総括

- **判断力 (judgment) が試された 3 chain 全て pragmatic middle path で正解**: NOCODED (display 固定 + text)、UnitsOfTime (boundsDuration only)、event.code (Array wrap + text 権威 pin)。いずれも「validator 挙動を無視した理想実装」でも「validator に完全譲歩した実装」でもなく、生成側で自然に成立する形で妥協点を見つけている。
- **Chain #315 は approach 選択そのものが要再考**: text-only は required binding を満たさない、これは FHIR spec の設計上の原則 (text は補助情報)。procedureCode を出さない選択が最もクリーン。
- **今後の chain 設計指針**: required binding の VS に該当 code を持たない時、text で回避しようとすると失敗する。要素省略 or VS 拡張 or upstream 緩和の 3 択で計画すべし。
