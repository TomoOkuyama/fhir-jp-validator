# JP-CLINS validation の既知の限界

本ドキュメントは、JP Core 1.2.0 / JP-CLINS 1.12.0 を HAPI Validator +
terminology server で検証する場合に **何が検出され、何が検出されないか** を
整理する。想定読者は、自身の FHIR data を JP-CLINS 準拠かどうか確認したい
実装者・ベンダー・システム連携担当者。

fhir-jp-validator が対応している範囲と、まだ対応していない範囲の両方を
記述する。

**適用範囲**: 本文書は **HAPI Validator 6.9.12 / JP Core 1.2.0 / JP-CLINS
1.12.0 / jpfhir-terminology 2.2606.0** 時点の挙動に基づく (2026-07 時点)。
HAPI Validator や profile 版の更新で Tier 2 の一部が Tier 1 に移動する等
挙動が変わる可能性がある。

## 1. 何が検出され、何が検出されないか (要旨)

FHIR profile の制約は、検出のされ方によって 3 層に分けられる。層ごとに
検出手段が異なり、fhir-jp-validator がどこまでカバーできるかも変わる。

| 層 | 制約の性質 | 検出手段 | fhir-jp-validator の対応 |
|---|---|---|---|
| Tier 1 | FHIR spec に符号化されており、閉じた slicing・cardinality・Fixed value・required binding など HAPI が確実に発火するもの | HAPI standard | ✅ 標準構成で検出 |
| Tier 2 | FHIR spec に符号化されているが、Open slicing (`rules=open`) により slice match しなかった場合に severity=information に留まるもの | HAPI (information issue の集計) | ⚠️ 集計 recipe で可視化 (当プロジェクトの回帰監視には test-cases を使用) |
| Tier 3 | IG 本文の散文にのみ記述され、FHIR spec の制約として符号化されていないもの (文字種規則、コーディング適用規則、5情報送信時の要素禁止など) | custom check 実装が必要 | ❌ **未実装**。docs で対象を列挙 |

**JP-CLINS を HAPI + fhirserver で検証する場合、Tier 2 の一部は
error/warning に現れず、Tier 3 は一切現れない**。生の validation 結果を
「fail=0 なら準拠」と読むと、Tier 2/3 の非準拠を見逃す。

以降 §2/§3/§4 で各層の詳細、§5 で中期の課題を述べる。

## 2. Tier 1: HAPI で確実に発火する制約

対象 (FHIR spec で符号化されている構造制約):

- 要素の cardinality (`min=1` の必須要素、`max=1` の重複禁止)
- 要素の datatype rule (`id` 長制限、`code` 形式、`Instant` 形式など)
- 閉じた slicing (`rules=closed`) の slice discriminator
- Fixed value / Pattern の完全一致
- FHIRPath invariant (`ele-1`, `dom-6`, `con-3/4/5` など)
- Reference 型の型制約 (`Reference(Patient)` に Practitioner を入れると error)
- required binding の ValueSet 適合 (match した slice 内)

これらは HAPI validator が自動で発火する。fhir-jp-validator の標準構成
(6 JVM cluster + fhirserver tx) で検出される。

**Tier 1 の位置づけ**: fhir-jp-validator の独自の付加価値ではなく、
HAPI standard の到達範囲。ただし **validator 構成が正常に動作していることの
positive control** としての意味を持つ:

- terminology load 漏れ、profile 解決失敗、tx server 未接続などがあると
  Tier 1 も静かに無反応になる。症状は Tier 2 の silent-pass と区別が
  つかない
- 「Tier 1 の case が期待どおり error を出すこと」を継続的に確認することで、
  validator infrastructure の生存を担保する

test-cases framework (`test-cases/` 200+ case) は Tier 1 の positive control
を主目的とする regression suite。

### 2.1 validator 構成に依存する挙動 (Tier 1 外の記録)

以下は「FHIR profile 制約として符号化されているが、HAPI 標準構成では
発火しない or 発火が構成に依存する」項目。**inline case にすると構成を切り
替えないと観測できない**ため、docs で挙動を記録する形にしている。

- **`mustSupport` は HAPI が標準で強制しない**: JP-CLINS eCS profile には
  1,600+ の `mustSupport=true` 要素があるが、これらは「受信側実装が処理
  できなければならない」という**実装要件**であり、インスタンスの妥当性
  条件ではない。HAPI validator は default で `mustSupport` の有無を error
  化しない。将来 HAPI 側で厳密モード flag が加わった場合、または custom
  check を実装した場合に評価されうる。**現状「発火しないことが正常」**
