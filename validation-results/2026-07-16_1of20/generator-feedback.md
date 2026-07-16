# FHIR (JP Core / JP-CLINS) データ生成 フィードバック
## 実データに基づく「現状 → あるべき姿」レポート

**対象**: FHIR R4 データ生成器チーム
**検証環境**: HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal) + JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0 / LOINC 2.82 / SNOMED CT International 2026-06-01
**検証データ**: 実データ 3.58M リソース の 1/20 サンプル (179,195 リソース、26 種別)
**検証日**: 2026-07-16

## 全体傾向

| 指標 | 値 |
|---|---:|
| 検証対象 | 179,195 リソース |
| 1+ error あり | 116,452 (**65%**) |
| errors 総数 | 399,657 |
| warnings 総数 | 202,527 |

**構造・型は概ね正しい** (parse は全リソースで成功) が、**JP-CLINS eCS プロファイル (JP_Condition_eCS 等) が要求する必須要素・ slice 制約の一部が体系的に未充足**。多くは data 生成テンプレートの共通ヘルパー修正で複数種別を一括改善できる性質のものです。

以下、実データから抜粋した具体例と「あるべき姿」を priority 順に。

---

## 【最優先 1】MedicationAdministration `dosage.dose` — Quantity.code 欠落

**影響**: 全 26,626 件中 24,780 件 (93%) が該当。fail 率 100%。

### 現状 (抜粋: `mar-ENC-POP-000017-816402801351-00000`)

```json
"dosage": {
  "text": "325.0mg DAILY",
  "dose": {
    "value": 325.0,
    "unit": "mg",
    "system": "http://unitsofmeasure.org"
  }
}
```

### FHIR (`Quantity`) 仕様と JP profile 要求

`Quantity` 型は `value` / `unit` (人間可読) / `system` (code system URI) / `code` (機械可読) の 4 要素構造。JP_MedicationAdministration_eCS は `code` を必須にしている (`Quantity.code: 最小必要値 = 1`)。

### あるべき姿

```json
"dosage": {
  "text": "325.0mg DAILY",
  "dose": {
    "value": 325.0,
    "unit": "mg",
    "system": "http://unitsofmeasure.org",
    "code": "mg"
  }
}
```

`code` は UCUM の単位 code (mL / mg / g / L / mmol 等) を使用。 `unit` は表示用文字列、`code` は照合用の機械 code。両者は多くの場合同じ文字列だが、必ず両方セットする。

### 対処

生成器の `Quantity` 生成ヘルパーで、`system=http://unitsofmeasure.org` を出す際は必ず `code` フィールドも同じ (or 対応する UCUM) 値でセット。 **同じ問題が `MedicationRequest.dosageInstruction[N].doseAndRate[N].doseQuantity` にも波及**しているので合わせて対応 (下記参照)。

---

## 【最優先 2】Condition / AllergyIntolerance / MedicationRequest — eCS 必須要素の体系的欠落

**影響**: Condition 3,142 件 (100%)、AllergyIntolerance 44 件 (100%)、MedicationRequest 824 件 (100%)。

3 リソース種類で同じ pattern の欠落が発生しており、生成テンプレートの共通改善で一括修正可能です。

### 現状 (Condition: `cond-ENC-POP-000002-393907799112-primary`)

```json
{
  "resourceType": "Condition",
  "id": "cond-ENC-POP-000002-393907799112-primary",
  "meta": {
    "profile": [
      "http://jpfhir.jp/fhir/core/StructureDefinition/JP_Condition",
      "http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Condition_eCS"
    ]
    /* ❌ lastUpdated がない */
  },
  /* ❌ identifier がない */
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "resolved"
      /* ❌ display がない */
    }]
  },
  "verificationStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
      "code": "confirmed"
      /* ❌ display がない */
    }]
  },
  "code": {
    "coding": [
      {
        "system": "http://hl7.org/fhir/sid/icd-10",
        "code": "S93.4"
        /* ❌ 1 個目に display がない */
      },
      {
        "system": "http://hl7.org/fhir/sid/icd-10",
        "code": "S93.4",
        "display": "Sprain and strain of ankle"
      }
    ],
    "text": "足首の捻挫及びストレイン"
  }
}
```

### JP_Condition_eCS が要求する形

