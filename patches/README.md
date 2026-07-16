# fhirserver パッチ (BSD-3-Clause)

このディレクトリには HealthIntersections/fhirserver (BSD-3-Clause) に対する差分パッチが 2 つ含まれます:

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

## 適用方法

`scripts/setup-fhirserver.sh` が自動適用しますが、手動で当てる場合:

```bash
cd tx-server-build/fhirserver   # HealthIntersections/fhirserver clone 済ディレクトリ
patch -p1 < ../../patches/kernel.pas.patch
patch -p1 < ../../patches/ftx_sct_services.pas.patch
```

## 上流への PR について

fhirserver 上流 (HealthIntersections/fhirserver) にも PR で提案予定です。マージされたら本 repo のパッチは不要になります。

## ライセンス

fhirserver source が BSD-3-Clause なので、これらのパッチも同ライセンスの派生物として扱ってください。