- **`dom-6` (narrative missing) は Best Practice 判定**: HAPI は default で
  warning、`-best-practice ignore` flag で downgrade される (実測では
  suppress ではなく warning のまま出続けるケースがある — 実装/version
  依存)。本プロジェクトの reconcile は `-best-practice ignore` を default
  付与しているが、実データ検証時は付与しないケースがあるため、data が
  narrative を持つべきかは data 側の設計判断
- **profile 解決失敗は silent**: `meta.profile` に未知の URL を宣言しても
  HAPI は「その profile は評価できない」ではなく、単に **profile 評価を
  skip** する。error/warning は出ない。誤字や存在しない profile URL を
  data 側で書いても、validator は静かに no-op する

これらは「validator が発火しないことを assert する case」を単体で書いても
構成切り替えの前提が伴い、regression suite として維持しにくい。docs 上の
記録にとどめ、custom check 実装 (§4) 時に取り込む候補とする。

### 2.2 test-cases framework 側の観測経路 (訂正、2026-07-24 v2)

**過去の記述の訂正**: 初版で「HAPI が実装していない check」として rat-1、
att-1、ele-1 on Coding、choice[x] 多重値、coding-empty、Ratio.denominator=0
等を挙げていたが、これは誤り。**HAPI はこれらを全て検出する**。誤認の原因は
`test-cases framework` (`scripts/reconcile-test-cases.py` の
`parse_errors`) の expression 解析不備で、issue の一部を silent に取り
こぼしていた:

- HAPI は Bundle validation 時、issue の expression に 2 形式を出す
  - 形式 A: `Bundle.entry[N].resource/*Type/id*/...` (構造レベル issue)
  - 形式 B: `Bundle.entry[N].resource` (parse-level issue、type/id 情報なし。
    「認識できないプロパティ」「オブジェクトには何らかのコンテンツが必要」
    「ルール rat-1 が失敗しました」等の parse-time で発火する error)
- 初版 framework は形式 A のみ regex match していたため、形式 B の issue は
  resource id に attribute できず silent に落ちていた
- 結果、期待通り検出されているのに reconcile が「検出されていない」と誤判定
- 「validator gap」と誤って結論、upstream 報告 draft まで進みかけた

**運用ルール** (再発防止):
- **「validator が検出しない」と判断する前に、framework を経由せず
  `validator_cli` に直接投げて確認する**
- framework の観測は測定器であり、測定器を疑う手段を常に持っておく必要がある
- 「テストが無い」を「実装が無い」の根拠にしない (fhir-test-cases に該当
  test-case が無くても、HAPI の汎用機構で cover されている可能性がある。
  例: rat-1 は StructureDefinition の constraint[] として定義された FHIRPath
  式で、HAPI は汎用 evaluator で処理する)

**現在の framework fix** (2026-07-24): `parse_errors` は形式 A/B の両方を
解析し、形式 B は同 OC 内の他 issue から entry_index → resource_id map を
作って attribute する。単一 resource 前提の OC には unique_id fallback も
用意している。この修正で以下 11 mechanism が正常に検出・PASS 化された:

- rat-1 (Ratio invariant、numerator-only 等)
- att-1 (Attachment.data → contentType 必須)
- ele-1 on empty Coding (`オブジェクトには何らかのコンテンツが必要です`)
- 多重 value[x] (deceasedBoolean + deceasedDateTime 等、`認識できない
  プロパティ 'X'`)
- rng-2 (Range.low > Range.high)
- per-1 (Period.start > Period.end)
- reference-empty (Reference 完全空、ele-1 発火)
- ext-1 (Extension で value[x] と nested extension 両方)
- Reference target-type mismatch (`type` field 明示で observable)
- CodeableConcept slice の system/code discriminator 不一致
- MedicationRequest.medication の unknown system

### 2.3 profile 定義が実際に要求していない項目 / preferred binding 挙動

以下の slug は当初「JP profile が要求している」想定で定義されていたが、
framework fix 後も発火しないことを実測 (2026-07-24 v2) で確認。**HAPI 側の
gap ではなく、profile 側 or spec 側の設計どおり**:

