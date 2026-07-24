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

## 分類原則 (path 固定ではなく per-slice-match で判定)

**重要**: 「Observation.category は Tier 2-benign」のような **path 固定の分類は
禁止**。同じ path が第三者データでは violation (真の silent-pass) になり得る。

分類原則:

- **Tier 2-benign**: **required slice が match している状態で** 余剰 coding や
  余剰 identifier が unmatched になっているケース。data は profile が要求する
  制約を満たしており、余剰要素は data 設計上の意図 (JP + HL7 base 両対応など)。
  data 変更で消すには「片方の要素を捨てる」しかなく、それは別の非準拠を招く
- **Tier 2-violation**: **required slice が match していない** ケース。data が
  profile の期待する slice の discriminator (Fixed value / Pattern) に一致して
  いない。slice 内の required binding / Fixed display / cardinality は全て
  skip され、実質的な非準拠が silent で見逃される

判定手順 (recipe は [`docs/output-guide.md §4.5`](../../docs/output-guide.md) 参照):

1. profile 定義 (StructureDefinition) を読み、対象要素の slice 定義を確認
2. 各 slice の discriminator + Fixed/Pattern を特定
3. data の実物を見て、required slice に match する element が存在するか確認
4. 存在すれば余剰は benign、不在なら violation

以下の切り分けは **v31 データ + JP Core 1.2.0 / JP-CLINS 1.12.0 profile の
組み合わせにおいて** 上記手順で判定した結果。data や profile version が
変われば再判定が要る。

## 切り分け結果 (v31 実測)

生 count 28,334 件は **本質的に異なる 2 種類の混合**。

### Tier 2-benign (22,894 件 / 対 unmatched 80.8%)

#### (a) 意図的多重 coding × Open slicing 副作用 (19,583 件)

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

**性質**:
- **data 設計の非準拠ではない** (両 profile の要求を意図的に両立させた設計)
- HAPI validator の欠陥でもない (spec 上正しい挙動)
- 単純に「複数 profile 対応 + Open slicing」の構造的な副作用

#### (b) 余剰 identifier (3,264 件)

対象:
- `Observation.identifier[1]` **2,523 件** (2,523 obs)
- `Condition.identifier[1]` **736 件**
- `AllergyIntolerance.identifier[1]` **5 件**

いずれも **`.identifier[1]`** (array index 1) の unmatched。data 構造は共通:

- `identifier[0].system = "http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier"` (JP canonical)
- `identifier[1].system = "urn:clinosim:<resource>-id"` (generator internal)

判定根拠 (3 種で共通、2026-07-24 検証で統一):

- 3 種の **JP-CLINS eCS profile はいずれも `identifier:resourceIdentifier`
  slice (min=1 max=1)** を明示的に定義:
  - `Observation.identifier:resourceIdentifier` (JP-Observation-LabResult-eCS)
  - `Condition.identifier:resourceIdentifier` (JP-Condition-eCS)
  - `AllergyIntolerance.identifier:resourceIdentifier` (JP-AllergyIntolerance-eCS)
- `resourceIdentifier.system` は min=1 max=1 だが Fixed/Pattern なし
  (comment で JP system 指定 = Tier 3 の prose only 制約)
- data は 3 種とも identifier[0] に `http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier`
  (JP canonical) を配置。**generator の明示的な処理**:
  - Observation: `clinosim/modules/output/fhir_r4_adapter.py:1414/1931` で
    `_JP_OBSERVATION_RESOURCE_IDENTIFIER_SYSTEM` を必ず先頭 insert
  - Composition: `_JP_COMPOSITION_IDENTIFIER_SYSTEM` handling
  - Condition / AllergyIntolerance: 個別 explicit code は未確認 (要 verify)
    だが実データで identifier[0] = JP canonical が全 例確認
- observed HAPI behavior: identifier[0] が resourceIdentifier slice に match、
  identifier[1] のみ unmatched information

結論: **3 種とも profile 側 required slice `resourceIdentifier` (min=1) は
satisfied**、[1] は generator 内部 ID の余剰で benign。

**訂正メモ**: 前版 (2026-07-24 初稿) で「Cond/Allergy は profile 側 named
slice なし」と説明したのは誤り (grep 条件のバグで slice sub-element を拾い
損ねた結果)。実際は 3 種とも同一 pattern。

#### (c) profile 側 未 named type slice への fall-through (47 件)

