# 2026-07-23 v26 — clinosim wave1 3 PR (#377/#379/#381) + tx=8181 full-set

## 位置付け

v25 (`3d173857`, P=100, tx=8181) で発掘した Pattern A/B (7,764 errors) への直接 fix。
同 config で generator master のみ差替、直接 A/B。

| PR | 内容 | 期待効果 |
|---:|---|---|
| #377 (Issue #376) | LOINC 8478-0 → 107117-4 "Method of oxygen delivery" | -1,165 (v25 code/display 意味的誤り解消) |
| #379 (Issue #378) | Patient.meta.profile に JP_Patient_eCS 追記 (multi-profile) | -3,096 (v25 の JP_Patient_eCS 未 match 解消) |
| #381 (Issue #380) | 14 LOINC display SHORTNAME → LONG_COMMON_NAME | -3,492 (v25 の SHORTNAME emit mismatch 解消) |

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- 単一 pass、sticky × 4 (Organization / Patient / Practitioner / PractitionerRole)
- `--chunk 30 --parallel 24 --timeout 300` (v25 の HTTP failed 対策で timeout を 120 → 300)
- Data: **35,062 res** (合成、seed=300, patients 434, master `3cb7b76b`)

## Result

| 指標 | 値 |
|---|---:|
| 総 res | 35,062 (processed 34,810) |
| 所要 | 29.6 min |
| 平均 rps | 19.6 |
| **error 総数** | **37,762** (v25 7,764 → +30,000 大幅悪化) |
| warning 総数 | 52,071 |
| information 総数 | 135,363 |
| HTTP failed bundle | 1 bundle (30 res) — timeout 300s でもさらに超えた obs bundle |

## v25 → v26 diff (期待は 0、実測は 5x 悪化)