- **JP profile 系** (slug 想定違い、profile 側に該当 constraint 無い):
  - `jp-coverage-identifier-{system,value}-missing` — JP_Coverage は
    identifier に system/value min=1 slice を持たない
  - `jp-medication-code-missing` / `jp-medication-ingredient-drugno-basic` —
    JP_Medication は code min=1 を強制せず (実データでは
    Medication.ingredient.strength min=1 が別 constraint として発火)
  - `jp-organization-identifier-system-missing` — JP_Organization は
    identifier slice に system fixed を持たない
  - `medicationdispense-subject-missing` — MedicationDispense.subject は
    base R4 で 0..1、JP profile も強制せず
  - `person-inactive-valid` — Person は全 field optional
  - **判定訂正 (2026-07-24 v2)**: `jp-condition-code-text-missing` および
    `jp-encounter-ecs-class-system-missing` は初版で「想定違い」と誤記して
    いたが、framework fix 後の再検証で **PASS** することを確認済。
    profile 側に該当 constraint がある (Condition.code.text min=1、
    Encounter.class.system min=1) と判明。「framework fix 前の観測不能」
    が「profile 想定違い」に見えていた事例。前記の §2.2 訂正と同根の失敗
- **preferred binding の挙動どおり** (fhir-test-cases に該当 test あり、
  HAPI は warning に留めるのが正しい):
  - `coding-code-not-in-preferred-binding` — `A definition for CodeSystem X
    could not be found, so the code cannot be validated` warning のみ
  - `codeableconcept-only-text-no-coding` — preferred binding では
    text-only は許容 (required binding element に絞れば error 化するが、
    Observation.code は preferred)
  - `codeableconcept-multiple-codings-none-valid` — 同上、preferred では
    error 不発火
- **HAPI が spec 上正しく check していない mechanism**:
  - `quantity-negative-value-observation` — base FHIR 側に invariant 無し、
    profile-defined `minValueQuantity` を宣言した profile で初めて error 化
    する (fhir-test-cases の `obs-value-min-profile` が実例)。base R4 での
    直接検出は仕様上ない
- **Bundle mode / 環境依存で single-resource 観測不能な mechanism**:
  - Bundle 内 Reference の resolve 失敗 (`Patient/does-not-exist`) —
    single-resource mode で他 resource が同 Bundle に無いため resolve check
    自体が走らない (**contained resource 内の未解決参照 (`#pat-nonexistent`)
    は observable、こちらは case 化済**)
  - `reference-target-profile-mismatch` — 単純 type 違いは
    `reference-type-mismatch` で cover 済、profile-level 違いは緩い制約下で
    再現困難

これらの slug は expected-issues.py に **未使用状態で残置**。将来 HAPI 版
更新や profile 版更新で挙動が変わった場合、または custom check 実装時に
取り込む候補。**「発火しないことを無理に PASS 化する」ためのダミー case は
作らない** (silent-pass を偽造することになるため)。

## 3. Tier 2: Open slicing で silent-pass する制約

対象: profile が `rules=open` の slicing を宣言している要素で、data が
どの slice の discriminator にも一致しない場合に発生する silent-pass。

### 3.1 発生原理

FHIR の Open slicing は「明示された slice の discriminator に一致しない
要素も許容する」設計。HAPI validator は次の挙動をとる:

1. 各 element を各 slice の discriminator (Fixed value / Pattern) と比較
2. どの slice にも一致しない element は
   `[information] この要素はどの既知のスライスとも一致しません` を出力
3. **slice に match しない要素については、slice 内の required binding /
   Fixed display / cardinality の check は全て skip される**

結果として、profile の意図から外れた data でも error/warning は発火せず、
information issue のみが残る = silent-pass。生の validation 結果を
error/warning のみで評価すると見逃す。

### 3.2 分類原則 (最重要)

Tier 2 の information issue が data の非準拠を示すかは、**個別に
per-slice-match で判定**する必要がある。**path 固定の分類は禁止** (「path が
X なら benign」のようなリストで判定すると誤る、同じ path が別 data では
violation になる)。

判定手順:

1. profile 定義 (StructureDefinition) を読み、対象要素の slice 定義を確認。
   実装上の注意:
   - discriminator の **type** を確認する (`value` / `pattern` / `type` /
     `profile`)。判定に使われる制約の探し方が type によって変わる
   - **snapshot が空で differential のみの StructureDefinition がある**
     (例: `StructureDefinition-jp-observation-common.json` は snapshot=[]、
     differential 側に slice 定義)。snapshot と differential の両方を対象に
