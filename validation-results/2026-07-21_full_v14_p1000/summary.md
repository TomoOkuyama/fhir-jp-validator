# 検証まとめ — 2026-07-21 v14 (v12 と同一データ、`-txCache` 完全クリア後)

> **英語 canonical writeup**: [../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md)
> — 上流 (hapifhir/org.hl7.fhir.core) 向けの issue 参照ポイント。

## 総評: **HAPI validator 側 txCache 汚染が真因と確定** — cache clear のみで v12 の 6 timeout が完全消滅

- **同一データ + 同一 fhirserver + 同一 validator jar** で、v12 (kept cache) と v14 (cleared cache) を比較
- v12 rest: **6 timeout**、7 種類の workaround で不変
- v14 rest: **0 timeout** — cache dir を wipe してから同じ pass を回しただけ
- **fhirserver / client / JVM は無関係**、`org.hl7.fhir.r5.terminologies.utilities.TerminologyCache` が SocketTimeout を永続化していた

## 検証環境

- HAPI FHIR Validator **6.9.12** (v13 で upgrade 済み、Display cache patch 適用 fhirserver)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Cluster: HAPI 6 JVM × `-Xmx3g` + `HAPI_HTTP_READ_TIMEOUT_MS=default` (v12 の 180s も無効だったので default に戻し)
- Client: `parallel-validate.py --chunk 30 --parallel 24`

## 検証データ

- **v12 と完全同一** (clinosim master 8b85ed45、p=1000 seed=300 JP、431,784 リソース)
- 変更点: `.hapi-cache/tx-cache/` を **バックアップ → 完全 wipe → 空 dir で cluster 再起動**

## 実行 pass

| pass | 件数 | 所要 | rps | error | timeout |
|---|---:|---:|---:|---:|---:|
| rest (fresh cache) | 178,818 | 10.9 分 | 273 | 26,238 | **0** |

**注**: error 26,238 のうち大半 (~26,196) は `text/plain; charset=utf-8` の MimeType VS 不整合 — これらは **v12 では cache に "成功" として保存されており見えなかった**。cache clear が SocketTimeout 永続化と同時に「隠されていた valid error」も露出させた形。

## エラー内訳

| # | カテゴリ | 由来 |
|---:|---|---|
| 13,098 × 2 = **26,196** | `text/plain; charset=utf-8` MimeType VS 未包含 | v12 では cache が success を返していた偽陰性 |
| 21 × 2 = **42** | eReferral `referralFromSection` / `referralToSection` Organization slice | cross-bundle infra artifact (Chain #329、v6.1〜継続) |
| **0** | HTTP timeout | **完全消滅** (v12 の 6 件が全て cache 由来だったと確定) |

## v12 と v14 の diff (timeout のみ抜粋)

| | v12 (poisoned cache) | v14 (fresh cache) |
|---|:-:|:-:|
| resources_total | 178,818 | 178,818 |
| jar version | 6.9.12 | 6.9.12 |
| fhirserver | 同一 image | 同一 image |
| tx server 実応答 (curl 直接) | 5–16 ms | 5–16 ms |
| HAPI 側 tx call 結果 | **cached SocketTimeout** (6 tuple) | **live 成功** (6 tuple 全 0.04–1.5 s) |

## 6 tuple 個別 live 実行結果 (fresh cache、参考)

`.hapi-cache/tx-cache/` を wipe した状態で、6 Compositions を単独 Bundle として順次 POST した結果:

| Composition id | live 応答時間 |
|---|---:|
| `comp-ENC-POP-000033-224923531116-187` | 1.51 s |
| `comp-ENC-POP-000270-188036175455-107` | 0.20 s |
| `comp-ENC-POP-000380-231140288681-119` | 1.28 s |
| `comp-ENC-POP-000411-281839974939-149` | 1.27 s |
| `comp-ENC-POP-000546-245245476108-135` | 0.04 s |
| `comp-ENC-POP-000631-093553807940-85`  | 0.04 s |

**6 件全て 2 秒未満で valid 応答** → HAPI の 15s hardcoded / 30s operation / どの timeout にも触れず、cached 版だけがずっと Read timed out を返していた。

## poisoned cache の内容 (backup した `.hapi-cache/tx-cache.v13.bak/loinc.cache` 実測)

```
{"code" : {
  "coding" : [{"system":"http://loinc.org","code":"34823-5"}],
  "text" : "リハビリテーション実施計画書"
}, "url":"http://hl7.org/fhir/ValueSet/doc-typecodes", ...}
####
e: {
  "error" : "java.net.SocketTimeoutException: Read timed out",
  "class" : "SERVER_ERROR",
  "issues" : { ... }
}
```

`"class" : "SERVER_ERROR"` として persistent 保存されていた。

## upstream に報告

- `org.hl7.fhir.r5.terminologies.utilities.TerminologyCache#store` が
  `TerminologyServiceErrorClass.SERVER_ERROR` / `NOSERVICE` を除外していない
- `TerminologyServiceErrorClass#isInfrastructure()` メソッド (既存) を使えば minimal patch で修正可能
- 別途 issue + PR を検討中、詳細は [../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md)

## caveat

- 26,196 件の MimeType 不整合 error は **cache 汚染とは無関係の real data issue** で、workspace:1 (clinosim) 側で対応対象
- v14 は「HAPI cache 汚染」と「MimeType real error」を切り分けするだけの実測、data compliance の観点では v12 → 別問題を再露出させただけ

## raw ファイル

- `raw/rest.{meta,stdout,ndjson}` — chunk=30 pass
- `.ndjson` gitignore
- `generator-metadata-snapshot.json` — v12 と同一
- obs は実行せず (v12 で 0 error 確認済、cache 汚染は rest 側だけの現象)
