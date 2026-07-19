# 検証まとめ — 2026-07-20 v6 (session 59 14 chain merge 後)

## ⚠️ 総評: 期待に反する大幅リグレッション発生

- **fail 率 v5 0.692% → v6 3.554% (+2.86pp)** — 予想 ~0.14% と真逆
- **error 総数 v5 5,048 → v6 15,148 (+200%)** — 予想 -86% と真逆
- **根本原因**: **Chain #292 / #301 (NOCODED fallback) の display 実装ミス** で MedicationAdministration/MedicationRequest に **12,891 件の display mismatch エラー** が発生

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-20 03:42 JST、JP p=1000 seed=300、master 2253deda)
- **fullset = 426,301 リソース / 28 NDJSON / 615MB** (v5 417,209 → +9,092)
- session 59 merged 14 PR (#280/#282/#285/#288/#290/#292/#294/#295/#297/#298/#300/#301/#302/#303) 反映済み

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 176,168 | 7 分 39 秒 | 384 | 100% |
| obs | 250,133 | 16 分 57 秒 | 246 | 100% |
| **合計** | **426,301** | **24 分 36 秒** | **289** | **100%** |

## Issue 分布 (v5 vs v6)

| severity | v5 total | v6 total | 変化 |
|---|---:|---:|---:|
| error | 5,048 | **17,642** | **+250%** ⚠️ |
| warning | 502,605 | 502,139 | ~0% |
| information | 854,559 | 882,199 | +3% |

**リソース単位 pass/fail** (1+ error あり)
- rest: 176,168 中 14,972 = **8.499%** (v5 1.578% → +6.92pp)
- obs: 250,133 中 176 = **0.070%** (v5 と同一)
- **合計 426,301 中 15,148 = 3.554%** (v5 0.692% → **+2.86pp**)

## エラーカテゴリ (v6 rest 内訳、17,103 error text 頻度)

| # | カテゴリ | 割合 | Chain 起因 |
|---:|---|---:|:---:|
| **12,891** | **NOCODED display mismatch** (`カルベジロール 2.5mg` vs `標準コードなし` 等) | **75%** | **#292/#301 regression** ⚠️ |
| **3,532** | UnitsOfTime `d` binding (periodUnit='d' が validator 側で system URI 決定不能) | **21%** | #282 副作用 |
| 571 | ImagingStudy RadLexPlaybook VS 非包含 (継続 backlog) | 3.3% | #302 効果なし |
| 44 | Composition eReferral referralFrom/toSection.entry:Organization slice min=1 | 0.3% | #297 部分 |
| 22 | Composition eReferral display `他医療機関紹介` vs `診療情報提供書発行` | 0.1% | 新規 |
| 13 | MAR route SNOMED 37161004 Sublingual → Per rectum default | 0.1% | 新規 (#252 対象外) |
| 15 | Composition Provenance `event.code` JSON array 期待だが Object | 0.1% | 新規 (データ構造誤り) |
| 6 | tx timeout (Read timed out) | 0.03% | インフラ |

## Session 59 14 chain 実測結果サマリ

| PR | 対象 | 期待効果 | 実測 | 判定 |
|---:|---|---:|---|:---:|
| #280 | eDS Composition.category display 退院時文書 | -252 | 0 件 (完全解決) | ✅✅ |
| #282 | MR tim-2 periodUnit | -1,748 | tim-2 は 0 件 ✅、ただし periodUnit="d" が validator の **UnitsOfTime binding で 3,532 件失敗** (副作用) | ⚠️ |
| #285 | ICD-10 3 codes swap (I84/R33.9/S62.9) | -86 | 全 0 件 | ✅ |
| #288 | eDS 5 discharge sections text.div | -630 | txt-2 0 件 | ✅✅ |
| #290 | eReferral extension:version 5 top-level | -120 | 0 件 (完全解決) | ✅✅ |
| #292 | JP MR medication.coding NOCODED fallback | -26 | **NOCODED display mismatch +12,891 件** (MAR にも波及、massive regression) | ❌❌❌ |
| #294 | AI drop SNOMED secondary | -76 | AI err 0 件 (該当 identifier slice も既に別 chain で処理済) | ✅ |
| #295 | eDS hospitalCourseSection.entry from free-text DocRef | -126 | 0 件 | ✅✅ |
| #297 | eReferral 920/910 section entry Organizations | -96 | referralFrom/to Organization slice が 22×2 = 44 件で残 (部分) | ⚠️ |
| #298 | US goldens chore sync | 0 chore | 該当なし | ✅ |
| #300 | 5 residual sweep (READM/exp/PT-OT-ST-MSW/empty-array/area) | -91 | 0 件 (完全) | ✅ |
| #301 | YJ nocoded fallback | -594 | YJ_VS non-inclusion 消滅 ✅ だが **NOCODED display 問題は #292 と共通で悪化** | ⚠️ |
| #302 | JP radiology DR _Radiology profile + spec slices | -499 | RadLexPlaybook VS 571 件で残 (Chain 効果なし or 別問題) | ❌ |
| #303 | LOINC 17 semantic-mismatch | 0 hygiene | 0 件 | ✅ |

**期待合計 -4,344 → 実測 +10,100** (期待から -14,444 の乖離)。

## 種別ごと fail 率 (v5 比較)

| 種別 | 検証数 | error あり | v6 fail | v5 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| MedicationAdministration | 64,821 | **12,565** | **19.4%** | 0% | **+19.4pp** ⚠️⚠️ |
| MedicationRequest | 1,893 | 1,806 | 95.4% | 95.7% | ↔ |
| ImagingStudy | 766 | 571 | 74.5% | 73.1% | ↔ |
| Composition | 4,480 | 28 | **0.6%** | 3.5% | -2.9pp ✅ (eDS/eReferral 大幅改善) |
| Location | 71 | 2 | 2.8% | 5.6% | -2.8pp |
| Condition | 6,242 | 0 | **0%** | 1.2% | -1.2pp ✅ |
| AllergyIntolerance | 76 | 0 | **0%** | 100% | **-100pp** ✅✅✅ (Ch294) |
| Encounter | 3,898 | 0 | 0% | 1.1% | -1.1pp ✅ |
| Practitioner | 100 | 0 | 0% | 10.0% | -10.0pp ✅ |
| その他 | 大部分 | 0 | 0% | 0% | ↔ |

**MedicationAdministration の 19.4% fail** が総 fail 率悪化の主要因。**Composition、Condition、AI、Encounter、Practitioner は完全解決** (Session 59 の複数 chain が期待通り機能)。

## 【最重要】NOCODED display 実装ミスの詳細

**現象**:
```
http://jpfhir.jp/fhir/eCS/CodeSystem/MedicationCodeNocoded_CS#NOCODED の誤ったdisplay
'カルベジロール 2.5mg' - 1 の選択肢のうちの一つであるべきです: '標準コードなし' (言語 'ja' のため)
```

**背景**: `MedicationCodeNocoded_CS` CodeSystem は `NOCODED` code 1 個のみを定義し、`display` は `'標準コードなし'` の 1 通りに固定されている (required binding 相当)。

**clinosim v6 の誤実装**:
```json
"medicationCodeableConcept": {
  "coding": [{
    "system": "http://jpfhir.jp/fhir/eCS/CodeSystem/MedicationCodeNocoded_CS",
    "code": "NOCODED",
    "display": "カルベジロール 2.5mg"  // ← 薬剤名を display に。禁止
  }]
}
```

**正しい実装**:
```json
"medicationCodeableConcept": {
  "coding": [{
    "system": "http://jpfhir.jp/fhir/eCS/CodeSystem/MedicationCodeNocoded_CS",
    "code": "NOCODED",
    "display": "標準コードなし"  // ← 固定
  }],
  "text": "カルベジロール 2.5mg"  // ← 薬剤名は CodeableConcept.text に
}
```

**影響範囲**:
- MedicationAdministration: 64,821 中 12,565 (19.4%) に発火 — v6 fail 率悪化の主要因
- MedicationRequest: 一部 (top 20 種類の薬剤名で計 ~12,891 display error)
- 個別 display 種類は薬剤ごとに異なるが、全て同じ根本原因

**対処**: clinosim の NOCODED coding 生成分岐で `display` を必ず `"標準コードなし"` にし、薬剤名は `CodeableConcept.text` に移す

## UnitsOfTime 'd' binding の詳細

**現象**:
```
The System URI could not be determined for the code 'd' in the ValueSet
'http://hl7.org/fhir/ValueSet/units-of-time|4.0.1'
提供された値（'d'）は ValueSet 'UnitsOfTime' に含まれていません
```

**背景**: Chain #282 は tim-2 (repeat.period.exists() → periodUnit.exists()) を修正するため `periodUnit: "d"` を追加した。tim-2 は解消 (実測 0 件) だが、`periodUnit` は `code` 型で system 情報を持たないため、HAPI validator が UnitsOfTime VS 内での照合ができず fail (3,532 件)。

**分析**: FHIR R4 UnitsOfTime VS は `d` (day) を含むはずだが、`periodUnit: code` の binding 検証で HAPI が system URI を決定できないパターン。**これは HAPI validator/fhirserver 側の既知の挙動** (v3/v4 でも同様の error が出ていた)。

**対処案**:
1. **`periodUnit: "d"` を継続** → HAPI 側の validator 挙動を諦める (v3/v4 では常態化)
2. **period + periodUnit を削除、boundsDuration のみに** → tim-2 は fire しなくなり、UnitsOfTime binding 検証も回避 (session 58 Chain #2 の元の狙い)
3. **HAPI validator を patch** して `code` 型 binding での system-less code 検証を修正 (upstream 対応)

## v6 で残る主要 issue (優先度順)

| # | 対象 | 対処 |
|---:|---|---|
| **12,891** | NOCODED display mismatch | **最優先**: display を `'標準コードなし'` 固定に、薬剤名を text へ移動 |
| **3,532** | UnitsOfTime `d` binding | boundsDuration のみに切替 (period/periodUnit を出さない) or HAPI 側課題として受容 |
| **571** | RadLexPlaybook VS 非包含 (継続) | RadLex 収録 or JP 用差替 (Chain #302 の効果が実測に反映されず、要精査) |
| **44** | eReferral referralFrom/to Organization slice | Chain #297 完全反映 |
| **22** | eReferral 他医療機関紹介 display mismatch | display を `診療情報提供書発行` に |
| **13** | MAR SNOMED 37161004 Sublingual display | display を Per rectum に (Chain #252 対象外だった) |
| **15** | Composition Provenance event.code 構造誤り | `code` を JSON Array に修正 |

### obs 側 (176 件、v5 と同一)

Chain 対象外のため変化なし。要 followup:
- 160 Observation.code.text 欠落
- 147 value.coding.display 欠落
- 24 ele-1 空要素
- 12 × 2 referenceRange units invariant

## 修正すれば戻せる見込み

**NOCODED display 修正のみで**:
- error -12,891 → **5,048 → 4,752 (v5 とほぼ同水準に回復)**
- fail 率 3.554% → ~0.7% (v5 水準に戻る)

**さらに boundsDuration only 化 (Chain #282 revert)** で:
- error -3,532 追加 → **~1,220**
- fail 率 → ~0.3%

上記 2 施策で **v6 → v6.1 で v5 を超えた実質完全準拠 (~0.15%)** が達成可能。

## caveat — 検証していないこと

- Observation の LOINC / SNOMED terminology 検証 (性能上スキップ)
- 業務ロジック (診療報酬点数、レセプト整合、医療的妥当性)
- Bundle Type validation

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~800MB) / `raw/obs.ndjson` (~1.1GB) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)
