# FHIR (JP Core / JP-CLINS) データ生成 フィードバック (第 2 回)
## Session 55 fix 反映後の regen (JP p=1000 seed=300) 検証結果

**対象**: FHIR R4 データ生成器チーム (clinosim)
**検証環境**: HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal) + JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0 / LOINC 2.82 / SNOMED CT International 2026-06-01
**検証データ**: 2026-07-17 生成 fhir_r4/ (26 NDJSON、**全 437,669 リソース**、589MB)
**検証日**: 2026-07-17
**検証所要**: rest 25 種 7.4 分 + Observation 17.9 分 = **25.3 分完走** (0 failed)

## 全体傾向 (前回比較)

| 指標 | 前回 (2026-07-16, 179k sample) | 今回 (2026-07-17, 全 437k) | 変化 |
|---|---:|---:|---:|
| 検証対象 | 179,195 リソース | **437,669 リソース** | 2.4x (フルセット) |
| 1+ error あり | 116,452 (65%) | **218,415 (~50%)** | **-15pp** |
| errors 総数 | 399,657 | 584,906 | – (規模差あり) |
| warnings 総数 | 202,527 | 490,424 | – (規模差あり) |

**大局評価**: fail 率 65% → 50% に改善。ただし Observation の fail 率は 70% → 70% で**ほぼ横ばい**であり、この regen で当てた 3 fix (#185/#187/#190) が**想定通り効いていない or 副作用を生んでいる**。以下、fix 別の実測状況と、そこから見える対処を priority 順にまとめます。

---

## 【Session 55 fix 実測結果サマリ】

| PR | 対象 | 前回件数 | 今回件数 | 判定 | メモ |
|---|---|---:|---:|:---:|---|
| #179 CareTeam.category → SNOMED 735320007 | LA27976-8 unknown | ~1,913 (推定) | **3,781** ("735320007" unknown) | ❌ | code 差替済だが fhirserver の SNOMED CT International 2026-06-01 に 735320007 が未収録として reject。SNOMED 版差 or code 選定ミス。§【要検討 A】参照 |
| #181 ServiceRequest 空 code coding[] 除外 | code 未設定 | ~24,364 | **131** (rest ServiceRequest err 率 0.4%) | ✅ | ほぼ完全解消 |
| #183 UCUM Quantity.code 4 site | Quantity.code min=1 | 25,532 | **6,179** (IU 3,386 + mcg 2,793) | 🟡 | 76% 削減。残る IU / mcg など**特殊 UCUM 単位が未対応**。§【最優先 1】参照 |
| #185 Observation.referenceRange extension URL | 未知 extension URL | 5,687 | **31,006** | ❌ | fix 後の URL `http://jpfhir.jp/fhir/core/StructureDefinition/JP_Observation_ReferenceRangeSource` が引き続き未知として reject。JP-CLINS 1.12.0 の StructureDefinition に存在しない URL。§【最優先 2】参照 |
| #187 Observation identifier + meta.lastUpdated | 必須要素欠落 | ~47,000 | **31,172** (identifier slice) | 🟡 | 34% 削減。identifier 追加は効いた模様だが `resourceIdentifier` slice が別途未充足 |
| #190 Observation.category HL7+JP dual coding | 単一 coding 誤り | 112,000 | **286,168** (dual mismatch 両方向 + category max=1 違反) | ❌ | dual coding にした結果、**両方の CodeSystem に対して単独 slice binding が違反**となり、加えて `category:laboratory.coding max=1` を超過。fix 意図と profile 制約が矛盾。§【最優先 3】参照 |
| #195 Observation.specimen 検体 Specimen emit | specimen reference 欠落 | 5,687 | **0** (Specimen 31,047 件、err 率 0%) | ✅ | 完全解消 |

merge 待ち PR (今回この regen では未反映想定):
- #192 Condition/AI/MR eCS min=1 → 実測: Condition 6,235 件 (100%) が引き続き identifier / lastUpdated / display 欠落。詳細 §【最優先 4】
- #197 MR dosageInstruction JP-CLINS 用法拡張 + R5020 → 実測: MedicationRequest 1,870 件 (100%) 継続。詳細 §【最優先 5】
- #199 FHIR resource.id spec 準拠 (P0) → データ側では 0 error。iris4h-ai import 想定通り通るはず

---

## 【最優先 1】UCUM 特殊単位: IU / mcg / {INR} 等

**影響**: MedicationAdministration 中 6,179 件 (9.6%)。

### 現状 (抜粋)

```
system'http://unitsofmeasure.org'で未知のコード'IU'    (3,386 件)
system'http://unitsofmeasure.org'で未知のコード'mcg'   (2,793 件)
```

### 原因

`IU`, `mcg` は日常的に医療現場で使われるが **UCUM の正式 code ではない**。UCUM で許容されるのは:

- `mcg` → **`ug`** (micro-gram)
- `IU` → **`[iU]`** (international unit)

### あるべき姿

```json
"dose": {
  "value": 500,
  "unit": "mcg",              ← human display はそのまま許容
  "system": "http://unitsofmeasure.org",
  "code": "ug"                ← ★ 機械 code は UCUM 正式表記
}
```

同様に `IU` → `[iU]`、`mEq` → `meq`、`mmol/L` → `mmol/L` (これは OK)、`%` → `%` (OK)、`mg/dL` → `mg/dL` (OK) と、単位ごとに変換テーブルが必要。

### 対処

生成器の Quantity ヘルパーに UCUM code マッピングテーブルを追加。`unit` 文字列 → UCUM `code` の対応表:

```
mcg  → ug
IU   → [iU]
mEq  → meq
IU/L → [iU]/L
mmHg → mm[Hg]
```

---

## 【最優先 2】Observation.referenceRange の extension URL

**影響**: Observation 31,006 件 (11.8%)。**#185 fix 後に増加**。

### 現状

fix 適用後の extension URL:
```json
"referenceRange": [{
  "extension": [{
    "url": "http://jpfhir.jp/fhir/core/StructureDefinition/JP_Observation_ReferenceRangeSource",
    ...
  }]
}]
```

### validator 側の反応

```
extension http://jpfhir.jp/fhir/core/StructureDefinition/JP_Observation_ReferenceRangeSource は未知であり、
ここでは許可されていません
Observation.referenceRange.extension: 最大許容値 = 0、見つかった値 = 1
```

つまり:
1. この URL は **JP-CLINS 1.12.0 の StructureDefinition カタログに存在しない**
2. JP_Observation_LabResult_eCS profile は `referenceRange.extension` の max を 0 に設定 (追加拡張禁止)

### 原因の仮説

fix の URL が誤り。正しくは以下いずれかの可能性:
- `http://jpfhir.jp/fhir/eCS/Extension/StructureDefinition/JP_Observation_ReferenceRangeSource` (eCS namespace)
- `http://jpfhir.jp/fhir/core/Extension/JP_Observation_ReferenceRangeSource` (Extension namespace)
- あるいは JP-CLINS 1.12.0 に該当 extension が未定義 → **仕様側に extension 定義を追加する PR が別途必要**

### 対処 (要仕様確認)

1. jpfhir-terminology 2.2606.0 と JP-CLINS 1.12.0 パッケージ内で正式な URL を検索
2. profile 側で `referenceRange.extension` の max を >=1 に緩めるか、この extension を使わない設計に戻す

`grep -r "ReferenceRangeSource" jp_core/ tx-server-build/terminology/` で該当 StructureDefinition を探して URL を確認するのが最速です。

---

## 【最優先 3】Observation.category dual coding の profile 適合性

**影響**: Observation 全体で 286,168 件 (fix #190 適用後、複数 error が per-resource 発生)。

### 現状 (#190 適用後)

```json
"category": [{
  "coding": [
    {"system": "http://terminology.hl7.org/CodeSystem/observation-category",
     "code": "laboratory", "display": "Laboratory"},
    {"system": "http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS",
     "code": "laboratory", "display": "Laboratory"}
  ]
}]
```

### validator 側の反応

```
(A) 値は 'http://terminology.hl7.org/CodeSystem/observation-category' ですが、
    'http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS' でなければなりません       (182,662 件)
(B) 値は 'http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS' ですが、
    'http://terminology.hl7.org/CodeSystem/observation-category' でなければなりません                  (103,670 件)
(C) Observation.category:laboratory.coding: 最大許容値 = 1、見つかった値 = 2                            (31,172 件)
```

### 診断

JP_Observation_LabResult_eCS profile は `category` を複数 slice に分けており、
- 一部 slice は **HL7 CodeSystem を強制**
- 別 slice は **JP CodeSystem を強制**
- かつ **各 slice の coding max = 1**

`category` を単一に、各 coding を 1 個ずつ複数の category 要素として持たせる必要があります。**dual coding を 1 category にまとめたのが問題**。

### あるべき姿

```json
"category": [
  {"coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
    "code": "laboratory", "display": "Laboratory"
  }]},
  {"coding": [{
    "system": "http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS",
    "code": "laboratory", "display": "Laboratory"
  }]}
]
```

= **2 個の category 要素、各 category に単一 coding**。

### 対処

`category` 生成ロジックで、`coding[]` にまとめず、**category 配列に 2 要素**として emit する。

---

## 【最優先 4】Condition eCS 必須要素 (PR #192 未 merge)

**影響**: Condition 6,235 件 (100%)。

前回と同一パターン、#192 未 merge のため状況変わらず。PR 内容通り修正すれば解消見込み。

### 実測 (per-resource 全て発生)

```
Condition.identifier: 最小必要値 = 1、見つかった値 = 0                          (6,235 件)
Slice 'Condition.identifier:resourceIdentifier': minimum required = 1, but only found 0  (6,235 件)
Condition.meta.lastUpdated: 最小必要値 = 1、見つかった値 = 0                    (6,235 件)
Condition.clinicalStatus.coding.display: 最小必要値 = 1、見つかった値 = 0        (6,235 件)
Condition.verificationStatus.coding.display: 最小必要値 = 1、見つかった値 = 0    (6,235 件)
Slice 'Condition.code.coding:medisRecordNo': minimum required = 1, but only found 0     (6,235 件)
```

### あるべき姿

```json
{
  "resourceType": "Condition",
  "id": "cond-ENC-...",
  "meta": {
    "profile": ["http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Condition_eCS"],
    "lastUpdated": "2026-07-17T00:00:00+09:00"     ← 必須
  },
  "identifier": [{                                  ← 必須 (resourceIdentifier slice)
    "system": "urn:oid:1.2.392.100495.20.3.51.<患者ID>",
    "value": "cond-..."
  }],
  "clinicalStatus": {"coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
    "code": "active",
    "display": "Active"                             ← display 必須
  }]},
  "verificationStatus": {"coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
    "code": "confirmed",
    "display": "Confirmed"                          ← display 必須
  }]},
  "code": {"coding": [
    {"system": "http://jami.jp/CodeSystem/medis-master-<version>", "code": "<MEDIS-recno>", "display": "..."},   ← medisRecordNo slice 必須
    {"system": "http://hl7.org/fhir/sid/icd-10", "code": "...", "display": "..."}
  ]}
}
```

---

## 【最優先 5】MedicationRequest eCS 必須要素 (PR #197 未 merge)

**影響**: MedicationRequest 1,870 件 (100%)。

### 実測

```
MedicationRequest.identifier: 最小必要値 = 3、見つかった値 = 2                                  (1,870 件)
Slice 'MedicationRequest.identifier:requestIdentifier': minimum required = 1, but only found 0  (1,870 件)
MedicationRequest.meta.lastUpdated: 最小必要値 = 1、見つかった値 = 0                            (1,870 件)
Dosage.extension: 最小必要値 = 1、見つかった値 = 0
Slice 'Dosage.extension:periodOfUse' for extension 'http://jpfhir.jp/fhir/core/Extension/StructureDefinition/JP_Medication_...'
Constraint failed: validUsage-MedicationUsage-codesystem: 'R5020:厚労省用法コード ...'
```

**PR #197 の実装で解消想定**。

---

## 【最優先 6】ICD-10 code の未知エントリ (S72.00, E11.65)

**影響**: rest 側全体で 7,652 件 (S72.00: 4,052 / E11.65: 3,600)。

### 現状

fhirserver は `http://hl7.org/fhir/sid/icd-10` version `2019-covid-expanded` を提供しているが、`S72.00` (Fracture of unspecified part of neck of femur, closed) と `E11.65` (Type 2 diabetes mellitus with hyperglycemia) が unknown。

### 診断

ICD-10 の版差。`S72.00`, `E11.65` は **ICD-10-CM (US 版)** の code。fhirserver に load されている ICD-10 (WHO 国際版) には存在しない。

### 対処

日本での ICD-10 使用実態に合わせ、以下いずれか:

1. 生成器で ICD-10 code を **ICD-10 (WHO) 準拠**に統一 (JP の医療現場で使われる版)
2. ICD-10-CM を使う場合は system URI を `http://hl7.org/fhir/sid/icd-10-cm` に変更
3. `.65` のような追加桁は WHO 版には無いため、`S72.0`, `E11.6` に丸める

日本 EHR の実データを模すなら **国際版 ICD-10 (`S72.0`, `E11.6`) 採用が妥当**。

---

## 【最優先 7】Observation vital-signs BP profile 違反 (新規発覚)

**影響**: 14,474 件 の Observation で発生。

### 現状 (推定)

Observation.code に LOINC `85354-9` (Blood pressure) を持つリソースに対し、HAPI validator は **自動的に `http://hl7.org/fhir/StructureDefinition/bp` profile を適用**する。この profile は以下を要求:

- `component[]` に 2 要素以上 (systolic + diastolic)
- `component:SystolicBP` slice (LOINC `8480-6`)
- `component:DiastolicBP` slice (LOINC `8462-4`)

現在の生成データは LOINC 85354-9 を使いつつ component を持っていない、または不一致 code を使っている模様。

### 実測 (per-resource)

```
Observation.component: 最小必要値 = 2、見つかった値 = 0                (14,474 件)
Slice 'Observation.component:SystolicBP': minimum required = 1        (14,474 件)
Slice 'Observation.component:DiastolicBP': minimum required = 1       (14,474 件)
BPCode: magic LOINC code 85354-9 required, but not found              (14,474 件)
```

`BPCode: magic LOINC code 85354-9 required, but not found` は逆で、**別 code の Observation なのに bp profile が誤って適用された可能性**もあります。

### あるべき姿 (BP を表現する場合)

```json
{
  "resourceType": "Observation",
  "meta": {"profile": ["http://hl7.org/fhir/StructureDefinition/bp"]},
  "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel"}]},
  "component": [
    {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
     "valueQuantity": {"value": 120, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}},
    {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]},
     "valueQuantity": {"value": 80, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}}
  ]
}
```

### 対処

生成器で LOINC 85354-9 (bp panel) を出す Observation では必ず component 2 個を emit。 逆に、component を持たない単発 systolic (LOINC 8480-6) や diastolic (LOINC 8462-4) の Observation は 85354-9 を使わず個別 code のみ使用。

---

## 【中優先 A】Patient で example URL CodeSystem 使用

**影響**: Patient 577 件 (100%)。

### 現状

```json
"extension": [{
  "url": "...",
  "valueCodeableConcept": {"coding": [{
    "system": "http://clinosim.example.org/CodeSystem/occupation-category",
    "code": "..."
  }]}
}]
```

### validator 反応

```
このコンテキストでのExample URLは許可されていません
(http://clinosim.example.org/CodeSystem/occupation-category)
```

### 対処

- 職業カテゴリの適切な CodeSystem を選定 (`http://terminology.hl7.org/CodeSystem/v3-EmployeeJobClass` or 日本標準職業分類の OID)
- 検証パス用データにはダミー URL を使わない (実データを模す方針と整合)

同様に `http://clinosim.example.org/CodeSystem/jp-care-level` も 66 件 warning で使用中。

---

## 【中優先 B】DiagnosticReport.category:first slice

**影響**: DiagnosticReport 2,265 件 (85% fail 率)。**新規発覚**。

### 実測

```
Slice 'DiagnosticReport.category:first': minimum required = 1, but only found 0
```

JP_DiagnosticReport profile が category slice を要求している。「first」slice の specific binding を確認して追加。

---

## 【noise 判定】対処不要な items

| 内容 | 件数 (rest+obs) | 判定 |
|---|---:|---|
| `dom-6` Best Practice narrative missing | 349k warning | 不要 (バリデータ側 `-best-practice ignore` で抑止済み) |
| `no Display Names for language ja` info | 大量 | 不要 (SNOMED/LOINC に日本語 translation なし) |
| `CodeSystem urn:oid:1.2.392.200119.4.1005 は未知` | 31k warning | 不要 or `jpfhir-terminology` 側の登録待ち (医療機関 OID) |
| `warn-localCode-observation-laboresult` | 31k warning | 情報のみ (電子カルテ情報共有サービス送信時のみ要件) |
| `master-HOT7` CodeSystem fragment 未知 code | 29k warning | fragment 判定なので許容範囲。医薬品 code の完全 load 不可 |

---

## 全体所感と次サイクル提案

**達成**:
- 全体 fail 率 65% → 50% (**-15pp**) — 大きな前進
- #181 (ServiceRequest), #195 (Specimen), #199 (id 準拠) は完全解消
- #183 (UCUM), #187 (Obs identifier) は 34-76% 削減

**課題 (次サイクル最優先)**:
1. **#190 Observation.category dual coding が profile 制約と矛盾** — 単一 category に coding[] 2 個ではなく、category 2 要素に分離する必要 (最大インパクト、282k error 減の余地)
2. **#185 Observation.referenceRange extension URL** — 正しい URL 選定 or 使わない設計に (31k error 減)
3. **#179 CareTeam SNOMED 735320007** — fhirserver で unknown 判定。code 差替か SNOMED 版揃え (3.8k error 減)
4. **PR #192 (Condition eCS) merge** — 37k error 減
5. **UCUM 特殊単位マッピング (IU, mcg 等)** — 6.2k error 減

上記全対処で見込み fail 率: 50% → **~25%** (218k → ~110k)。

**新規 issue (次サイクル対応候補)**:
- ICD-10 版統一 (7.6k)
- BP profile 準拠 component emit (14k)
- Patient 職業 CodeSystem 見直し (577)
- DiagnosticReport.category:first slice (2.3k)

上記対応でさらに **~10% pp 改善** し、最終 fail 率 ~15% 到達見込み。
