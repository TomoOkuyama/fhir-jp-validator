# JP-CLINS validation の既知の限界

本ドキュメントは、JP Core 1.2.0 / JP-CLINS 1.12.0 を HAPI Validator +
terminology server で検証する場合に **何が検出され、何が検出されないか** を
整理する。想定読者は、自身の FHIR data を JP-CLINS 準拠かどうか確認したい
実装者・ベンダー・システム連携担当者。

fhir-jp-validator が対応している範囲と、まだ対応していない範囲の両方を
記述する。

## 1. 何が検出され、何が検出されないか (要旨)

FHIR profile の制約は、検出のされ方によって 3 層に分けられる。層ごとに
検出手段が異なり、fhir-jp-validator がどこまでカバーできるかも変わる。

| 層 | 制約の性質 | 検出手段 | fhir-jp-validator の対応 |
|---|---|---|---|
| Tier 1 | FHIR spec に符号化されており、閉じた slicing・cardinality・Fixed value・required binding など HAPI が確実に発火するもの | HAPI standard | ✅ 標準構成で検出 |
| Tier 2 | FHIR spec に符号化されているが、Open slicing (`rules=open`) により slice match しなかった場合に severity=information に留まるもの | HAPI (information issue の集計) | ⚠️ 集計 recipe と test-cases で可視化、data-side 修正の判断材料を提供 |
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

1. profile 定義 (StructureDefinition) を読み、対象要素の slice 定義を確認
2. 各 slice の discriminator と Fixed/Pattern 制約を特定
3. data 実物を見て、required slice に match する element が存在するか確認
4. 存在すれば余剰は **benign**、不在なら **violation** (真の silent-pass)

具体的な判定例と背景解説は
[`validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md`](../validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md)
参照。

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

**現象**: profile が `identifier:resourceIdentifier` slice (min=1、system を
comment で JP resourceInstance-identifier に指定) を要求する要素で、data が
`[JP canonical identifier, 実装内部 identifier]` の 2 個並置している場合、
`identifier[1]` が unmatched。

**代表例**: JP-CLINS eCS の Observation / Condition / AllergyIntolerance の
identifier。3 種とも同一 pattern の slice 定義。

**判定**: required slice `resourceIdentifier` は identifier[0] で satisfied、
[1] は実装内部 ID の余剰。data は準拠。

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

**対処**: data 側で slice が要求する system + display (英語 abbrev や
Fixed value) を strict に emit する。JP-CLINS 検体検査の場合は
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
named slice に fall-through して同 message が出る。しかし原因は Open slicing
ではなく **profile が特定 type slice のみ named 定義した設計**。data は
type 制約 (SimpleQuantity 等) を満たしていれば準拠。

集計 recipe の生 count には Tier 2 と本節の症状が混在する。厳密な Tier 2
集計をするには profile 定義側の slicing 種類 (discriminator が `type` か
`value on system` か等) で切り分ける必要があるが、実運用上は
「symptom として同じ、原因が違う」ことを理解した上で per-slice-match の
判定手順で個別に判断すれば十分。

### 3.8 実測分布と test-cases での監視

**実測分布**: 特定の合成 EHR data set (clinosim v31、1,161 Bundle) を
HAPI 6.9.12 + JP Core/JP-CLINS/MHLW 完全版 load 済 fhirserver 構成下で
validate した測定では、全 issue に対する slice unmatched information の
割合が約 22%、うち約 4 分の 1 (全 issue の約 4%) が Tier 2-violation
(真の silent-pass)、残りが Tier 2-benign および §3.7 の症状類似だった。
絶対数と個別 path 分布は
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

## 5. 中期検討事項 (内部向け)

以下はプロジェクトの内部的な運用改善候補。docs 読者への直接影響はないが、
記録として残す。

- **Tier 2-benign 情報の suppress option**: 特定の condition で benign と
  判定できる information issue を CLI 側で filter する option (例:
  `--suppress-slice-unmatched-info`)。benign 判定条件が data 依存のため
  ユーザ側 whitelist 設定を持たせる形が現実的
- **slice 適合率 baseline monitoring**: 移行が完了した後は Tier 2-violation
  分布は low base line 維持となる。base line 逸脱時に alarm する運用に
  移ることを generator 側の validation loop に組み込む価値がある
- **Tier 3 custom check の段階的実装**: 文字種チェックが最初の候補
  (実装コスト低、適用範囲広)
