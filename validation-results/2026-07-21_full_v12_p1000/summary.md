# 検証まとめ — 2026-07-21 v12 (p=1000 seed=300、Display cache patch 適用 fhirserver、timeout 修正 4 手法比較)

> **⚠ 2026-07-21 追記 — 本 run の "内部処理由来" 結論は誤り、真因は HAPI validator の on-disk txCache 汚染だった**
> v14 ([../2026-07-21_full_v14_p1000/summary.md](../2026-07-21_full_v14_p1000/summary.md)) で
> **同じデータ + 同じ fhirserver + 同じ jar** で `.hapi-cache/tx-cache/` を wipe しただけで
> timeout 6 → 0 に減った。詳細と upstream 対応は
> [../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md) 参照。
> 本 summary 以下は「4 種 workaround 全滅」の実測記録として残す (誤結論を含む)。

## 当時の総評 (誤): timeout は client/JVM/HAPI socket-timeout の全対処に不応、HAPI validator 内部の特定 Composition 処理由来と確定

- **fail 率**: obs 0%、rest 0.0151% (27 unique / 178,818)、合計 0.00625%
- **20 timeout 修正手法 4 種**を並行比較、**全て 6 → 6** (baseline と完全同一)
- **timeout は具体的な 6 Composition** に固定 (id が run 間で一致)、全て `Composition.type = LOINC 34823-5 (リハビリテーション実施計画書)` パターン
- 原因は **HAPI validator の内部処理** (VS 展開 or LOINC 全体走査 or 循環参照)、client/tx側の workaround では届かない層

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (**Display cache patch 適用済 image `ddcaff46e8e6`**)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Cluster: HAPI 6 JVM × `-Xmx3g`
- Client: `parallel-validate.py` (defaults=retries4/timeout120)

## 検証データ

- clinosim 0.2.0 生成 (2026-07-21、**p=1000 seed=300 JP**、master **8b85ed45** = session 62 wrap = 全 16 PR 適用)
- **fullset = 431,784 リソース** (v8 と完全同一サイズ、session 62 fix 適用済 data)
- data-side 生成側 error は 0 期待、eReferral cross-bundle infra artifact のみ残る想定

## 実行 pass 一覧 (rest 4 種 + obs 1 種)

| pass | chunk | parallel | HAPI socket | 所要 | rps | error | timeout |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest baseline | 50 | 24 | default | 7.2 分 | 414 | 48 | **6** |
| rest chunk30 | **30** | 24 | default | 5.6 分 | **532** | 48 | **6** |
| rest httpto180 | 50 | 24 | **180s** | 8.7 分 | 341 | 48 | **6** |
| rest p6 (low concurrency) | 30 | **6** | 180s | 6.1 分 | 489 | 48 | **6** |
| obs | 50 | 24 | 180s | 25.3 分 | 166 | 0 | 0 |

**timeout は全 4 rest pass で 6 件、Composition id も完全一致**。

## timeout の犯人 6 Composition (全 run で同一)

- 全て `Composition.type = LOINC 34823-5 "リハビリテーション実施計画書"`
- profile 未設定 (base FHIR Composition のみ)
- Composition サイズ ~3KB、5 unique coding、section 9 個
- id list (v12 実測):
  - `comp-ENC-POP-000033-224923531116-187`
  - `comp-ENC-POP-000270-188036175455-107`
  - `comp-ENC-POP-000380-231140288681-119`
  - `comp-ENC-POP-000546-245245476108-135`
  - `comp-ENC-POP-000411-281839974939-149`
  - `comp-ENC-POP-000631-093553807940-85`

エラーは全て `Composition.type` 要素で `java.net.SocketTimeoutException: Read timed out, code=exception`。

## fhirserver 単独応答時間 (直接 curl 計測、参考)

| operation | 応答時間 |
|---|---:|
| `CodeSystem/loinc/$validate-code` code=34823-5 ja | **4-16 ms** |
| `ValueSet/$validate-code` doc-typecodes VS ja | **88 ms** |
| `ValueSet/$expand` doc-typecodes ja | **800 ms** |
| 他 4 code の validate-code | **4-5 ms** |

**fhirserver は全 operation で 1 秒未満**。timeout の原因は fhirserver 応答ではない。

## 修正 4 手法の効果分析

### 1. Display() cache patch (fhirserver 内、v0.2 で適用済)

- 効果: **測定不能** (HAPI txCache warm で fhirserver 呼出頻度低い、baseline と v11 で同一結果)
- 論理的には正しい cache 化 (per-code SQL 削減) だが timeout には無関係

