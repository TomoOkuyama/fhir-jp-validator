# 検証まとめ — 2026-07-20 v11 (fhirserver Display() cache patch 適用後、データ v10 と同一)

## 総評: Display() cache 効果は同一データ再現条件では測定不能

- **fail 率 v10 → v11 変化なし** (rest 226 errors、obs 0 errors、合計同一)
- **timeout 20 件は解消せず** — 期待していた「Display() cache 化で HAPI ↔ fhirserver tx timeout 消滅」は達成できず
- **HAPI-side txCache が warm ですでに大半をカバーしており、fhirserver Display() 呼出頻度が低く cache 効果が現れない条件**
- **v11 の実質意義**: patch が build 通り healthcheck 通り regression 起こしていないことを確認 (**patch の safety を validate**、実性能効果は測定できず)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, **patched + Display() cache**)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一 (image `ddcaff46e8e6`)
- Client: `parallel-validate.py` (defaults=retries4/timeout120)

## 検証データ

- **v10 と完全同一** (clinosim master 8b85ed45、p=5000 seed=500、431,784→wait 1,594,817 リソース)
- 目的: patch の性能効果を等条件で測定

## 実行 pass

| pass | 件数 | 所要 | rps | error |
|---|---:|---:|---:|---:|
| rest baseline | 667,696 | 21.7 分 | 513 | **226** |
| obs (5 chunk 集約) | 927,121 | 57.5 分 (5x sub-run) | 269 | **0** |
| **合計** | **1,594,817** | **79.2 分** | 336 | **226** |

**注**: 実行 harness の ~30 分 kill limit があり、obs は 5 chunk (310k/155k/155k/155k/152k) に分割実行して集約。合計時間は sub-run の単純和 (chunk 間の restart オーバーヘッド含まず)。

## v10 vs v11 比較

### エラー

| | v10 | v11 | 変化 |
|---|---:|---:|---:|
| rest error 総数 | 226 | 226 | ↔ |
| obs error 総数 | 0 | 0 | ↔ |
| eReferral slice (cross-bundle infra) | 206 | 206 | ↔ (client 側 sticky 未使用) |
| HTTP timeout (Composition) | 20 | 20 | ↔ (**Display() cache 効果なし**) |
| unique errored resources | 123 | 123 | ↔ |
| **fail 率** | **0.0129%** | **0.0129%** | ↔ |

### 性能

| | v10 | v11 | 変化 |
|---|---:|---:|---:|
| rest 所要 | 19.5 分 | 21.7 分 | +11% (JIT cold start on restart) |
| rest rps | 572 | 513 | -10% |
| obs 所要 (連続) | 60.3 分 | 57.5 分 (chunk 和) | -5% |
| obs rps | 256 | 269 | +5% |

## なぜ Display() cache 効果が測定できなかったか (分析)

### HAPI-side txCache が warm

`.hapi-cache/tx-cache/` は既に v6-v10 で warm 化されており、HAPI validator が同一 `(code, display, system, valueSet)` タプルを再度検証する際は **fhirserver を呼ばずローカルキャッシュを使う**。この状態では:

- HAPI が fhirserver に投げる validate-code call の数は少ない (miss のみ)
- Display() cache は fhirserver 内部で効くので、外部呼出が少なければ cache hit も少ない
- 結果: cache 有効/無効で外形的な差が現れない

### 20 timeout の性質

`java.net.SocketTimeoutException: Read timed out` は特定 Composition (~20 件、全て `.type` 要素) で発火。パターンから推定:

- HAPI txCache **miss** な `(code, display, system, VS)` タプル
- 該当 tuple の validate-code call が fhirserver で異常に長い
- Display() 以外の別要因: valueSet expansion、SNOMED 参照、complex expansion 等

**Display() cache patch は fhirserver 側の 1 SQL 削減が本質**であり、上記 timeout の主要因が別 (VS expansion / concurrent lock contention / etc.) の場合は効果が現れない。

### 直接測定 (curl による fhirserver 単独計測)

patch 適用後の validate-code (Japanese Accept-Language):
```
call 1 (cold): 11ms
call 2-4 (warm): 5-9ms
別 code cold: 4-5ms
```

これは **既に十分速い**。以前推定されていた「per-code 700ms」は tx cache miss + concurrent lock + VS expansion の合算だった可能性。**単純 code の Display() 単体では既にボトルネックではなかった**。

## Patch の validate 結果

- fhirserver build 通過 (最初 Pascal 型順序エラー → 修正、`TLoincDisplay` を `TLoincProviderContext` より前に宣言) ✅
- healthcheck 通過 ✅
- 各種 validate-code 直接 curl で正常応答 ✅
- v11 rest/obs validation 完走、regression なし (error 数完全一致) ✅

**patch は safety の意味で問題なく、既存機能を壊していない**。性能改善効果は測定条件を変える必要あり (下記)。

## 次にやるべきこと

Display() cache の実効果を測定するには以下いずれかの条件が必要:

1. **HAPI txCache を完全クリアして cold state で計測** (`rm -rf .hapi-cache/tx-cache/`) → fhirserver 呼出が最大化、Display() cache 有無で差が出る想定
2. **fhirserver を全て cold start 状態 + 別 seed の新規 data で計測** → HAPI/fhirserver 両側 cold で純粋な per-code コスト比較
3. **タイムアウト以外の指標を追う**: fhirserver 側 SQL query 数 (statsd/log 収集)、平均 tx call 応答時間の p50/p99

## 20 timeout の別対処案

Display() cache が効かない以上、timeout 解消には別方向のアプローチが必要:

| 案 | 変更範囲 | 期待 |
|---|---|---|
| **client 側 --chunk 20 --retries 6** | script 実行時パラメータのみ | Bundle 内 code 密度低下で per-call 負担軽減、+10-20% 実行時間 |
| **HAPI validator patch (`-check-display Ignore` を tx call payload まで伝播)** | Java patch、upstream 可能性 | display 送らず fhirserver 側 SQL 発生せず、劇的改善想定 |
| **VS expansion の fhirserver 側 cache** | Pascal patch (別位置) | validate-code の VS check 部分の高速化 |
| **valueSet を event.code に持たない Composition の識別 + 別 chunk** | client 側 grouping | 重い Composition を分離して timeout 回避 |

## 結論

- **Display() cache patch は正しく動作** (build/health/regression 全 OK)
- **v11 の性能特性は v10 と同一** — 期待した timeout 解消は達成できず
- **原因は「patch の対象が実際の bottleneck ではなかった」**: HAPI txCache が warm で fhirserver Display() が呼ばれる頻度が少なく、Display() の SQL 削減効果が現れない
- 次段は **HAPI patch (`-check-display Ignore` 伝播)** か **client 側 chunk 縮小 workaround** を試すべき

## raw ファイル

- `raw/rest.{meta,stdout,ndjson}` — rest pass
- `raw/obs_a/b1/b2/c1/c2.{meta,stdout,ndjson}` — obs sub-run
- `raw/obs.{meta,ndjson}` — 集約版 (5 chunk concat)
- `.ndjson` (~計 8GB) は gitignore
- `generator-metadata-snapshot.json` — clinosim meta

## Summary in one line

> **Display() cache patch は正しく実装され動作しているが、HAPI txCache warm 条件下では効果が測定できず、20 timeout は解消しなかった。真の bottleneck は別 (VS expansion / HAPI 側 display 伝播 / etc.)。**