対象: `MedicationAdministration.dosage.rate.ofType(Quantity)` 47 件
(全て 1 encounter POP-000017-816402801351 系、5 件目視確認、`rateQuantity`
value=60 U/h で全同一)

判定根拠 (2026-07-24 訂正):

- **JP_MedicationAdministration profile 定義**:
  ```
  MedicationAdministration.dosage.rate[x]  slicing={discriminator: type on $this, ordered: false, rules: open}
  MedicationAdministration.dosage.rate[x]:rateRatio  min=0 max=1  type=Ratio(profile=JP_MedicationRatio_DosePerPeriod)
  ```
- **rateRatio slice のみ named 定義**、rateQuantity 相当の named slice は無し
- base R4 は `rate[x]` type = [Ratio, SimpleQuantity]、data は rateQuantity で
  SimpleQuantity 制約に適合
- rules=open のため Ratio 以外の型は「unmatched information」が出るが、
  data 準拠は保たれる

**訂正メモ**: 前版で「HAPI validator の polymorphic quirk と推定」と書いたのは
誤り (base R4 profile しか見ていなかった)。実際は JP profile 側の設計
(rateRatio slice のみ named 定義、Quantity は open fall-through) 由来で
HAPI 側の bug ではない。

**性質**: (a) と同種で「profile 側の意図的な open 設計 × data の適合的な選択」
の組み合わせ副作用。data 非準拠ではない。upstream 報告候補にもしない
(HAPI 側 bug ではないため)。

### Tier 2-violation: 真の silent-pass (5,440 件 / 対 unmatched 19.2%)

data が profile の期待する slice の discriminator に一致していない **真の
silent-pass**。slice 内の required binding / Fixed display / cardinality は
全て skip される。

per-issue と per-resource の両方で示す (per-issue は coding を多く積むほど
悪く見える偏りがあるため、準拠率指標には per-resource が適切):

| resourceType | path | per-issue | per-resource | 主な原因 |
|---|---|---:|---:|---|
| Observation | `.code.coding` | 5,032 | **2,523** | JP-CLINS 検体検査 primary system misalign (Gate 2 pattern) |
| DiagnosticReport | `.code.coding` | 203 | 203 | 同 pattern |
| MedicationRequest | `.medication.ofType(CodeableConcept).coding` | 118 | 118 | 医薬品 CS 不一致 |
| Procedure | `.code.coding` | 44 | 11 | Procedure 標準 code 不一致 |
| Condition | `.bodySite.coding` | 43 | 43 | 部位 CS 不一致 |
| **合計** | | **5,440** | **2,898** | |

**pattern としては全て同一** = Open slicing の CodeableConcept slice で
discriminator (Fixed system / Pattern) 不一致。当初想定した 3 pattern
(CodeableConcept / identifier / polymorphic) は 分析後に **1 pattern に集約**
された:
- identifier 系 3,264 → benign (b) に移動
- polymorphic (Quantity) 47 → benign (c) に移動
- CodeableConcept slice 5,440 のみが violation

### 混同すると起きること

生 count 28,334 を「Tier 2 silent-pass の実態」として引用すると、
- 実際は **80.8% (22,894 件) が benign** (data 設計 or 制約なし or validator 副作用)
- 真に監視すべき **violation は 19.2% (5,440 件、全 issue の 4.26%)**

「JP-CLINS validation では issue の 22.19% が silent-pass」という一文だけ
切り出されると、実質 4.26% が本題の割合であることが失われる。

## 観察

1. **Tier 2-violation は全て CodeableConcept slice pattern に集約** — Gate 2 で
   発掘した検体検査 `code.coding` pattern がその代表 (per-resource 2,523 obs、
   violation の 87%)
2. **identifier 系は全て benign** — Observation は generator 側の explicit slice
   handling で保証、Condition/Allergy は profile 側 named slice なしで violation
   概念不成立
3. **HL7 base vital-signs profile 8,491 件は Tier 2-benign (a) 側**。HAPI 自動
   適用自体が問題ではなく、data の意図的多重 coding と組み合わさって現れる
4. **Quantity 47 件は独立 pattern に立てない**。HAPI validator 側 quirk と推定、
   小規模、修正の主体は upstream HAPI 側

## 中期検討事項 (docs 記録)