### 2. client `--chunk 30` (Bundle 内 code 密度低下)

- 効果: **speed +28%、timeout ±0**
- Bundle 密度と timeout は無関係、rps 改善は副産物

### 3. HAPI JVM socket timeout 180s (`sun.net.client.defaultReadTimeout`)

- 効果: **timeout ±0**
- HAPI validator の tx client (Apache HttpClient) は sun.net properties を尊重せず自前 config 使用の疑い
- 或いは timeout が実は tx call 経由ではなく、HAPI validator の internal timeout

### 4. `parallel=6` (low concurrency)

- 効果: **timeout ±0**
- concurrent lock contention は無関係、単一 JVM でも同じ Composition で fail
- **各 Composition 単体で HAPI validator が hang** することが確定

## 真の原因の推定

**HAPI validator が特定の Composition パターン (LOINC 34823-5 in Composition.type、profile 未指定) で内部処理に > 120 秒かかる**:

- 疑い 1: **VS 展開の無限 iteration** — Composition.type binding は `http://hl7.org/fhir/ValueSet/doc-typecodes` (extensible)、HAPI が LOINC 全体を走査する code path に入っている可能性
- 疑い 2: **HAPI validator の internal timeout の class** — HTTP socket 系ではなく Java concurrent の内部 wait
- 疑い 3: **base FHIR profile 未指定時の default validation path が特定 code で hang**
- fhirserver 側は無関係 (直接 curl で 5ms 応答)

## 修正案 (次段候補)

品質犠牲なしの案 (優先度順):

### A. Composition.type に profile 明示追加 (**generator 側修正、最短**)

profile 未指定 = HAPI が default validation path (VS 展開含む) を実行する origin。JP_Composition_Common や JP_Composition_eDS 等の profile を meta.profile に追加すれば、HAPI は profile 内定義に従い validate → default path 回避。

**期待効果**: -6 timeout (= 0 到達)、data-side 修正 1 行

### B. HAPI validator debug log で hang code path を特定

`-txLog /tmp/tx.log` や `-loglevel DEBUG` で HAPI 内部処理を dump し、無限 loop or 極端に遅い code path を特定。原因判明後、HAPI validator upstream patch or workaround を検討。

**期待効果**: 根治療法の候補創出

### C. 特定 Composition (LOINC 34823-5 + profile 未指定) を validator に投げる前に skip / warn

client 側 filter で「validator 側で hang するパターン」を事前 skip し別途 sample validation。

**リスク**: silent skip は品質犠牲、明示的 warn が必要

### D. HAPI validator を最新版 (7.x) に upgrade して同一パターン再検証

現行 6.9.11 で hang するが 7.x で改善されている可能性。

**期待効果**: 未知

## Session summary

- **fhirserver 側の性能仮説 (Display() cache) は正解ではなかった** — 本 patch は regression なく safety OK、但し timeout 削減 impact は 0
- **timeout の真因は HAPI validator の Composition.type validation 経路** で、client/JVM property/concurrency の全てが無関係
- **最速の修正は generator 側で該当 Composition に profile を明示追加** (推定 -6 timeout)

## caveat — 検証していないこと

- Observation の LOINC / SNOMED terminology 検証 (性能上スキップ、`HAPI_TX=n/a`)
- HAPI validator debug log 収集 (次段候補)
- HAPI 7.x upgrade

## raw ファイル

- `raw/rest.{meta,stdout,ndjson}` — baseline
- `raw/rest_chunk30.{meta,stdout,ndjson}` — chunk=30
- `raw/rest_httpto180.{meta,stdout,ndjson}` — HAPI socket timeout 180s
- `raw/rest_p6.{meta,stdout,ndjson}` — parallel=6
- `raw/obs.{meta,stdout,ndjson}`
- `.ndjson` gitignore
- `generator-metadata-snapshot.json`

## v0.2 の性能改善効果 (総括)

| 項目 | 結果 |
|---|---|
| Display() cache patch build/health/regression | **OK** ✅ |
| Display() cache patch による timeout 削減 | **効果測定不能** (HAPI txCache warm で発火なし) |
| Display() cache patch による rps 改善 | **測定不能** (同上) |
| client chunk 縮小による rps 改善 | **+28%** (副産物) |
| client chunk / HAPI socket / concurrency による timeout 削減 | **効果 0** (全 4 手法 6→6) |
| **generator 側で該当 Composition に profile 追加** | **未実施、期待 -6 timeout、次段候補** |