| 指標 | v25 | v26 | 差分 |
|---|---:|---:|---|
| error 総数 | 7,764 | **37,762** | +30,000 ⚠️ |
| Pattern A (LOINC display mismatch) | 4,657 | **1,547** | -3,110 (#381 部分効果) |
| Pattern B (JP_Patient_eCS 未 match) | 3,096 | (吸収) | — |
| **新規 cascade regression (profile match failure)** | 0 | **36,215** | **PR #379 由来 ⚠️** |

## PR 別評価

### ✅ PR #377 完全効果

v25 で 1,165 だった LOINC 8478-0 code/display 意味的誤り (emit "Inhaled oxygen delivery
system" vs canonical "Mean blood pressure") が **0 に**。code を 107117-4 (Method of oxygen
delivery) に変更、正しい canonical と整合。

### 🟡 PR #381 部分効果

top 14 LOINC の SHORTNAME 修正:
- v25: 2160-0 (415), 2345-7 (352), 2823-3 (239), 2951-2 (187), 6690-2 (136), 1920-8 (134),
  1742-6 (127), 1988-5 (112), 718-7 (101), 11331-6 (61), 3094-0 (53), 6301-6 (39), 42637-9 (34)
  → v26 で全て 0 (完全解消)
- **未対応で残った**:
  - **LOINC 80288-4 (1,252)**: `Level of consciousness AVPU` (v25/v26 同数)、`Level of consciousness AVPU score` が canonical
  - LOINC 2744-1 (38): `pH`
  - LOINC 2019-8 (38): `pCO2`
  - LOINC 2703-7 (38): `pO2`
  - LOINC 1963-8 (38): `Bicarbonate`
  - LOINC 777-3 (27): `Platelet count`
  - LOINC 17861-6 (27): `Calcium`
  - LOINC 2524-7 (27): `Lactate`
  - その他 (10839-9, 13969-1 等)、合計 1,547 error 残存

**80288-4 は user 事前予測通り fhirserver 独自 canonical で残存**、他 9 code は #381 の 14 code
リストに含まれていなかった可能性。次 chain で追加拡張要。

### ❌ PR #379 深刻な cascade regression

Patient.meta.profile に `JP_Patient` + `JP_Patient_eCS` を multi-profile 宣言した結果、
**Patient 全 61 件が JP_Patient_eCS validation で fail** → Patient を reference する **全
resource が subject/patient reference の profile match で fail** の cascade。

**cascade 波及 (target profile 別)**:

| target profile | error 件数 |
|---|---:|
| Device (Observation.subject の Device slice 選択肢) | 20,080 |
| JP_Patient | 9,392 |
| JP_Patient_eCS | 3,396 |
| JP_Location (ServiceRequest.subject の Location slice 選択肢) | 2,823 |
| Group | 444 |
| RelatedPerson (Coverage.subscriber の選択肢) | 61 |
| unknown-profile | 19 |
| **合計** | **36,215** |

**cascade 波及 (source resourceType 別)**:

| rt | fail res | issues | total | fail 率 |
|---|---:|---:|---:|---:|
| Observation | 20,005 | 24,991 | 20,035 | 99.9% |
| MedicationAdministration | 5,227 | 5,227 | 5,227 | **100%** |
| ServiceRequest | 2,823 | 2,823 | 2,823 | **100%** |
| Condition | 736 | 1,472 | 736 | **100%** |
| Encounter | 444 | 452 | 444 | **100%** |
| Immunization | 342 | 342 | 342 | **100%** |
| DiagnosticReport | 210 | 210 | 791 | 26.5% |
| FamilyMemberHistory | 175 | 175 | ? | — |
| MedicationRequest | 151 | 302 | ? | — |
| Coverage | 61 | 122 | ? | — |

**Patient を reference する全ての resource type で fail が急増**、7 種類の resource type で
100% fail。

## PR #379 regression の構造 (真因)

**現象**: HAPI validator が Patient を multi-profile validation する時、宣言された **全 profile
に対して conform** することを要求。Patient data は `JP_Patient` (core) の必須要素は満たしていたが、
`JP_Patient_eCS` の追加必須要素 (例: identifier slice、拡張、追加要素) を満たしていない。

**結果**: Patient が eCS conform でない → Patient を reference する resource が subject
resolve 時に "profile 選択肢の中からマッチ見つからない" と判定 → cascade error。

**構造上の教訓**:

1. **`meta.profile` の追加は data conformance と一致していなければならない**
2. **Patient に eCS profile を宣言するには data 側で eCS 必須要素を全て emit する必要がある**
   - JP_Patient_eCS 側 slice/必須要素の PR #379 と併走する data emission fix が未着手
3. **v25 で見えていた 3,096 error は "profile 未宣言の警告"**、data 側改修と profile 宣言追記の
   **両方が必要** — profile だけ宣言すると今回のように悪化

## fix 案 (2 択)

### Option A: PR #379 revert (即効)

- Patient.meta.profile から `JP_Patient_eCS` 削除、`JP_Patient` のみに戻す
- v25 の 3,096 errors (JP_Patient_eCS 未 match) 再発
- 但し合計は v25 と同水準 (~7,700) に復帰、cascade 34k 消滅
- 恒久解決ではない (Pattern B の根本残る)

### Option B: PR #379 維持 + Patient data を eCS 準拠化

- JP_Patient_eCS の spec 要素を確認、Patient.ndjson emit で全項目を追加
- 該当 spec: `http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Patient_eCS`
  - 必須 slice: identifier (MHLW 患者 ID system 系)、拡張等
- 実装コスト: JP_Patient_eCS のプロファイル差分に応じて 1-3 日
- v26 の cascade 34k + v25 の 3,096 = 両方解消の根本解

## fhirserver 最適化の並行検討

本 run と別調査で以下を確認:

- fhirserver LOINC cache は SQLite、`Descriptions(CodeKey, LanguageKey)` compound index 済み
- SQL 直接測定: 0.057ms/query (以前推定の 700ms は古い vault 情報、per-context cache patch 適用で解消済み)
- curl 直接呼び出し: 20-30ms/call (v26 高負荷下)、素なら 10ms 前後
- 遅さの本質は per-call latency ではなく **Bundle 内シーケンシャル処理** + **FLock 争奪**

現行 patch (per-context Display cache) で fhirserver 側の主要 bottleneck は解消済み、更なる改善
余地は FLock read/write 分離、起動時 pre-populate 等の中期候補。

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/all.failed.ndjson` (git-ignored、1 bundle)
- `raw/generator-metadata-snapshot.json`