2. 各 slice の discriminator と Fixed/Pattern 制約を特定。discriminator が
   `value` / `pattern` の場合、判定制約は slice sub-element の `fixed[x]`
   または `pattern[x]` に載る。**FHIR spec の Fixed/Pattern は 12+ 型別
   field 名を持つため、思いつきで 2-3 個指定すると見落とす**。以下を
   whitelist として全対象で grep:
   ```
   fixedUri fixedCode fixedString fixedCanonical fixedInteger fixedBoolean
   fixedDateTime fixedInstant fixedDate fixedId
   patternUri patternCode patternString patternCanonical
   patternCoding patternCodeableConcept patternIdentifier
   patternReference patternQuantity patternPeriod patternRange
   ```
3. data 実物を見て、required slice に match する element が存在するか確認
4. 存在すれば余剰は **benign**、不在なら **violation** (真の silent-pass)

**探索漏れの症状に注意**: Fixed/Pattern 探索の whitelist が不足すると、
「制約が無い」と誤認して benign/violation の判定根拠を **別の (誤った) 説明で
埋めてしまう**。たとえば `patternUri` を見落として「system は Fixed/Pattern
なし (Tier 3 comment のみ)」と結論すると、実際は spec 符号化された制約なのに
「HAPI が position ベースで match しているかもしれない」といった誤った仮説を
発明する結果になる。「見つからない」は「間違った説明を発明する」形で現れる。

**判定例 (短)**: JP-CLINS eCS Observation の identifier に slicing
(discriminator=`value on system`, rules=open) と `resourceIdentifier` slice
(min=1、`.system.patternUri` = JP resourceInstance-identifier URI) が定義され
ている。data が `[JP canonical identifier, 実装内部 identifier]` の 2 個を
持つとき、system value が patternUri と一致する identifier が resource
Identifier slice に match、もう片方は unmatched information。前者で
required slice satisfied のため、後者は benign。data から JP canonical
identifier を外すと、HAPI は resourceIdentifier slice に対する `min=1`
error を発火する (silent-pass ではない)。

第三者が自分のデータに本手順を適用する際、**判定を data の並び順・path 名
だけで固定しないこと**。上記例でも identifier の並びを反転させても match
関係は system value に基づき同じ結果になる (2026-07 実測確認)。

具体的な適用例と実測分布は
[`validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md`](../validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md)
参照 (特定 data set の実測例)。

### 3.3 Tier 2-benign (a): 意図的な多重 coding

**現象**: data が「JP profile 用 coding + HL7 base 用 coding」を意図的に
並置しているとき、各 profile 視点から相手側の coding が余剰 unmatched と
評価される。

**代表例**: `Observation.category` に
`http://terminology.hl7.org/CodeSystem/observation-category` の coding と
`http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS` の
coding を並置している場合:

- JP profile 側 (例: `JP_Observation_Common`) は category の first slice に
  JP CS coding を要求 → data の [1] JP coding が match、[0] HL7 base が unmatched
- HL7 vital-signs auto-profile 側は category に HL7 base
  observation-category coding を要求 → data の [0] HL7 base が match、
  [1] JP が unmatched
- 両 profile が並行評価され、それぞれが「相手側の coding」を
  unmatched information と報告

**判定**: required slice はどちらの profile でも satisfied。余剰は
「両 profile 対応を意図した data 設計」の副作用で、data 側の非準拠ではない。
data 変更で消すには片方の coding を捨てる必要があり、それは別の非準拠を招く。

### 3.4 Tier 2-benign (b): 余剰 identifier

**現象**: profile が `identifier:resourceIdentifier` slice (min=1) を要求し、
slice の `.system` に `patternUri` で明示的な pattern (
`http://jpfhir.jp/fhir/core/IdSystem/resourceInstance-identifier`) が
定義されている要素で、data が JP canonical identifier + 実装内部 identifier
(別 system) を並置すると、system value が patternUri と一致する identifier
が resourceIdentifier slice に match、もう片方が unmatched information と
なる。

**代表例**: JP-CLINS eCS の Observation / Condition / AllergyIntolerance の
identifier。3 種とも `discriminator = value on system` + `slice.system.
patternUri` で同一 pattern。

**判定**: required slice `resourceIdentifier` は data の JP canonical
identifier で satisfied (patternUri による pattern match)、もう片方は
実装内部 ID の余剰で spec 通り Open slicing rules=open の information。
data は準拠。

**§3.2 判定手順を実践した例**: identifier の並び順を反転した data で
validate すると、位置ではなく system value が判定基準であることが確認できる
(2026-07 実測)。JP canonical のみ持つ data は unmatched なし、実装内部
identifier のみ持つ data は `Slice 'Observation.identifier:resourceIdentifier':
minimum required = 1, but only found 0` の error が発火する。→ HAPI は spec
通り value:system discriminator + patternUri で match を判定しており、benign
判定は position ベースではない。