```json
{
  "resourceType": "Condition",
  "id": "cond-ENC-POP-000002-393907799112-primary",
  "meta": {
    "profile": ["...JP_Condition_eCS"],
    "lastUpdated": "2026-04-15T20:53:00+09:00"   /* ✅ 追加 */
  },
  "identifier": [                                  /* ✅ 追加 */
    {
      "system": "http://example-hospital.jp/fhir/condition-id",
      "value": "cond-ENC-POP-000002-393907799112-primary"
    }
  ],
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "resolved",
      "display": "Resolved"                        /* ✅ 追加 */
    }]
  },
  "verificationStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
      "code": "confirmed",
      "display": "Confirmed"                       /* ✅ 追加 */
    }]
  },
  "code": {
    "coding": [
      {
        "system": "http://hl7.org/fhir/sid/icd-10",
        "code": "S93.4",
        "display": "Sprain and strain of ankle"    /* ✅ 追加 (両方の coding に) */
      }
      /* 重複 coding は 1 個にまとめて OK */
    ],
    "text": "足首の捻挫及びストレイン"
  }
  /* ... 他フィールド ... */
}
```

### AllergyIntolerance も同種欠落 (`allergy-POP-000021-1`)

同じく `identifier`、`meta.lastUpdated`、`clinicalStatus.coding.display`、`verificationStatus.coding.display` に加えて **`code.coding.display`** も欠落。

### MedicationRequest (`ORD-ENC-POP-000002-393907799112-ED-T4`)

`identifier` と `meta.lastUpdated` は既に有り (OK) だが、以下が欠落:
- `dosageInstruction[N].extension` (JP-CLINS 固有の用法拡張が profile で必須)
- `dosageInstruction[N].doseAndRate[N].doseQuantity` に `code` 欠落 (最優先 1 と同種)
- `Constraint failed: validUsage-MedicationUsage-codesystem` — 「R5020:厚労省用法コード（電子処方箋）かまたはダミー用法コードのどちらか一方だけが必ず使われている」

### 対処

生成テンプレートの eCS プロファイル対応リソース (Condition, AllergyIntolerance, MedicationRequest, Observation 等) 共通に:
1. `meta.lastUpdated` を生成時タイムスタンプで必ず埋める
2. `identifier[0]` を必ず付与 (施設内一意 ID)
3. code system を持つ全 `coding` に `display` を付与 (英語 or 日本語、正式表示名)
4. eCS 固有の必須 extension (`JP_MedicationDosage_eCS` の用法拡張等) を profile 準拠で追加

---

## 【最優先 3】Observation `category` — profile 別に CodeSystem を切り替える必要

**影響**: 111,623 件 (Observation 全体 115,718 中の 96%)。**双方向 error が存在** (どちらを使っても他方の profile で怒られる)。

- 66,321 件: 「値は `http://terminology.hl7.org/CodeSystem/observation-category` ですが、`http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS` でなければなりません」
- 45,302 件: 逆方向 (JP → HL7)

### 現状 (JP_Observation_LabResult_eCS を meta.profile に持つ検体検査 Observation)

```json
{
  "resourceType": "Observation",
  "id": "lab-ENC-POP-000003-489218081940-0000",
  "meta": {
    "profile": [
      "http://jpfhir.jp/fhir/core/StructureDefinition/JP_Observation_LabResult",
      "http://jpfhir.jp/fhir/core/StructureDefinition/JP_Observation_Common",
      "http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Observation_LabResult_eCS"
    ]
  },
  "category": [{
    "coding": [{
      "system": "http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS",
      "code": "laboratory"
    }],
    "text": "検体検査"
  }]
  /* ... */
}
```

### profile 別の要求

| profile | 要求される category CodeSystem |
|---|---|
| `JP_Observation_LabResult_eCS` (電子カルテ情報共有) | `http://terminology.hl7.org/CodeSystem/observation-category` (code=`laboratory`) |
| `JP_Observation_LabResult` (JP Core 基本) | 上記どちらでも可 (但し slice で両方求められる場合あり) |
| `JP_Observation_Common` | `JP_SimpleObservationCategory_CS` |
| Heart rate / Oxygen saturation (自動判定) | `http://terminology.hl7.org/CodeSystem/observation-category` (code=`vital-signs`) |

### あるべき姿 (LabResult_eCS の場合)

```json
"category": [
  {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "laboratory",
      "display": "Laboratory"
    }]
  },
  {
    "coding": [{
      "system": "http://jpfhir.jp/fhir/core/CodeSystem/JP_SimpleObservationCategory_CS",
      "code": "laboratory"
    }]
  }
]
```