第三者ユーザーにとって 22,894 件 (17.9% of all issues) の benign 系 information
issue が出力に混ざるのは UX 上の問題。suppress or 集約 option を提供できると
実用性が上がる (例: `--suppress-slice-unmatched-info`、または集計 side での
自動フィルタ)。ただし suppress 実装時は「benign と判定する条件」が data 依存
なので、ユーザ側で white-list を設定できる形が望ましい。

## 移行効果測定における意味

JLAC 移行の効果測定では、これまで「エラー数の増減」を追ってきたが、
**Tier 2-violation 分布はエラーには全く現れない**。5,440 件 / 2,898 resources
の分布を移行前後で比較することで:

- per-resource **`matched / (matched + unmatched)` の比率 = slice 適合率**
  という新指標が取れる
- 移行前は unmatched がベースラインとして数えられていなかったため、この計測は
  「エラーが減った」とは全く別軸の成果になる
- **per-resource 指標を使う** (per-issue だと coding を多く積むほど悪く見える)
- ただし Tier 2-benign の生 count は移行の効果測定には使えない (data の
  設計 or profile 定義に依存する定数分)

**移行が violation を消す実例予測**: JLAC 移行後、CoreLabo slice が data に
match することで Observation.code.coding 2,523 resource 全てが violation
から外れる。LOINC secondary coding を残しても required slice が match すれば
それは benign (a) 側 (意図的多重 coding) に自動的に移動するだけ。→ **この指標は
移行の効果を正しく反映する**ことが分析から裏付けられた。

### 移行後の残差 (375 resource) の内訳

Observation.code.coding 2,523 resource が violation から外れた後、以下 375
resource が残る (v31 時点、いずれも移行対象外の resourceType):

| resourceType | path | per-issue | per-resource |
|---|---|---:|---:|
| DiagnosticReport | `.code.coding` | 203 | 203 |
| MedicationRequest | `.medication.ofType(CodeableConcept).coding` | 118 | 118 |
| Condition | `.bodySite.coding` | 43 | 43 |
| Procedure | `.code.coding` | 44 | 11 |
| **合計** | | **408** | **375** |

移行前にこの内訳を把握しておく理由: 移行後 violation が「~2,898 → ~375」に
落ちた際、想定内 vs 未把握 drift かを判断可能にするため。予測 375 と実測値の
乖離があれば、それは移行過程で新たに導入された非準拠 or 発生条件の変化を示す。

**generator 側 移行スコープの示唆** (workspace:1 検討材料、docs 化しない
内部記録): 残 375 の最多が DiagnosticReport.code の 203 resource である点は、
JP-CLINS の JP_DiagnosticReport_LabResult_eCS も検体検査 Observation と
対になる profile であることを反映している。Observation.code のみを移行対象と
すると、対の DiagnosticReport.code は同じ CoreLabo slice を用意しても
未 match のまま残る。generator 側の移行実装で対象 resource スコープを
決める際の判断材料。

### 移行後の役割変化 (最重要)

Observation.code.coding 移行完了後、この指標は「検体検査を測る軸」から
「**新規 drift を検出する軸**」に役割が変わる。

- 移行前 (現状): violation 2,898 のうち検体検査 2,523 (87%) が dominant
  → 検体検査の実装進捗を測る指標
- 移行後: violation 375 前後 (base line)
  → 生成側 data の変更 / profile 更新 / validator 版更新で
     この数値が変動した瞬間、新規 drift の signal になる

**数値が小さくなったことを「軸の価値が下がった」と読まないこと**。むしろ
「検出感度が高い状態に到達した」段階で、以降は 375 前後を平常値として維持し、
逸脱時のみ alarm する運用に移る。generator 側の validation loop に
「slice 適合率 baseline 逸脱チェック」を組み込む価値がある (中期検討)。

## 陳腐化リスクと更新方針

- **Tier 2-violation** 5,440 件は JLAC 移行完了で Observation.code 分 5,032 が
  消え、残 408 issue / 375 resource は移行対象外 (DiagnosticReport / Medication
  Request / Procedure / Condition.bodySite) のため変動しない見込み
- **Tier 2-benign (a) 意図的多重 coding** 19,583 件は clinosim generator の
  category emit 設計が変わらない限り constant
- **Tier 2-benign (b) 余剰 identifier** 3,264 件は generator の identifier[1]
  emit 設計が変わらない限り constant
- **Tier 2-benign (c) profile 側 未 named type slice** 47 件は JP_Medication
  Administration profile が rateQuantity slice を named 定義する更新をしない
  限り constant。data 側で rate を Ratio 型で emit するように変更しても消える

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