### 3.5 Tier 2-violation: 真の silent-pass

**現象**: profile が要求する slice の discriminator (Fixed system / Pattern)
に data が一致していない。slice 内の required binding や Fixed display は
全て skip され、実質的な非準拠が silent で見逃される。

**代表例**: JP-CLINS 検体検査 profile
(`JP_Observation_LabResult_eCS`) を宣言している Observation で、
`code.coding` に `JLAC10 CoreLabo` slice が要求する 17 桁 code + JLAC
system を持たず、LOINC-only で emit している場合。CoreLabo slice に match
せず、Open slicing のため error にならず information のみ。

同 pattern は次の要素でも発生:

- `DiagnosticReport.code.coding`
- `MedicationRequest.medication.ofType(CodeableConcept).coding`
- `Procedure.code.coding`
- `Condition.bodySite.coding`

**対処**: data 側で各 slice が定義する Fixed value / Pattern (system /
display / code) を **StructureDefinition から機械的に取得**して strict に
emit する。JP-CLINS の Fixed display には英数字ベース (`WBC` / `K` / `AST`
など) と日本語ベース (`HBs抗原(定性)` / `血液型-ABO` / `HCV核酸増幅検査
(定量)` など) が混在するため、slice ごとの Fixed 値を手写しでコピーすると
事故が起きる (半角/全角、括弧種類、句読点の差で match しない)。SD parser
(`fhir.resources` / `jsonpath` 等) で slice の `fixed*` / `pattern*` field を
機械取得する pipeline を構築するのが安全。JP-CLINS 検体検査の場合は
JLAC10/11 の 17 桁 code + JLAC system を primary に置く。

### 3.6 計測: per-issue と per-resource

情報 issue の集計は 2 つの軸で行える:

- **per-issue**: validator が発する message 数。運用 log 監視や UX 上の
  noise 量測定に使う
- **per-resource** (unique resource 数): 1 resource が「compliant か
  non-compliant か」を数える。準拠率の指標にはこちらを使う

同じ非準拠を coding 多く積むほど per-issue は膨らむため、
`matched / (matched + unmatched)` の適合率を追う場合は per-resource が適切。

汎用の集計 recipe (message pattern 日/英対応、element path 正規化、
resourceType / profile / (resourceType, path) 3 軸集計) は
[`docs/output-guide.md §4.5`](output-guide.md) 参照。集計 recipe は
Tier 2-benign と Tier 2-violation を区別せず生 count で返すため、
§3.2 の判定手順で切り分ける必要がある。

### 3.7 症状が似ているが Tier 2 ではないもの

集計 recipe は「どの既知のスライスとも一致しません」message を機械的に
拾うため、Open slicing 由来ではない profile 定義の別種問題も混じって
検出される。以下は同 message が出るが Tier 2 (Open slicing 由来) ではない
例:

**profile 側の未 named type slice への fall-through**:
polymorphic 型 (例: `MedicationAdministration.dosage.rate[x]`) で、profile が
`rateRatio` slice のみ named 定義し、data が `rateQuantity` を使うと、
named slice のいずれにも該当せず fall-through して同 message が出る。
しかし原因は Open slicing ではなく **profile が特定 type slice のみ named
定義した設計**。data は type 制約 (SimpleQuantity 等) を満たしていれば準拠。

集計 recipe の生 count には Tier 2 と本節の症状が混在する。厳密な Tier 2
集計をするには profile 定義側の slicing 種類 (discriminator が `type` か
`value on system` か等) で切り分ける必要があるが、実運用上は
「symptom として同じ、原因が違う」ことを理解した上で per-slice-match の
判定手順で個別に判断すれば十分。

### 3.8 実測分布と test-cases での監視

**実測分布**: 特定の合成 EHR data set (clinosim v31、1,161 Bundle) を
HAPI 6.9.12 + JP Core/JP-CLINS/MHLW 完全版 load 済 fhirserver 構成下で
validate した測定では、slice unmatched information は **全 issue の約 22%**、
そのうち **約 19% (全 issue の約 4%) が Tier 2-violation** (真の silent-pass)、
残りが Tier 2-benign および §3.7 の症状類似 だった。絶対数と個別 path
分布は
[`validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md`](../validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md)
参照。

