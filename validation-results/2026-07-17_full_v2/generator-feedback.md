# FHIR (JP Core / JP-CLINS) データ生成 フィードバック (第 3 回、v2)
## Session 57 で追加 merged された 7 PR 反映後の regen 検証結果

**対象**: FHIR R4 データ生成器チーム (clinosim)
**検証環境**: HAPI Validator 6.9.11 + HL7 fhirserver / JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0 / LOINC 2.82 / SNOMED CT International 2026-06-01
**検証データ**: clinosim 0.2.0 生成 (2026-07-17 14:04 JST、master 253bced5、JP p=1000 seed=300、fullset 417,209 res / 26 NDJSON / 567MB)
**検証日**: 2026-07-17
**検証所要**: rest 25 種 7:04 + Observation 16:24 = **23:28 完走** (0 timeout)

## 全体傾向 (前回 v1 vs 今回 v2)

| 指標 | 前回 v1 (2026-07-17 10:44) | 今回 v2 (2026-07-17 14:48) | 変化 |
|---|---:|---:|---:|
| 検証対象 | 437,669 | 417,209 | 生成量ほぼ同一 |
| errors 総数 | 584,906 | **85,195** | **-85%** |
| 1+ error あり | 218,415 (49.9%) | **~49,495 (11.9%)** | **-38pp** ✅✅✅ |

**大局評価**: v1 (fail 率 50%) → v2 (**12%**) の大幅改善。session 57 の 7 PR がほぼ期待通り (合計期待 -345k、実測 -400k、期待値以上) に効いた。特に Observation の error は **484,240 → 30,848 (-94%)** で fail 率 70% → 12% と劇的改善。以下、fix 別の実測状況と残った/新規発覚した issue を priority 順にまとめます。

---

## 【Session 57 fix 実測結果サマリ】

| PR | 対象 | 期待効果 | 実測 | 判定 | メモ |
|---:|---|---:|---:|:---:|---|
| #201 | Observation.category per-CS 分離 | -286k | ✅ 消失 | ✅✅ | 前回の dual mismatch 双方向 error 完全解消 |
| #203 | referenceRange extension 全廃止 | -31k | ✅ 消失 (実測 -62k、v1 で 2 種計 62k だった) | ✅✅ | referenceRange.extension max=0 違反も同時に消えた |
| #205 | UCUM canonicalization (IU→[iU], mcg→ug) | -6.2k | ✅ 消失 | ✅ | 完全解消 |
| #207 | `_generator_metadata.json` sidecar | 追跡性 | ✅ 動作確認 | ✅ | commit hash / recent_merges / hospital_scale 等 machine-readable |
| #209 | MAR.reasonCode ICD-10 mapping | -7.6k | ✅ 消失 | ✅ | S72.00 / E11.65 消えた |
| #211 | BP LOINC 85354-9 panel + component[] | -14.5k | ✅ 消失 | ✅ | bp profile 違反 (component 欠落 / closed slice mismatch) 完全解消 |
| #213 | example.org → .dev CodeSystem URI | -577+66 | ✅ Patient occupation / care-level 消失 | ✅ | 副作用: `http://clinosim.dev/fhir/CodeSystem/*` は依然として validator 上で未知 CodeSystem 扱い (warning 止まり、error にならず OK) |

