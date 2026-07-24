# Tier 2 (slice unmatched) 分布 — v31 データ実測

## 測定条件 (先頭明記、陳腐化防止)

| 項目 | 値 |
|---|---|
| 測定日 | 2026-07-24 |
| データセット | clinosim v31 の合成 EHR、`fhir_r4/` (Bundle 化後 1,161 Bundle) |
| validator | HAPI Validator 6.9.12、6 JVM cluster、tx=`http://localhost:8181/r4` |
| fhirserver 構成 | Phase 1 (MHLW ICD-10 完全版) + Phase 3 (MHLW masterB/Z 完全版) load 済 |
| 元 run | `validation-results/2026-07-23_full_v31_p100_phase3_receipt_complete/` |
| 集計 script | [`docs/output-guide.md §4.5`](../../docs/output-guide.md) |

**このファイル内の数値 (28,334 件 / 22.19% 等) は上記条件でのみ有効**。
data の性質と validator 構成に強く依存するため、後日別条件で測ると変わる。
外部への引用時は必ず条件セットで示すこと。

## 何を計測したか

Gate 2 で発掘した silent-pass パターン (`code.coding` の Open slicing) が、
検体検査 Observation の code.coding 固有ではなく **JP-CLINS profile 全体に
広範に分布する構造的パターン**であることを、v31 の `result.ndjson` で実測。

message pattern は日本語版
`この要素はどの既知のスライスとも一致しません` + 英語版
`This element does not match any known slice` の両方をカバー。

## 実測サマリ

- **scanned**: 1,161 Bundle、127,663 issue
- **slice unmatched (severity=information)**: **28,334 件 = 全 issue の 22.19%**
- 該当リソース種別: 7 種 (Observation / Condition / DiagnosticReport /
  MedicationRequest / MedicationAdministration / Procedure / AllergyIntolerance)

silent-pass は **`Observation.code.coding` だけの現象ではない**。JP-CLINS
profile を宣言している任意の CodeableConcept 系 slice で発生している。

## resourceType 別

| resourceType | 発生件数 | unique リソース |
|---|---:|---:|
| Observation | 26,954 | 13,431 |
| Condition | 779 | 736 |
| DiagnosticReport | 387 | 210 |
| MedicationRequest | 118 | 118 |
| MedicationAdministration | 47 | 47 |
| Procedure | 44 | 11 |
| AllergyIntolerance | 5 | 5 |

## profile 別

| profile | 発生件数 |
|---|---:|
| `JP_Observation_Common` | 10,908 |
| `JP_Observation_LabResult_eCS\|1.12.0` | 7,555 |
| `heartrate\|4.0.1` (HL7 vital-signs 自動 profile) | 2,819 |
| `oxygensat\|4.0.1` | 2,500 |
| `bp\|4.0.1` | 1,252 |
| `bodytemp\|4.0.1` | 987 |
| `resprate\|4.0.1` | 933 |
| `JP_Condition_eCS\|1.12.0` | 779 |
| `JP_DiagnosticReport_LabResult` | 354 |
| `JP_MedicationRequest_eCS\|1.12.0` | 118 |
| `JP_MedicationAdministration` | 47 |
| `JP_DiagnosticReport_Radiology` | 26 |
| `JP_Procedure` / `JP_Procedure_eCS\|1.12.0` | 各 22 |
| `JP_DiagnosticReport_Microbiology` | 7 |
| `JP_AllergyIntolerance_eCS\|1.12.0` | 5 |

**HL7 vital-signs 系 5 profile (heartrate/oxygensat/bp/bodytemp/resprate) の
合計 8,491 件**は、Observation に LOINC vital-sign code が含まれると HAPI が
自動的に vital-signs profile を追加適用する挙動由来。JP-CLINS 側の profile と
同時評価されるため、双方で unmatched が計上される。

## 要素 path 別 (top、正規化済)

| resourceType | element path | 発生件数 | unique リソース |
|---|---|---:|---:|
| Observation | `.category` | **19,399** | 10,908 |
| Observation | `.code.coding` | 5,032 | 2,523 |
| Observation | `.identifier` | 2,523 | 2,523 |
| Condition | `.identifier` | 736 | 736 |
| DiagnosticReport | `.code.coding` | 203 | 203 |
| DiagnosticReport | `.category` | 184 | 184 |
| MedicationRequest | `.medication.ofType(CodeableConcept).coding` | 118 | 118 |
| MedicationAdministration | `.dosage.rate.ofType(Quantity)` | 47 | 47 |
| Procedure | `.code.coding` | 44 | 11 |
| Condition | `.bodySite.coding` | 43 | 43 |
| AllergyIntolerance | `.identifier` | 5 | 5 |

path は `[N]` (array index) と `:sliceName` を除去して正規化。

## 切り分け: unmatched は 2 種類に分かれる (最重要)

生の unmatched カウント 28,334 件をそのまま「silent-pass の実態」と読むと誤る。
分析すると **2 つの本質的に異なる pattern の混合**であることが確定した。

### Tier 2-noise: 意図的多重 coding × Open slicing の副作用 (19,583 件)

対象:
- `Observation.category` **19,399 件** (10,908 obs)
- `DiagnosticReport.category` **184 件**

原因:

- **JP_Observation_Common の `Observation.category:first` slice 定義**:
  - discriminator = `value on coding.system`
  - rules = `open`
  - first slice の `coding.system` = **fixed to `JP_SimpleObservationCategory_CS`**
  - required binding to `JP_SimpleObservationCategory_VS`