**留意**: この割合は特定の data と特定の validator 構成に依存する。data の
性質 (どの profile を宣言しているか、multi-coding を採るか、identifier 設計
など) が変われば大きく変動する。外部への引用時は必ず条件セット
(data、profile 版、validator 構成) と共に示すこと。

**test-cases framework での監視**:
[`test-cases/expected-issues.py`](../test-cases/expected-issues.py) に
以下 slug を登録している:

- `tier2-violation-codeable-slice-unmatched`: violation pattern の代表 case
  (JP-CLINS 検体検査)。**silent-pass の再現を assert** する (message が
  確かに出ていること = 検出手段が生きていることの記録)
- `tier2-benign-multi-coding-category`: benign (a) が誤って error/warning
  化していない ことを assert
- `vital-signs-auto-profile-active`: positive control。HAPI が LOINC
  vital-sign code から HL7 vital-signs profile を自動適用する挙動が有効で
  あることを、profile URL が message に現れることで検出

validator 版更新や profile 版更新で挙動が変わったとき、reconcile pass/fail
の差分として現れる。

## 4. Tier 3: IG 本文の散文にのみ存在する制約

**現状: fhir-jp-validator は Tier 3 の check を一切実装していない**。
本節は spec から抽出した対象一覧であり、実装は今後の課題。

Tier 3 の制約は FHIR StructureDefinition の invariant として符号化されて
おらず、IG 本文の comment / definition / description に散文で記述されて
いる。**どの FHIR validator も自動検出できない**。準拠を担保するには data
生成側または custom validator 側で個別に check を実装する必要がある。

以下は `JP_Observation_LabResult_eCS` から抽出した例 (網羅的ではない):

| 制約 | 内容 |
|---|---|
| display / text の文字種 | 半角カタカナ・全角空白・制御文字を含んではいけない。カタカナは全角、英数字記号と空白は半角。全角ギリシャ文字・全角ローマ数字は可。機種依存文字禁止 |
| LocalCode の display | 空白を含まない、なるべく長い文字列名称を推奨 |
| LocalCode の code | 英数字・ハイフン・アンダーバーのみ。異なる検体材料に同項目コードがある場合は `検査項目コード_検体材料コード` (例 `0198394_082`) |
| コーディング適用規則 | LocalCode は全検体検査で常に必須。指定検査 43 項目・指定感染症 5 項目に該当するなら共有項目 JLAC コードも必須。非該当なら MEDIS 一般項目を強く推奨、不可能なら未標準化コードが必須 |
| `hasMember` | 電子カルテ情報共有サービスで5情報を送信する場合は使用しない |
| `meta.tag:lts` | 指定感染症検査の場合のみ設定できる |

他の JP Core / JP-CLINS profile にも同種の散文制約が存在する。JP FHIR
仕様書の各 profile の comment / description を読むことでしか特定できない。

Tier 3 check の実装候補 (優先度は費用対効果で判断される):

- **文字種チェック** (最も汎用、実装容易): 全 CodeableConcept.text /
  Coding.display / narrative に対する正規表現ベースの check。実装コスト低、
  適用範囲広
- **LocalCode コード形式チェック**: 特定 profile の CodeableConcept slice
  に対する code 形式 check
- **コーディング適用規則チェック**: 指定検査 43 項目 + 指定感染症 5 項目の
  list を保持し、Observation.code に応じて JLAC/MEDIS 有無を判定

## 5. 今後の対応予定

現時点で未実装だが、fhir-jp-validator に組み込む方向で検討している改善。
第三者ユーザの利用場面で有用性が高いと想定される順に記述。

- **Tier 2-benign 情報の suppress option**: 生の validation 出力には Tier
  2-benign の information issue が多数混じる (§3.8 の測定例では全 issue の
  約 18%)。data 準拠を評価する際にはノイズとなるため、CLI 側で filter する
  option (例: `--suppress-slice-unmatched-info`) を提供する予定。benign
  判定条件は data 依存 (§3.2) のためユーザ側で whitelist 設定を持たせる
  形が現実的
- **Tier 3 custom check の段階的実装** (§4 参照): 文字種チェックが最初の
  候補 (実装コスト低、適用範囲広)。LocalCode コード形式、コーディング適用
  規則が続く
- **Tier 2-violation の継続監視サポート**: 適合率 (`matched / (matched +
  unmatched)`) を測定した状態から、その値の baseline 逸脱を検出する運用
  向けの集計 subcommand。現状は §3.6 の recipe を手動で回す形