**両方の CodeSystem を並記** することで、どちらの profile 側 slice も満たせます (これは JP-CLINS 標準的な運用パターン)。

### 対処

生成器で Observation を出す前に:
1. `meta.profile` の内容を判定
2. `LabResult_eCS` を含む場合は HL7 標準 category (`laboratory` / `vital-signs` / `imaging` 等) と JP category の**両方を並記**
3. `JP_Observation_Common` のみの場合は JP category のみで OK

---

## 【最優先 4】Observation — 必須要素・拡張型違反

**影響**: 14,000〜28,000 件規模で複数の欠落。合計 100,000+ error。

### 現状 (`lab-ENC-POP-000003-489218081940-0000`)

前述の JSON に加えて:
- ❌ `identifier` が無い
- ❌ `meta.lastUpdated` が無い
- ❌ `specimen` (検体 reference) が無い
- ⚠️ `referenceRange[N].extension[N].url` の値が `.../JP_Observation_Common#referenceRangeSource` (fragment `#` を含む URL、FHIR 仕様上不可)

### profile 要求

`JP_Observation_LabResult_eCS` は以下を必須:
- `identifier`
- `meta.lastUpdated`
- `specimen`: `Reference(Specimen)` (検体検査は検体情報が必須)
- extension URL は canonical URI であるべき (fragment `#foo` は不可)

### あるべき姿 (追加分抜粋)

```json
{
  "identifier": [{
    "system": "http://example-hospital.jp/fhir/observation-id",
    "value": "lab-ENC-POP-000003-489218081940-0000"
  }],
  "meta": {
    "profile": [ /* ... */ ],
    "lastUpdated": "2025-03-15T12:31:00+09:00"
  },
  "specimen": {
    "reference": "Specimen/spm-ENC-POP-000003-489218081940-0000"
    /* 検体 Specimen リソースを別途生成し、reference で結ぶ */
  },
  "referenceRange": [{
    "low": { /* ... */ },
    "high": { /* ... */ },
    "extension": [{
      "url": "http://jpfhir.jp/fhir/core/StructureDefinition/JP_Observation_ReferenceRangeSource",
      /* ✅ fragment (#) なしの canonical URL に修正 */
      "valueString": "https://www.jccls.org/wp-content/uploads/2022/10/kijyunhani20221031.pdf"
    }]
  }]
}
```

### 対処

- **`Specimen` リソースの自動生成**: 検体検査 Observation を出す際は、対応する Specimen リソースも同時に生成し、`Observation.specimen` で reference
- **extension URL の修正**: fragment `#referenceRangeSource` を廃止し、独立した canonical URL の StructureDefinition (`.../StructureDefinition/JP_Observation_ReferenceRangeSource` 等) を定義するか、既存 JP profile の正式 extension URL を使用

---

## 【最優先 5】CareTeam.category — 無効な LOINC code

**影響**: 全 1,913 件 (100%)。

### 現状 (`careteam-ENC-POP-XXX-...`)

```json
"category": [{
  "coding": [{
    "system": "http://loinc.org",
    "code": "LA27976-8"
  }],
  "text": "エピソード・オブ・ケアチーム"
}]
```

### 問題

LOINC 2.82 に `LA27976-8` は存在しない (deprecated or typo)。error: `Unknown code 'LA27976-8' in the CodeSystem 'http://loinc.org' version '2.82'`

### あるべき姿

JP Core の `CareTeam.category` は http://loinc.org または SNOMED CT のいずれかを要求。以下のいずれかに:

```json
/* 選択肢 A: SNOMED (エピソード・オブ・ケアチームに近い concept) */
"category": [{
  "coding": [{
    "system": "http://snomed.info/sct",
    "code": "735320007",
    "display": "Multidisciplinary care team"
  }],
  "text": "エピソード・オブ・ケアチーム"
}]

/* 選択肢 B: 現行 LOINC に存在する code (例) */
"category": [{
  "coding": [{
    "system": "http://loinc.org",
    "code": "LA28866-0",  // 実在確認要 (LOINC 検索で妥当な代替を選ぶ)
    "display": "..."
  }],
  "text": "エピソード・オブ・ケアチーム"
}]
```

生成器で使用する CareTeam.category code list を LOINC 2.82 に存在するものに差し替え。

---

## 【中優先 6】MedicationRequest `periodUnit` — 日本独自値の使用

**影響**: 752 件。

### 現状

```json
"timing": {
  "repeat": {
    "frequency": 1,
    "period": 1,
    "periodUnit": "日"    /* ❌ 日本語 */
  }
}
```

