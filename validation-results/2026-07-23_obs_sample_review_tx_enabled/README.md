# 2026-07-23 Observation 10 サンプル tx=8181 レビュー

## 位置付け

v24 (clinosim master `3d173857`, seed=300) の Observation.ndjson (252k res) から **10 件を
random sample** し、通常運用の `tx=n/a` ではなく **`tx=http://localhost:8181/r4` (tx 有効)** で
検証。**tx=n/a では発火しない terminology-side error** を洗い出す目的。

- v24 obs pass は `tx=n/a` (structure/slice/invariant のみ) で **0 error**
- 本レビューは **tx を有効化した場合に何が出るか** を 10 件で先行確認

## Setup

- HAPI cluster: 6 JVM、`HAPI_TX=http://localhost:8181/r4 HAPI_EXTRA_ARGS="-best-practice ignore -check-display Ignore"`
- `parallel-validate.py --chunk 10 --parallel 6 --include-file Organization.ndjson --include-file Patient.ndjson`
  (sticky: 全 Organization 17 + 全 Patient ~580 を前置して cross-bundle Reference resolve)
- 実行時間: 10.4 秒 / 1 rps (fhirserver への日本語 display validation で per-code ~700ms、10 obs で 3-5 code 平均含む)

## Result

| severity | 件数 |
|---|---:|
| error | **6** (Observation 10 件中 **5 件** に発火、fail rate 50%) |
| warning | 16 (うち dom-6 narrative 10 件) |
| information | 17 |

同一 10 obs を **tx=n/a で回すと 0 error**。tx 有効化で 6 error 出現 = v24 obs pass の
「0 error / 0.000%」は structure/slice レベルの意味、terminology conformance は別 layer。

## 発掘 error 2 pattern

### Pattern A: LOINC display mismatch (4 error、rest pass DocRef/FMH と同構造)

Observation の `code.coding[].display` が LOINC canonical と不一致:

| Obs id | code | emit display | canonical |
|---|---|---|---|
| `vs-*-loc` | LOINC 80288-4 | `Level of consciousness AVPU` | `Level of consciousness AVPU score` (truncated) |
| `vs-*-o2` component | **LOINC 8478-0** | **`Inhaled oxygen delivery system`** | **`Mean blood pressure`** ⚠️ **意味的誤り疑い** |
| `lab-*-0002` | LOINC 2160-0 | `Creatinine` | `Creatinine [Mass/volume] in Serum or Plasma` |
| `lab-*-0005` | LOINC 1988-5 | `C-reactive protein` | `C reactive protein [Mass/volume] in Serum or Plasma` |

- LOINC 80288-4/2160-0/1988-5 は SHORTNAME/simplified label emit、canonical は LONG_COMMON_NAME
  → v22 の DocRef LOINC 11506-3 と同構造 (`docs/output-guide.md` 3.2)
- **LOINC 8478-0 は深刻**: emit "Inhaled oxygen delivery system" だが canonical は "Mean blood
  pressure"。code/display 対応が壊れている疑い (酸素配送 component に血圧 LOINC が割当)、
  clinosim data generator の code-mapping 誤りの可能性。要調査

**generator-side fix**: code-by-code で canonical に整合 (v3-RoleCode fix (#375) と同 pattern)、
または display 省略。LOINC 8478-0 は code 対応そのものが誤りか要確認。

### Pattern B: JP_Patient_eCS profile match failure (2 error)

```
subject: 選択肢 http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Patient_eCS|1.12.0 の中から
profile Patient/POP-000805 のマッチを見つけることができません
```

lab-* Observation は `JP_Observation_LabResult_eCS` 準拠、その `subject` は
`JP_Patient_eCS` profile 準拠 Patient を binding で要求。clinosim の Patient は `JP_Patient`
(core) 準拠、`meta.profile` に `JP_Patient_eCS` 宣言なし。

**注意**: 同じ issue リストに information severity で `Patient/POP-XXX の詳細はプロファイル
JP_Patient_eCS に一致します` の逆判定が出ており、HAPI validator の判定タイミング差の可能性も
あるが、まず data 側で **Patient.meta.profile に `JP_Patient_eCS` を追加宣言** する対応が
妥当。

**generator-side fix**: JP_Observation_LabResult_eCS を emit するときの subject reference target
Patient に、`meta.profile` として `JP_Patient_eCS` を明示宣言 (multi-profile 宣言可)。

## Warning (16、うち有意なのは 6)

- **dom-6 narrative missing** (10、全 obs): Best Practice、無視可
- **CodeSystem 未収録 (2)**:
  - `http://clinosim.dev/fhir/CodeSystem/nursing-scores` — NEWS2 用 custom CS、clinosim 独自
  - `urn:oid:1.2.392.200119.4.1005` — 日本医療情報学会 検体検査コード、jpfhir-terminology 未収録 (既知)
- **LOINC display warning (2)**: Pattern A の一部が warning severity で二重報告
- **`warn-localCode-observation-laboresult` invariant (2)**: CLINS 送信時にローカルコード必須の
  注意喚起、CLINS 送信でなければ問題なし

## Information (17、参考のみ)

- 日本語 translation なし通知 (SNOMED CT JP 未存在 / LOINC 日本語部分収録の設計)
- slice 未一致情報 (`category` 系)
- Heart rate profile 自動適用 (LOINC 8867-4 → HL7 heartrate profile 自動 chain)

## 結論

- **v24 の "fail 率 0.000%" は structure/slice/invariant 準拠の意味**、terminology 完全性は別
- Observation の tx 有効検証では **10 obs 中 5 obs (50%) に error 発火**
- 主因は 2 種の generator-side issue:
  1. **LOINC display の canonical 不整合** (rest pass の DocRef/FMH 同構造、Observation にも
     存在、特に LOINC 8478-0 の意味的誤りは深刻)
  2. **`JP_Patient_eCS` profile 未宣言** (JP_Observation_LabResult_eCS が subject に eCS 要求、
     Patient.meta.profile 追記が必要)

## 運用への示唆

**run cycle に「obs 10 sample の tx=8181 sanity check」を組み込む** ことを推奨:

- 所要時間: ~10 秒 (10 obs で完走)
- rest pass の後、obs pass (tx=n/a) の前に挟むだけ
- terminology 側 regression の早期発見が可能 (v24 のように fail 率 0.000% だが実は tx 検証で
  50% fail という状況を防げる)

## Raw

- `raw/sample.meta.json` — parallel-validate.py meta
- 詳細 issue list (10 obs × 平均 4 issue) は本 README に転記済み、raw NDJSON は生成し捨て

## 元 data

- clinosim master `3d173857` (v24 と同一)
- Observation.ndjson から `random.seed(42)` で 10 件抽出
- 対象 obs id 一覧:
  - vs-ENC-POP-000315-928901704338-0210-loc
  - gcs-ENC-POP-000747-067992509972-32
  - gcs-ENC-POP-000172-952018765412-43
  - vs-ENC-POP-000560-523218704166-0086-o2
  - news2-ENC-POP-000033-224923531116-115
  - lab-ENC-POP-000805-448571852426-0002
  - lab-ENC-POP-000614-744588730604-0005
  - gcs-ENC-POP-000990-144030771240-8
  - vs-ENC-POP-000520-690211373027-0000-heart-rate
  - gcs-ENC-POP-000662-620597779598-394