**Session 56 fix (#192/#197 open) 状況**:
- #192 (Condition eCS): 未 merge、Condition 100% fail 継続 (6,242 res × 6 種類の必須欠落)
- #197 (MR dosageInstruction + R5020): 未 merge、MedicationRequest 100% fail 継続 (1,871 res × 6 種類)

---

## 【最優先 1】Observation.identifier:resourceIdentifier slice — 全 obs で欠落 (最大インパクト)

**影響**: Observation 30,315 件 (fail の 100%)。obs 側で唯一残った主 error。

### 実測

```
Slice 'Observation.identifier:resourceIdentifier': minimum required = 1, but only found 0
(from http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Observation_LabResult_eCS|1.12.0)
```

### 原因分析

現状の Observation.identifier は `[{system: "urn:oid:...", value: "..."}]` の形式で 1 個以上ある。しかし JP_Observation_LabResult_eCS profile の `identifier:resourceIdentifier` slice は特定の system URI パターンで discriminator しており、渡している identifier がそれに match していない。

### あるべき姿

```json
"identifier": [
  {
    "system": "http://jpfhir.jp/fhir/eCS/NamingSystem/resourceIdentifier",
    "value": "<院内で一意なリソース ID>"
  }
  // 他の identifier (検体番号など) は追加可
]
```

または、profile が期待する discriminator (JP-CLINS 1.12.0 の `Observation.identifier:resourceIdentifier.system` の fixedUri) に system を合わせる。JP-CLINS の StructureDefinition-JP_Observation_LabResult_eCS.json を確認して正確な system URI を採用。

### 対処

Observation 生成時、`identifier[]` の先頭に必ず `resourceIdentifier` slice に一致する system+value を emit する。同じ pattern が MedicationRequest / Condition の resourceIdentifier slice にも適用可 (すでに #192/#197 で対処されているはず)。

**このひとつの対処で fail 率が 11.9% → ~4.6% (-7.3pp) に一気に下がる**。

---

## 【最優先 2】CareTeam.category SNOMED 735320007 — fhirserver 側 SNOMED CT に code 未収録

**影響**: CareTeam 3,788 件 (100%)。v1 から改善無し。

### 実測

```
Unknown code '735320007' in the CodeSystem 'http://snomed.info/sct'
version 'http://snomed.info/sct/900000000000207008/version/20260601' (International Edition)
```

### 原因分析

`735320007` は SNOMED CT の Community Health Care Team code だが、fhirserver に load されている **SNOMED CT International 2026-06-01 (International Edition)** には収録されていない (SNOMED International vs 各国 edition の差異、または版差)。

### 対処案

以下いずれか (data 側での回避が現実的):
1. **別 code に差替** (International Edition 収録済 & CareTeam 用途に妥当な code、例: `407484005` "Rehabilitation care team" 等)
2. **SNOMED CT 版切替** (fhirserver 側で version 変更 or 拡張 edition 使用) — 環境変更が大きい
3. **US Extension SNOMED** を fhirserver に追加 load (US Extension には 735320007 収録) — fhirserver 側の設定変更

即効性重視なら (1) を推奨。

---

## 【最優先 3】MedicationAdministration `mad-1` invariant 失敗 — 新規発覚

**影響**: MedicationAdministration 2,755 件 (4.3%)。v2 で新規発覚。

### 実測

```
ルール mad-1 が失敗しました
```

### 診断

R4 base の `mad-1` invariant:
```
mad-1: Reason not given is only permitted if NotGiven is true
```
つまり `MedicationAdministration.statusReason` が設定されていて `MedicationAdministration.status = "not-done"` でないと fail する。

現状の data では `status = "completed"` で `statusReason` を持つケースがあるはず。

### 対処

生成器で以下いずれか:
- `status = "not-done"` の時のみ `statusReason` を出力
- `statusReason` を持つ MedicationAdministration は `status = "not-done"` に統一

---

## 【最優先 4】Condition invariant `con-4` 失敗

**影響**: Condition 2,452 件 (39%)。v1 から継続。

### 診断

R4 base の `con-4`:
```
con-4: If condition is abated, then clinicalStatus must be either inactive, resolved, or remission
```

現状: Condition.abatement[x] が設定されているが clinicalStatus が `active` 等になっているケース。

### 対処

生成器で abatement 設定時は clinicalStatus を必ず inactive/resolved/remission のいずれかに切替える。

---

## 【最優先 5】JP_MedicationRequest_eCS の未対応 constraint 群 (PR #197 未 merge 分 + 新規)

**影響**: MedicationRequest 1,871 件 × 複数種類 = ~11,000 error。

### 実測

```
1,871  MedicationRequest.identifier: 最小必要値 = 3、見つかった値 = 2
1,871  Slice 'MedicationRequest.identifier:requestIdentifier': minimum required = 1
1,748  Dosage.doseAndRate.type: 最小必要値 = 1
1,748  The System URI could not be determined for the code 'd' in the ValueSet 'UnitsOfTime'
1,748  提供された値（'d'）はValueSet 'UnitsOfTime' に含まれていません
1,540  値は 'active' ですが、 'completed' でなければなりません
  848  MedicationRequest.substitution.allowed[x].coding: 最小必要値 = 1
  848  substitution.allowed[x] タイプ CodeableConcept を許可していますが、タイプ boolean が見つかりました
  848  値は 'instance-order' ですが、 'order' でなければなりません
```

### 主な原因と対処

1. **identifier count 3 & requestIdentifier slice** (v1 と同一、PR #197 で対処予定)
2. **Dosage.doseAndRate.type 必須** — JP_MedicationDosage_eCS profile が要求。dose を持つ Dosage には `doseAndRate[].type` (例: `ordered`) が必要
3. **UnitsOfTime 'd' 未知** — periodUnit の値。`d` は正しい UCUM code だが FHIR の `UnitsOfTime` ValueSet では大文字含む列挙になっている可能性 (spec 確認要)。または UCUM system を指定して binding をパス
4. **status enum "active" → "completed"** — profile が特定 subtype で status を制約
5. **substitution.allowed[x] 型不一致** — data は `allowedCodeableConcept` を送るべきなのに `allowedBoolean` を送っている? もしくは profile がすでに CodeableConcept を要求
6. **intent "instance-order" → "order"** — profile が enum を order のみに制約

**PR #197 では substitution / doseAndRate / status / intent / UnitsOfTime も対応範囲に含めることを推奨**。

---

## 【最優先 6】JP_Condition_eCS の未対応必須要素 (PR #192 未 merge 分)

**影響**: Condition 6,242 件 (100%)。v1 と同一、状況変わらず。

### 実測 (per-resource 全て発生)

```
Slice 'Condition.identifier:resourceIdentifier': minimum required = 1, but only found 0
Slice 'Condition.code.coding:medisRecordNo': minimum required = 1, but only found 0
```

**PR #192 の実装で解消想定**。

---

## 【中優先 7】ICD-10 日本語 display mismatch

**影響**: rest 側 ~2,500 件 (I10 "本態性高血圧症" 1,782 + E78 "脂質異常症" 643 + 他)。v2 で顕在化。

### 実測

```
Wrong Display Name '本態性高血圧症' for http://hl7.org/fhir/sid/icd-10#I10.
Valid display is 'Essential (primary) hypertension' (for the language(s) 'en')
```

### 診断

`http://hl7.org/fhir/sid/icd-10` (英語版) には display に日本語が定義されていない。生成器は日本語 display を送っているが英語 CodeSystem では認識されない。

### 対処案

以下いずれか:
1. **display を省略** — display は optional なので送らない (最も簡単)
2. **英語 display を使う** — CodeSystem の canonical display と揃える
3. **日本語 display は別の system で** — 例: `http://terminology.jp/CodeSystem/icd-10-ja` 等 (要 CodeSystem 定義)
4. **HAPI validator の `-check-display Ignore` を tx call まで伝播する patch** — fhir-jp-validator 側の話 (別 track)

即効性重視なら (1) 推奨。

---

## 【中優先 8】Narrative status "generated" vs "additional"

**影響**: rest 側 750 件。

### 実測

```
値は 'generated' ですが、 'additional' でなければなりません
```

### 原因

一部 profile が narrative.status を `additional` に制約している (通常は `generated`/`extensions`/`additional`/`empty` の 4 択で自由)。該当 profile を特定して生成器で narrative.status を `additional` に変更。

---

## 【noise 判定】対処不要

| 内容 | 件数 (v2) | 判定 |
|---|---:|---|
| `dom-6` warning narrative missing | 350k | 不要 (`-best-practice ignore` で抑止済) |
| SNOMED/LOINC 日本語 display なし info | 大量 | 不要 |
| `urn:oid:1.2.392.200119.4.1005 未知` warning | ~30k | 不要 (医療機関 OID、jpfhir-terminology 側の登録待ち) |
| `warn-localCode-observation-laboresult` warning | 30,315 | 情報のみ (電子カルテ情報共有サービス送信時のみ要件) |
| `http://clinosim.dev/fhir/CodeSystem/*` 未知 warning | ~640 | 不要 (data の CodeSystem 定義側に含まれないが検証には影響なし) |

---

## 全体所感と次サイクル提案

**達成**:
- v1 fail 率 65% (2026-07-16 1/20) → v1 50% (2026-07-17 fullset) → v2 **12%** — 5.4x 改善
- 特に **Observation error -94%** は劇的。#201/#203 の効果が大きい
- 期待値 -345k errors に対し実測 -400k、期待以上

**次サイクル最優先** (期待効果順):

1. **Obs.identifier:resourceIdentifier slice の system URI 修正** → **-7.3pp** (最大インパクト)
2. **PR #192 (Condition eCS) merge** → -1.5pp
3. **PR #197 (MR eCS) merge + substitution/intent/UnitsOfTime 追加対応** → -0.5pp
4. **CareTeam SNOMED 735320007 差替** → -0.9pp
5. **MAR mad-1 fix (statusReason / status consistency)** → -0.7pp
6. **Condition con-4 fix (abatement / clinicalStatus consistency)** → -0.6pp
7. **ICD-10 日本語 display 省略** → -0.6pp

上記全対処で fail 率 **~12% → 数 % 台** 到達見込み。

**追加観察 (品質)**:
- 分割検証 (rest tx 有効 / obs tx=n/a) は今回も安定完走 (23:28、0 timeout)
- fhirserver 側の負荷は前回同様。今回のデータ特性 (LOINC 日本語 display 少なめ) を考えると、Observation を tx 有効で流す実験も可能な範囲 (別途検討)