- **data 側の category 構造 (合成 EHR 例)**:
  - `category[0].coding`: `system=http://terminology.hl7.org/CodeSystem/observation-category, code=vital-signs`
  - `category[1].coding`: `system=JP_SimpleObservationCategory_CS, code=vital-signs`

結果として:

- **JP_Observation_Common の view**: `[1] JP` は first slice に match (OK)、
  **`[0] HL7 base` は system fixed 不一致で unmatched information** → 10,908 件
- **各 vital-signs auto-profile の view**: `[0] HL7 base` は VSCat slice に match
  (OK)、**`[1] JP` は unmatched information** → 合計 8,491 件

**両方の profile が並行評価され、それぞれが「相手側の coding」を unmatched と
報告している** 状態。data は両方の profile の要求を同時に満たしているのに、
Open slicing rules=open の仕様上、余剰 coding が必ず information として残る。

**Tier 2-noise の性質**:
- **data 設計の非準拠ではない** (両 profile の要求を意図的に両立させた設計)
- HAPI validator の欠陥でもない (spec 上正しい挙動)
- 単純に「複数 profile 対応 + Open slicing」の構造的な副作用
- data 変更で消すには「片方の coding を捨てる」しかなく、それは別の非準拠を招く

### Tier 2-real: 真の silent-pass (data missing required slice match) (8,751 件)

対象 (残り 全て):

| resourceType | path | 件数 |
|---|---|---:|
| Observation | `.code.coding` | 5,032 |
| Observation | `.identifier` | 2,523 |
| Condition | `.identifier` | 736 |
| DiagnosticReport | `.code.coding` | 203 |
| MedicationRequest | `.medication.ofType(CodeableConcept).coding` | 118 |
| MedicationAdministration | `.dosage.rate.ofType(Quantity)` | 47 |
| Procedure | `.code.coding` | 44 |
| Condition | `.bodySite.coding` | 43 |
| AllergyIntolerance | `.identifier` | 5 |
| **合計 (全 issue の 6.86%)** | | **8,751** |

これらは data が profile の期待する slice の discriminator (Fixed value / Pattern)
に一致していない **真の silent-pass**。Gate 2 で発掘した `Observation.code.coding`
の JP-CLINS 検体検査 pattern がその代表例。

### 混同すると起きること

生 count 28,334 を「Tier 2 silent-pass の実態」として引用すると、
- 実際は 69% (19,583 件) が **data 設計として正しいもの** の副作用
- 真に監視すべき Tier 2-real は 31% (8,751 件)

「JP-CLINS validation では issue の 22.19% が silent-pass」という一文だけ
切り出されると、実質 6.86% が本題の割合であることが失われる。

## 観察

1. **Tier 2-real の最多は `Observation.code.coding` (5,032 件、2,523 obs)** —
   Gate 2 で発掘した検体検査 pattern
2. **identifier 系** (Observation / Condition / AllergyIntolerance) は全て
   Tier 2-real。Open slicing + system 別 slice で discriminator 不一致
3. **`MedicationAdministration.dosage.rate.ofType(Quantity)` 47 件** は Quantity 型
   の Open slicing (rate\[x\] の型別 slice) unmatched、Tier 2-real 型として異色
4. **HL7 base vital-signs profile 8,491 件は Tier 2-noise 側**。HAPI 自動適用
   自体が問題ではなく、data の意図的多重 coding と組み合わさって現れる

## 移行効果測定における意味

JLAC 移行の効果測定では、これまで「エラー数の増減」を追ってきたが、
**Tier 2-real 分布はエラーには全く現れない**。8,751 件の分布を移行前後で比較
することで:

- **matched / (matched + unmatched)** の比率 = **slice 適合率**という新しい指標が
  取れる
- 移行前は unmatched がベースラインとして数えられていなかったため、この計測は
  「エラーが減った」とは全く別軸の成果になる
- ただし Tier 2-noise (category 系) を含めた生 count は移行の効果測定には使えない
  (data の多重 coding 設計に依存する定数分)

## 陳腐化リスクと更新方針

Tier 2-real の 8,751 件 は generator が JLAC 移行を完了すれば **検体検査分
(5,032 件) が変動**する。他 (identifier 系 3,264 件、medication 系 165 件、
Procedure 44 件、bodySite 43 件、DiagnosticReport 203 件) は移行対象外のため
変動しない見込み。

Tier 2-noise の 19,583 件は clinosim generator の category emit 設計が
変わらない限り constant。generator が JP + HL7 base の両方を出す限り、必然的に
このカウントが出る。

**別の validation run で測り直したら、必ず run ごとに測定条件 + 分布を新規
`tier2-distribution-<run-id>.md` として記録**。このファイルを更新して古い数字を
上書きしない (陳腐化した測定値の追跡不能を防ぐ)。

## 再現手順

```bash
# 分布再計測
python3 <<'PY'
import json, re, collections
path = 'validation-results/2026-07-23_full_v31_p100_phase3_receipt_complete/raw/all.ndjson'
# ... (recipe は docs/output-guide.md §4.5)
PY
```

recipe 本体は [`docs/output-guide.md`](../../docs/output-guide.md) の
「4.5 Tier 2 (slice unmatched) の集計」節に、汎用形 (message pattern と
resourceType 両方でフィルタ可能) で維持。
