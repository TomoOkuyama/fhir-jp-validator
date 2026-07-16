# アーキテクチャ詳細

## なぜ HL7 純正 fhirserver か

HAPI Validator は `-tx` に渡す terminology server に対して起動時 **tx-compat test** を実行し、以下の feature を advertise していない tx server は `is not approved for use` と判定して起動失敗させます:

- `http://hl7.org/fhir/uv/tx-tests/FeatureDefinition/test-version` = 1.8.0
- `http://hl7.org/fhir/uv/tx-ecosystem/FeatureDefinition/CodeSystemAsParameter` = true

主要な OSS FHIR サーバとの互換性:

| tx server | HAPI 互換 | 備考 |
|---|:---:|---|
| **HL7 fhirserver (Pascal)** | ✅ | GitHub: `HealthIntersections/fhirserver`。Grahame Grieve 管理、tx.fhir.org の実体。**唯一の approved local tx** |
| HAPI FHIR JPA (Java) | ❌ | `feature-query` 未実装、起動失敗 |
| Firely Server | 未確認 | 商用ライセンス |

## fhirserver の challenge (と本 repo の対処)

HL7 fhirserver は素晴らしい tx server ですが、以下の制約:

1. **GHCR image は private** — GitHub Packages で `HealthIntersections` org private、`docker pull` 不可
2. **Linux binary release なし** — GitHub Releases に Mac/Windows のみ、Linux は user が build 必須
3. **LOINC/SNOMED を import する CLI が無い** — 内部 API は `importLoinc()`/`importSnomedRF2()` 実装済だが CLI エントリなし
4. **SNOMED import が POSIX locale で crash** — `SNOMED_DATE_FORMAT.DateSeparator` 未初期化で `EConvertError` 発生

本 repo は上記を全て解決:

1. **Docker build を Ubuntu 24.04 + Free Pascal Compiler で local build**
2. **`patches/kernel.pas.patch`** で `-cmd loinc-import` / `-cmd snomed-import` CLI を追加
3. **`patches/ftx_sct_services.pas.patch`** で SNOMED DateSeparator を明示初期化

## Apple Silicon 対応

fhirserver の Pascal ソースは amd64 前提で、arm64 native build は難易度高。よって amd64 image を Rosetta 2 経由で実行します。

**Rosetta 2 実効化のポイント**:

- macOS 側 `softwareupdate --install-rosetta`
- Docker Desktop の Settings → General → **Use Rosetta for x86/amd64 emulation** を ON
- 有効化後、Docker Desktop 再起動

実効化していないと Docker Desktop が QEMU にフォールバック、build/import が 5-10 倍遅くなります (SNOMED import 実測 QEMU 4-8 時間 → Rosetta 9 分 50 秒)。

## HAPI Validator クラスタ設計

### 8 JVM 並列の理由

- HAPI Validator CLI (`validator_cli.jar`) は HTTP server モードで 1 プロセス = 1 JVM (`java -jar ... server <port>`)
- 単一 JVM は CPU 1 core しか使わない (validation 処理は主にシングルスレッド内で完結)
- Apple Silicon M3 Max (14 core) 上で **8 JVM 並列**で MacBook をほぼ full 稼働。JVM 数を 12/16 に増やすと fhirserver 側が bottleneck 化
- JVM 1 個あたり `-Xmx3g` (合計 24 GB RAM 消費前提)

### streaming client (parallel-validate.py) の設計

- **Bundle 生成は generator lazy** — 全部メモリに載せない (3.4M res 対応)
- **ThreadPoolExecutor + `wait(FIRST_COMPLETED)`** で back-pressure、in-flight 上限を `parallel × 2` に制限
- **OperationOutcome は 1 行 = 1 リソースの NDJSON に逐次書き出し** — I/O バッファも最小
- **サーキットブレーカ**: port ごとに連続失敗 10 回で 60 秒 quarantine (JVM 停止時に有効な JVM に振り分ける)

## Terminology load 順序

fhirserver 起動時に:

1. `~/.fhir/packages/` に無い IG は npm registry (packages.fhir.org) から DL、既存なら cache 使用
2. `packages.ini` に列挙された order で load
3. `config.json` の `content.uv.files` に指定された `.cache` (LOINC/SNOMED) を追加 load
4. 起動時 total ~40 秒 (cache 既存の場合)

HAPI Validator クラスタ起動時に:

1. `-ig` で指定した各 IG を load (JP Core 284 res + JP-CLINS 296 res + jpfhir-terminology 210 res)
2. `-ig` に加え、`~/.fhir/packages/` の各種 HL7 terminology を auto load (合計 ~10 IG)
3. 起動時 total ~20 秒 (cache 既存の場合)

**初回実行時は on-demand で外部 IG (US Core、VSAC、PHINVADS 等) を DL する場合あり、その JVM だけ数分 stall する可能性あり**。cache warm 化後 (2 回目以降) は問題なし。
