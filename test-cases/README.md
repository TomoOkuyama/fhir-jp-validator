# test-cases/ — validator の regression 検出用テストデータ

意図的に問題を含む FHIR リソースを、期待される error 種別 (slug) と共に
格納する。`scripts/reconcile-test-cases.py` で validator を回し、
期待通り検出されたかを自動判定する。

## 目的

- validator + IG (JP Core / JP-CLINS) + terminology の設定変更で **今まで
  検出できていたエラーが検出できなくなる** regression を早期に発見
- 新しい profile / rule 対応を追加したときに、対応するテストケースを
  1 個作れば以降ずっと監視される

## ファイル構成

```
test-cases/
├── README.md                    # このファイル
├── expected-issues.py           # slug → 期待 error 正規表現の辞書
├── fhir-base/                   # FHIR コア (cardinality, invariant, code enum 等)
├── terminology/                 # CodeSystem/ValueSet 由来
├── jp-core/                     # JP Core profile 固有
├── jp-clins/                    # JP-CLINS eCS profile 固有
└── extensions/                  # extension URL / 位置制約
```

## 1 テストケースの書式

- **1 case = 1 FHIR リソース** (1 NDJSON ファイルに 1 リソース、ただし複数入れても OK)
- 期待されるエラー種別は `meta.tag[]` に埋め込む:

```json
{
  "resourceType": "Observation",
  "id": "tc-obs-lab-no-specimen",
  "meta": {
    "profile": ["http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Observation_LabResult_eCS"],
    "tag": [
      {
        "system": "http://fhir-jp-validator.test/expected-issue",
        "code": "jp-obs-lab-specimen-missing"
      }
    ]
  },
  ...
}
```

- `system` は必ず `http://fhir-jp-validator.test/expected-issue`
- `code` は `expected-issues.py` の `EXPECTED_ISSUES` に登録された slug
- 1 リソースに複数 tag を付けることで **複数エラー同時発生ケース** を表現可

## 新しいテストケースの追加手順

1. `expected-issues.py` の `EXPECTED_ISSUES` に slug を追加
   ```python
   "my-new-issue": {
       "desc": "何を検出したいかの一言説明",
       "pattern": r"error text にマッチする regex (日/英どちらでも通るように)",
   },
   ```
2. `test-cases/<category>/<descriptive-name>.ndjson` に 1 行 JSON で
   問題ありリソースを書く。`meta.tag` にその slug を入れる
3. `./scripts/reconcile-test-cases.py` を走らせて PASS を確認
4. commit

## 走らせ方

前提: fhirserver + HAPI cluster 起動中。

```bash
docker compose up -d fhirserver
HAPI_EXTRA_ARGS="-best-practice ignore" ./scripts/hapi-cluster.sh start

./scripts/reconcile-test-cases.py

# 詳細を見る
./scripts/reconcile-test-cases.py -v
```

exit 0 = 全 case PASS。exit 1 = FAIL / 未定義 slug あり。

## 現在のカバレッジ (v6, 2026-07-18)

- **101 case / 161 期待 slug、reconcile 全 PASS**
- 内訳:
  - `fhir-base/` 34 case: R4 基本 cardinality (status/subject/intent/effective 等)、invariant (con-4, obs-6/7, bp)、Bundle 系 (bdl-1/3)、Reference 型不一致
  - `jp-core/` 15 case: JP_Patient/Practitioner/Organization/PractitionerRole/Encounter/Location/Immunization/AllergyIntolerance/Coverage/DocumentReference/Procedure/ServiceRequest/Condition_Diagnosis/MedicationRequest/FamilyMemberHistory
  - `jp-clins/` 30 case: eCS 系 (LabResult/Condition/MedicationRequest/DR/Encounter/CarePlan/AllergyIntolerance/Patient/Organization/Practitioner/FamilyMemberHistory/Consent/Procedure/MedAdmin/DocumentReference/Coverage) + Composition eReferral / eDischargeSummary
  - `terminology/` 12 case: unknown code (LOINC/SNOMED/ICD-10/UCUM)、CodeSystem 未登録、Example URL、display mismatch、Quantity/Coding.system 欠落、dataAbsentReason、enum 違反
  - `extensions/` 10 case: unknown extension URL、extension 型不一致 (us-core-race 等)、位置制約違反、value[x] と nested 両立、modifier extension、URL 欠落
- 網羅性: 全 profile 全 slice ではなく **代表的な失敗パターン** を高信頼で監視する目的。

## Roadmap

- [x] framework 導入 (このファイル + 照合 script + 15 seed cases)
- [x] JP Core 主要 profile 主要 slice 網羅 (v6 で 101 case)
- [x] JP-CLINS eCS 主要制約網羅 (v6 で 30 case)
- [ ] Composition profile の section slice 系 (現状 meta 系のみ)
- [ ] Reference target 制約系 (Reference(Patient) に Practitioner を渡す等の網羅)
- [ ] CI 統合 (main への push 時に自動実行)
- [ ] 期待通り検出されなかったケースの原因 (validator バグ / IG バグ / データ設計) 分類
