# 2026-07-21 v15 — clinosim PR #344 検証 (MimeType charset drop)

## 位置付け

v14gen で unmask された data 側 issue に対する fix の検証。

| run | 変数 | 目的 |
|---|---|---|
| v14 | `.hapi-cache/tx-cache/` wipe | HAPI cache poisoning 真因確定、副作用として MimeType issue 26k を unmask |
| v14gen | clinosim PR #342 (Composition profile 宣言) | HAPI VS 展開 default path 回避で timeout 再発予防 (6→0) |
| **v15** | **clinosim PR #344** (Attachment.contentType の charset drop) | v14gen で残った 23,556 件の MimeType binding error を解消 |

## 何が変わったか (vs v14gen)

**clinosim 側のみ** 1 PR (master `ef9d7706`):

- `DocumentReference.content[N].attachment.contentType`: `"text/plain; charset=utf-8"` → `"text/plain"`
- `DiagnosticReport.presentedForm[N].contentType`: 同上
- FHIR R4 `MimeType` binding (BCP 13 = RFC 6838 registered media types、parameter 無し) に完全準拠

fhir-jp-validator 側は変更なし。validator_cli 6.9.12、fhirserver、cluster 設定、`-txCache` 全て v14gen と同一。

**pre-verify**: 生成データ内の 13,098 件全て bare `text/plain` (charset parameter 残存 0 件)。

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (HL7 fhirserver、warm cache 継承)
- Client: `parallel-validate.py --chunk 30 --parallel 24`
- Data: 178,818 rest + 252,966 obs = 431,784 res (合成データ、`clinosim` v0.2.0, `country=JP`, `population=1000`, `seed=300`)

## Result

| pass | 件数 | 所要 | rps | error | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181) | 178,818 | 7.6 min | 394 | **42** | 21 | 0.012% | **0** |
| obs (tx=n/a) | 252,966 | 16.7 min | 252 | **0** | 0 | 0.000% | **0** |
| **合計** | **431,784** | **24.3 min** | 296 | **42** | **21** | **0.0049%** | **0** |

- **PR #344 効果**: rest error **26,238 → 42** (-99.84%)、MimeType binding error 全消滅
- **rest pass rps**: 366 → **394** (+7.7%) — MimeType tuple の重複 VS lookup 消失で若干高速化
- **regression 無し**: 他 resource / 他 profile の error 数不変
- **fail 率 0.0049%** は v10 (0.0063%) を下回る過去最良水準 (p=1000, seed=300 の異なるデータセットゆえ厳密比較不可だが、絶対値としては最も低い)

## 残 error 42 件の内訳

全て **Composition eReferral cross-bundle slice** 由来:

| slice | 件数 |
|---|---:|
| `Composition.section:referralFromSection.entry:referralFromOrganization` (min=1) | 21 |
| `Composition.section:referralToSection.entry:referralToOrganization` (min=1) | 21 |

これは生成データ側は正しく `Organization` を出力しているが、`parallel-validate.py` が Bundle 分割時に別 NDJSON にある target を含められない client-side infra 制約 (v8 以降同じ 42 件で持続)。生成器側の課題ではない。

### client-side 解消手段 (実測確認済み)

`--include-file` (sticky Reference 前置) で Organization をすべての Bundle に混ぜれば消える。
[`docs/real-world-validation.md`](../../docs/real-world-validation.md#43-cross-bundle-reference-の解決---include-file) 4.3 節に手順・トレードオフを追記。

**demo (同 v15 data、Composition.ndjson のみを対象に再検証)**:

```bash
./scripts/parallel-validate.py Composition.ndjson --output demo.json \
  --chunk 30 --parallel 24 \
  --include-file fhir_r4/Organization.ndjson
# → 4523 res, 0 errors (通常実行の 42 errors 完全消滅)
```

raw log: [`raw/rest_composition_with_sticky.stdout.log`](raw/rest_composition_with_sticky.stdout.log) / [`raw/rest_composition_with_sticky.meta.json`](raw/rest_composition_with_sticky.meta.json)

## v13 → v14 → v14gen → v15 完全比較

| run | timeouts | rest error | rest fail% (res) | obs error | 合計 fail% |
|---|---:|---:|---:|---:|---:|
| v13 (poisoned cache) | 6 | 48 | 0.017% | 0 | 0.011% |
| v14 (cache wipe) | 0 | 26,238 | 7.34% | 0 | 3.04% |
| v14gen (+ PR #342) | 0 | 26,238 | 7.34% | 0 | 3.04% |
| **v15 (+ PR #344)** | **0** | **42** | **0.012%** | **0** | **0.0049%** |

v13 の 48 error のうち 6 が false negative (timeout)、42 が真の eReferral 制約。v14/v14gen の 26,238 は
真の MimeType binding violation が cache wipe で unmask された結果。v15 は真の error だけが残った状態
= data 品質の実力値。

## 結論

- PR #344 は **想定通りの効果と 0 regression**
- clinosim generator の data 品質は「eReferral cross-bundle infra 課題を除けば全リソース pass」水準に到達
- 次 chain 候補: client-side `--include-file` docs 追加 (残 21 件解消)、または clinosim 側の他改善

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
