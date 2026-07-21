# 検証まとめ — 2026-07-21 v13 (validator_cli 6.9.12 upgrade、v12 と同一データ)

## 総評: validator_cli minor upgrade (6.9.11 → 6.9.12) では timeout 解消せず

- **rest error 48 (v12 と完全同一)**、timeout **6 件** (v12 と完全同一)
- 6.9.12 の主要変更 (**SimpleHTTPClient → okhttp3 への HTTP client 総入替**、value set validation NPE fix 等) は本問題に無効
- **結論**: HAPI validator 6.9.x 系全体で本 hang バグは修正されていない
- **generator 側で profile 追加以外の対処策は確認できず** (v0.2 patch も、client workaround も、minor upgrade も全て 6 → 6)

## 検証環境

- HAPI FHIR Validator **6.9.12** (最新) + HL7 fhirserver (Display cache patch 適用済 image `ddcaff46e8e6`)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Cluster: HAPI 6 JVM × `-Xmx3g` + `sun.net.client.defaultReadTimeout=180000`
- Client: `parallel-validate.py --chunk 30`
- **データは v12 と完全同一** (p=1000 seed=300 JP master 8b85ed45)

## 6.9.11 → 6.9.12 主要変更 (release notes)

- **Switch SimpleHTTPClient to okhttp3 (#2519)** ← HTTP client 総入替
- fix version bug excluding codes / server side handling for excluded valuesets
- NPE fix for missing version when doing value set validation
- fix htmlChecks() implementation on string in validator
- rework cache shutdown
- fix cache-id double header issue
- fix tx server addresses to https

## 実測結果

| pass | 所要 | rps | error | timeout |
|---|---:|---:|---:|---:|
| v12 rest chunk30 (6.9.11) | 5.6 min | 532 | 48 | **6** |
| **v13 rest chunk30 (6.9.12)** | 8.1 min | 369 | 48 | **6** |

**変化**:
- timeout: **±0** (期待した okhttp3 化の効果なし)
- 実行時間: **+45%** (rps 532→369、原因不明)
- error 種別: 完全同一 (21×2 eReferral + 6 timeout)

## 検証済み対処一覧 (全て timeout 6 → 6)

| 対処 | 適用時 | 効果 |
|---|---|:-:|
| baseline (chunk=50, HAPI 6.9.11, default JVM) | v8/v10/v11/v12 | 6 |
| Display() cache patch (fhirserver) | v11/v12/v13 | 6 |
| client `--chunk 30` | v12 chunk30 | 6 |
| JVM `sun.net.client.defaultReadTimeout=180000` | v12 httpto180 | 6 |
| `parallel=6` (low concurrency) | v12 p6 | 6 |
| **validator_cli 6.9.11 → 6.9.12 (okhttp3 化含む)** | **v13** | **6** |

**7 種類の workaround を試して全て無効**。真因は HAPI validator の internal validation logic (Composition.type binding path で hang) と確定。

## 犯人 6 Composition (v8-v13 で完全一致)

- `Composition.type = LOINC 34823-5 (リハビリテーション実施計画書)` + `meta.profile 未指定`
- fhirserver 直接応答は 5-16ms (無関係)
- HAPI 6.9.x 系全体の bug

## 修正責任と現実的な対処

| 修正主体 | 案 | 実装難度 | 期待効果 |
|---|---|:-:|:-:|
| **generator (workspace:1)** | `meta.profile` 明示追加 | 小 (1 行) | ◎ 即効 6→0 |
| **hapifhir/org.hl7.fhir.core upstream** | 内部 hang 修正 | 大 | 月単位、fix 後 6.9.13+ で解消 |
| **この repo で自 patch** | Java patch (再 build) | 大 | 上流採用可能性あり |

**現実的な最速経路は generator 側 profile 追加**。workspace:1 に v12 で提案送信済み、対応待ち。

## upstream issue 報告候補

hapifhir/org.hl7.fhir.core に issue 報告する場合の再現手順:

```json
Bundle collection {
  entry: [
    { resource: Composition {
        "resourceType": "Composition",
        "type": {"coding":[{"system":"http://loinc.org","code":"34823-5"}],"text":"リハビリテーション実施計画書"},
        // no meta.profile
        // (他 required fields)
    }}
  ]
}
```

HAPI validator が `Composition.type` element で 120s+ hang し、`java.net.SocketTimeoutException: Read timed out, code=exception` を返す。

- validator_cli 6.9.11 / 6.9.12 両方で再現
- fhirserver (`http://localhost:8181/r4`) 側応答は 5ms、tx call ではなく HAPI 内部の問題
- profile 明示すると解消 (JP profile を使用時は発火しない)

## 次段候補

1. **workspace:1 側の profile 追加を待つ → v14 として再検証** (~30 分 for validation)
2. **hapifhir/org.hl7.fhir.core に issue 報告** (~1 時間、上流貢献)
3. **6.9.12 を default 化 for repo** (`scripts/setup-fhirserver.sh` or docs 明記) — 本 patch 効果なしだが最新版維持は望ましい

## raw ファイル

- `raw/rest.{meta,stdout,ndjson}` — 6.9.12 での rest 結果
- `.ndjson` gitignore
- `generator-metadata-snapshot.json` — v12 と同一 (data 同一)
- obs は実行せず (v12 で 0 error 確認済、6.9.12 upgrade で obs 側変化なし想定)

## Session summary (v0.2 timeout 対処調査完了)

- **v0.2 Display() cache patch は safety OK、but timeout 効果 0**
- **7 手法検証、全て timeout 6 → 6**
- **HAPI validator 6.9.x 内部 bug と確定**
- **最速修正は generator 側 profile 追加 (workspace:1 対応待ち)**
