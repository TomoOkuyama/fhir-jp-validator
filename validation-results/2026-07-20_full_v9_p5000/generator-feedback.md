# 生成者向けフィードバック — 2026-07-20 v9 (p=5000 seed=500 regression)

対象: clinosim 側 (workspace:1)。5x scale + 別 seed で発掘された新規 issue と、v8 chain robustness の実測。

## 総評

- **fail 率 v8 0.0063% → v9 0.0129%** (予測 0.005-0.02% 範囲内、良好)
- **v8 の 11 PR fix 全て regression なし** (chain robustness 完全維持)
- **新規 latent issue 3 種発掘** (seed=500 で初出): R53.1 (ICD-10 covid-expanded)、admit-source 'hosp'、microbiology Observation identifier
- **generator 完成度が非常に高い**ことを scale + seed 変動で再確認

## 【最優先 1】 R53.1 in ICD-10 covid-expanded (78 件、fail 率 0.005pp)

**現象**:
```
Unknown code 'R53.1' in the CodeSystem 'http://hl7.org/fhir/sid/icd-10' version '2019-covid-expanded'
```

**内訳**:
- MedicationAdministration.reasonCode: 75 件 (fail 率 0.034%)
- Encounter.reasonCode: 2 件
- Condition.code: 1 件

**背景**: R53.1 = "Weakness / 体力低下" は base ICD-10 (SID `http://hl7.org/fhir/sid/icd-10`) にはあるが、
Composition が指定する `2019-covid-expanded` version の CS 定義に含まれていない (covid 関連拡張版として
別の code 集合を持つため)。**session 57 Chain #285 で I84 (結核関連) が covid-expanded 版に無くて base ICD-10
に切替えた** のと同じパターン。

**対処**:
- R53.1 を使う diagnosis code 生成時、覆う CS version を確認
- 選択肢 1: base ICD-10 (`http://hl7.org/fhir/sid/icd-10` の version 指定なし) を使う
- 選択肢 2: covid-expanded 対応 code に置換 (例: R53.83 "Other fatigue" ないし G93.3 "Postviral fatigue syndrome")
- 汎用 fix: generator の diagnosis code walker に「使用 code × 該当 CS version 整合性チェック」を追加

**期待効果**: **-78 error (-25% of total v9 error)**

## 【中優先 2】 Encounter admit-source `'hosp'` (2 件)

**現象**:
```
system 'http://terminology.hl7.org/CodeSystem/admit-source' で未知のコード 'hosp'
```

**背景**: v3 admit-source CS の有効 code 一覧 (`emd`, `nursing`, `psych`, `rehab`, `hosp-trans`, `mp`, etc.) に
`hosp` は存在しない。おそらく `hosp-trans` "Transfer from hospital" の短縮版として使われた誤り。

**対処**: `hosp` → `hosp-trans` に置換 (Transfer from hospital)

## 【低優先 3】 Microbiology Observation identifier resourceIdentifier slice (1 件、非常に稀)

**現象**:
```
Slice 'Observation.identifier:resourceIdentifier': minimum required = 1, but only found 0
(from JP_Observation_LabResult_eCS)
mb-org-ENC-POP-002287-170531078110-0
```

**背景**: microbiology Observation (`mb-org-*`) の identifier slice `resourceIdentifier` が空。
JP_Observation_LabResult_eCS profile は identifier[use=official + system=eCS namespace] を required。

**対処**: microbiology Observation の identifier[0] に use=official + system=`urn:oid:1.2.392...` (eCS namespace) を設定

## v8 chain の 5x scale + 別 seed regression チェック結果

**全 11 chain regression なし**:

| Chain | 対象 | v9 実測 | 判定 |
|---:|---|---|:---:|
| #306 | NOCODED display 固定 | **0 件** | ✅ hold |
| #308 | boundsDuration only | **0 件** | ✅ hold |
| #310 | event.code Array wrap | **0 件** | ✅ hold |
| #312 | route SL Sublingual | **0 件** | ✅ hold |
| #315→#320 | procedureCode 省略 | **0 件** | ✅ hold |
| #322 | code.text + valueCC display | **0 件** | ✅ hold |
| #324 | valueQuantity omit | **0 件** | ✅ hold |
| #326 | LAB_UNITS PT/APTT | **0 件** | ✅ hold |
| #328 | Location OR text-only | **0 件** | ✅ hold |
| #329 | eReferral eCS Organization emit | **data 完璧、client sticky で確定** | ✅ (v8.1 で証明) |

## 【継続 backlog】 client 側の Chain #329 追加課題 (v8.1 で発見)

v8.1 で sticky include (`--include-file`) を実装した際、**cross-bundle resolve() が成立した瞬間に露出した
163 件の latent error** — Composition.author[1] と Composition.custodian が `Organization/hospital-main`
を参照するが base JP_Organization のみで eCS profile を持たない。

**Chain #330 候補**:
- eCS Composition (JP_Composition_eDischargeSummary、JP_Composition_eReferral 等) の author/custodian は
  eCS-flavored Organization (`hospital-main-ecs`) を参照するよう切替
- または `hospital-main` にも `JP_Organization_eCS` profile を追加宣言 (profile stacking)

v9 では sticky なしで検証したためこの issue は表面化していないが、実運用の document Bundle 検証では発火する。

## 修正見込み

**優先度 1 (R53.1) 対処のみで**: error 310 → 232 (**-25%**)、fail 率 0.0129% → **0.0079%** (v8 水準に回復)

**優先度 1 + 2 + 3 全対処 + Chain #330 (eCS Organization author/custodian) で**:
- data 由来 error → **0**
- 残 error は timeout 20 のみ = **0.0013%** (実質完全準拠)

## Session 60→61 の総括 (v9 で確定)

- **fail 率推移**: v1 65% → v6 3.55% → v6.1 0.19% → v8 0.006% → v9 0.013% (scale-adjusted)
- **11 PR chain は seed/scale variance 耐性を実証**、Chain fix design が本質的に正しい
- **compliance 到達水準**: rare event pattern (R53.1 / admit-source / microbiology) の残余対処のみで実質完全準拠
- **generator design maturity**: 主要な準拠課題は解消済み、今後は long-tail pattern の pruning
