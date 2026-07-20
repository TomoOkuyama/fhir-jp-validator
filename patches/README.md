# fhirserver パッチ (BSD-3-Clause)

このディレクトリには HealthIntersections/fhirserver (BSD-3-Clause) に対する差分パッチが 4 つ含まれます:

## kernel.pas.patch

**目的**: fhirserver に LOINC / SNOMED CT のヘッドレスインポート CLI コマンドを追加。

**元の状況**: fhirserver は `importLoinc()` と `importSnomedRF2()` 関数を実装しているが、CLI エントリポイントが無く、`fhirserver -cmd loinc-import` のような使い方ができない。GUI (SNOMED editor / LOINC importer) からは実行可能。

**追加した機能**:

```
fhirserver -cmd loinc-import \
  -source <folder> -version <ver> -date <YYYY-MM-DD> -dest <output.cache>

fhirserver -cmd snomed-import \
  -source <RF2 folder> -uri <sct URI> -lang <byte> -dest <output.cache> \
  [-base <base folder>]
```

**変更箇所**: `server/kernel.pas`、~50 行追加。

## ftx_sct_services.pas.patch

**目的**: SNOMED import 時に POSIX locale で発生する `EConvertError: "20260601" is not a valid date` を修正。

**原因**: SNOMED RF2 の日付フィールド (yyyyMMdd 形式) を parse する際、`SNOMED_DATE_FORMAT.ShortDateFormat = 'dd/mm/yyyy'` に対して `DateSeparator` が未初期化のまま (POSIX ロケールでは空文字が入る) となり、`StrToDate` が失敗する。

**修正**: `SNOMED_DATE_FORMAT.DateSeparator := '/'` を明示的にセット。1 行追加。

**変更箇所**: `library/ftx/ftx_sct_services.pas` line 5515 付近。

## zero_config.pas.patch

**目的**: HTTP 最大接続数 (`http-max-conn`) を config で override 可能にし、default を 50 → 200 に引き上げる。

**元の状況**: `zero_config.pas:267` で `cfg.web['http-max-conn'].value := '50';` とハードコード。config file からの上書き経路が無く、fhirserver 起動時に必ず 50 になる。HAPI cluster (6 JVM × 8+ 並列 = 48 concurrent) と拮抗するため、大規模検証時のヘッドルームが不足しやすい。

**変更**: 他の web 設定と同じ `def(local.ReadString(...), ..., '200')` パターンに揃え、config 上書き可能かつ default 200 に。

```pascal
cfg.web['http-max-conn'].value :=
  def(local.ReadString('web', 'http-max-conn', ''), cfg.web['http-max-conn'].value, '200');
```

**注意**: 実測 (synthetic P=1〜64 の concurrent `$validate-code`) では 50→200 化による latency 改善は誤差レベルでした (真のボトルネックは接続数上限ではなく、fhirserver 内部のロック/シリアライゼーション)。とはいえ config 上書き経路が塞がっていた欠陥は解消しており、将来 fhirserver 内部を並列化した際にヘッドルームとして効きます。

**変更箇所**: `server/zero_config.pas` line 267。1 行変更。

## ftx_loinc_services.pas.patch

**目的**: `TLOINCServices.Display()` の per-context lazy cache 化。非英語 langList 呼び出しごとに Descriptions/Languages テーブルへ発行していた SQL クエリを、1 code = 1 回に削減する。

**元の状況** (`library/ftx/ftx_loinc_services.pas:830-877`):

- `Display(ctxt, langList)` が呼ばれるたびに `Select ... from Descriptions, Languages where CodeKey = X and DescriptionTypeKey in (1,2,5) ...` を実行
- LOINC の日本語 display 検証で毎リクエスト SQL 発火 → 実測 per-code ~700ms
- 更に `FLock` mutex で内部シリアライゼーションが働き、並列度を上げても実効スループット改善なし
- `Designations()` 側には既に per-context `FDisplays` cache があるのに、`Display()` 側は未 cache という設計非対称

**修正**:

- `TLoincProviderContext` に `FDisplayCache : TFslList<TLoincDisplay>` を追加 (nil 初期化)
- `Display()` 最初の非英語呼び出しで SQL + supplement を実行し `FDisplayCache` へ格納
- 2 回目以降は `FDisplayCache` を lock-check → in-memory langList match のみ
- Cache は per-context で LOINC/supplements が load-time 固定である前提 (fhirserver の他 provider と同じ扱い)
- 二重初期化は最初の winner を採用してもう一方は破棄 (`FDisplayCache.link` パターン)

**変更箇所**: `library/ftx/ftx_loinc_services.pas` line 111 + line 830 周辺、~40 行変更 (net +25 行)。

**期待効果**:
- 実運用の LOINC 日本語 display 検証で **per-code SQL 発生数 N → 1**
- HAPI ↔ fhirserver 間の tx call 応答時間短縮 (実測は `validation-results/` 次回 run で公表予定)
- v10 で残っていた 20 HTTP timeout (Composition の重い code 群で発火) の解消が主目標

**リスク**:
- Cache 有効性は「LOINC descriptions が起動後 immutable」前提。fhirserver は起動時に LOINC を読み込み、Descriptions テーブルは runtime 更新が想定されない。他の provider (SCT / UCUM) は既に load-time で全 in-memory index を持つ設計で、この前提は fhirserver 全体で一貫している。
- Cache miss 時の SQL は変更なし (query 文言と semantics は同一)、cache hit 時のみ SQL を省く。

**上流 PR 候補**: HealthIntersections/fhirserver に PR で提案予定 (BSD-3-Clause)。

## 適用方法

`scripts/setup-fhirserver.sh` が `patches/*.patch` を自動 iterate 適用しますが、手動で当てる場合:

```bash
cd tx-server-build/fhirserver   # HealthIntersections/fhirserver clone 済ディレクトリ
patch -p1 < ../../patches/kernel.pas.patch
patch -p1 < ../../patches/ftx_sct_services.pas.patch
patch -p1 < ../../patches/zero_config.pas.patch
patch -p1 < ../../patches/ftx_loinc_services.pas.patch
```

## 上流への PR について

fhirserver 上流 (HealthIntersections/fhirserver) にも PR で提案予定です。マージされたら本 repo のパッチは不要になります。

## ライセンス

fhirserver source が BSD-3-Clause なので、これらのパッチも同ライセンスの派生物として扱ってください。