### 問題

`periodUnit` は FHIR 標準 UCUM 時間単位 ValueSet のみ許可。日本語 `"日"` は該当 ValueSet 外。

### あるべき姿

UCUM の時間単位 code を使用:

```json
"timing": {
  "repeat": {
    "frequency": 1,
    "period": 1,
    "periodUnit": "d"    /* ✅ UCUM: d=day, h=hour, wk=week, mo=month, a=year */
  }
}
```

`text` フィールドに `"1日1回"` のように表示用テキストを別途入れれば日本語表示は担保できます。

---

## 【中優先 7】ServiceRequest `code.coding.code` — 空文字

**影響**: 1,251 件。

### 現状

```json
"code": {
  "coding": [{
    "system": "http://...",
    "code": ""              /* ❌ 空文字 */
  }]
}
```

### 問題

FHIR 仕様 `ele-1: All FHIR elements must have a @value or children` に違反。空文字は「値なし」ではなく「不正な値」扱い。

### あるべき姿

有効な code を入れるか、`coding` エントリごと出さない:

```json
/* 選択肢 A: 有効な code */
"code": {
  "coding": [{
    "system": "http://loinc.org",
    "code": "44140-4"
  }]
}

/* 選択肢 B: code が決まらない場合、coding を出さず text のみ */
"code": {
  "text": "手術オーダー"
}
```

---

## 【中優先 8】ICD-10 code の一部が Unknown 判定

**影響**: `E11.65` × 1,679、`S72.00` × 1,357、`M48.50` × 414、他多数。合計約 5,000 件。

### 問題

data 側は **正しい ICD-10 code** を使っているが、validator が参照する `http://hl7.org/fhir/sid/icd-10` version=`2019-covid-expanded` に**すべての ICD-10 code が含まれていない**ため Unknown 判定される。

### 対処 (data 側の選択)

- (A) **日本の ICD-10 code system を使う** (`http://jpfhir.jp/fhir/core/CodeSystem/...` — jpfhir-terminology への正式登録待ち)
- (B) 独自の CodeSystem URI に切り替える (data 側で URI を独自定義し、validator の tx 未登録扱いに寄せる。`system'X'で未知のコード` warning に緩和)
- (C) 現状維持 (validator 側の CodeSystem 拡張を待つ)

これは data 品質ではなく terminology 環境の問題なので、fix は**必須ではない**が、warning ノイズを減らすなら (A) または (B) を検討。

---

## 【対処不要 — validator noise / 環境要因】

以下は data 側の問題ではありません:

| 内容 | 件数 | 理由 |
|---|---:|---|
| `dom-6 narrative missing` (Best Practice) | 133,717 | Best Practice Recommendation。narrative は必須ではない |
| SNOMED/LOINC の日本語 display 「no valid display for ja」 | 30,000+ | SNOMED CT International には日本語 translation なし。生成器は英語 display を入れれば良く、警告は無視可 |
| `未知の CodeSystem urn:oid:1.2.392.200119.4.1005` | 14,998 | 日本の医療機関マスターコード OID。jpfhir-terminology への登録待ち。data 側は正しい |

---

## 期待効果

**【最優先 1〜5】** を対処するだけで:

| 項目 | 現状 | 期待 |
|---|---:|---:|
| 全体 fail 率 | 65% | **15% 以下** |
| 削減 error 数 | - | ~350,000 件 (全体の 87%) |
| 生成器の共通ヘルパー修正で解消 | - | 上記のほぼ全て (テンプレート 1 修正で全リソース波及) |

## caveat — validator 側の未検証項目

- **Observation の LOINC / SNOMED terminology 検証**は今回 validator 性能上スキップ (fhirserver の日本語 display 照合が per-code ~700ms かかり 11 万件を通せないため)。構造/slice/invariant のみ検証。code の妥当性は別途サンプリング等で追試を推奨
- **業務ロジック** (診療報酬点数、レセプト整合、医療的妥当性) は検証対象外 (FHIR 準拠性のみ)

## 参照

- 全 error / warning 生 NDJSON: `full_1of20.ndjson` (~200MB) 詳細解析が必要な場合は連絡ください
- validator 環境と実行方法: https://github.com/TomoOkuyama/fhir-jp-validator
- JP Core spec: https://jpfhir.jp/fhir/core/
- JP-CLINS spec: https://jpfhir.jp/fhir/clins/igv1/
