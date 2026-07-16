# fhir-jp-validator

Local HL7 FHIR JP Core / JP-CLINS validation stack — HL7 純正 `fhirserver` (LOINC/SNOMED import CLI patch 付き) + HAPI Validator cluster (8 JVM streaming client)。Apple Silicon Mac (Rosetta 2) で amd64 emulation 最適化済み。

実測 (M3 Max 14 core、Docker Desktop 18GB): **343k FHIR resource を 28 分で 100% success 検証、平均 205 rps** (JP Core + JP-CLINS + jpfhir-terminology + LOINC + SNOMED 全 load、cache warm、`chunk=50 parallel=32`)。他構成の測定は [docs/benchmarks.md](docs/benchmarks.md)。

## 何を検証できるか

- FHIR R4 リソース (NDJSON) の JP Core 1.2.0 準拠性 (structure、slice、必須要素、拡張)
- JP-CLINS 1.12.0 (電子カルテ情報共有サービス実装ガイド) の eCS プロファイル制約
- LOINC 2.82 / SNOMED CT International の code 妥当性 + display 名一致
- JP Core / JP-CLINS の ValueSet メンバーシップ、日本 CodeSystem (JP_MedicationCode_VS 等)
- UCUM 単位 code

## 何を検証しないか

- **FHIR R4 のみ**。R4B / R5 / DSTU2 は非対応 (HAPI Validator 側の `-version` 引数変更で拡張可能だが、IG は差し替え要)
- **業務ロジック検証は対象外** — 診療報酬点数計算、レセプト整合、医療的妥当性 (投薬量チェック等) は行わない
- **Bundle Type validation は行わない** — client (`parallel-validate.py`) が入力 NDJSON を `Bundle.type=collection` に強制ラッピングするため、`transaction`/`document` 等の Bundle 制約はチェックされない
- **HL7 CDA / HL7 v2 / DICOM は対象外** — FHIR JSON リソースのみ
- **IG バージョンは固定** — JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0。旧版で検証したい場合は `jp_core/package/` と `HAPI_IG_EXTRA_DIRS` を差し替え

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│ fhirserver (Docker, port 8181)                              │
│   HL7 純正 4.0.8-SNAPSHOT (Pascal 実装)                     │
│   HAPI validator の tx-compat test を通る唯一の approved tx │
│   Load 済: HL7 terminology / JP Core / JP-CLINS /           │
│           jpfhir-terminology / LOINC / SNOMED               │
└─────────────────────────────────────────────────────────────┘
                       ↑ localhost:8181/r4
┌─────────────────────────────────────────────────────────────┐
│ HAPI Validator cluster (8 JVM, port 3001-3008)              │
│   -ig jp_core -ig JP-CLINS -ig jpfhir-terminology            │
│   -tx=http://localhost:8181/r4 -txCache=.hapi-cache/tx-cache│
│                                                              │
│   scripts/hapi-cluster.sh          — start/stop/status      │
│   scripts/parallel-validate.py     — Bundle streaming client │
└─────────────────────────────────────────────────────────────┘
```

補足: `docker compose --profile tx up -d hapi-tx` で HAPI FHIR JPA (port 3010) を追加起動可能。REST で `$expand` / `$validate-code` を対話的に試したい開発者向けのオプションで、validation 用途ではありません (HAPI Validator の tx-compat test を通らないので `-tx` には指定不可)。

## クイックスタート

### 1. 前提

- macOS Apple Silicon (M1/M2/M3)、Docker Desktop 4.30+ (Use Rosetta for x86/amd64 emulation を ON)、または amd64 Linux host
- Java 11+ (HAPI Validator 用)
- Python 3.10+ (parallel-validate.py 用、標準 library のみ使用)
- 40 GB のディスク空き (fhirserver 486 MB、SNOMED cache 846 MB、LOINC cache 841 MB、その他)
- 8 GB RAM (JVM 8 × 3 GB heap 前提の場合 24 GB 推奨)

### 2. Rosetta 2 有効化 (Apple Silicon のみ)

```bash
softwareupdate --install-rosetta --agree-to-license
# Docker Desktop の Settings → General → Use Rosetta for x86/amd64 emulation を ON、再起動
```

**Rosetta 未有効だと build 25 分 → QEMU で 2 時間、SNOMED import 10 分 → 4-8 時間になります**。必ず有効化してください。

### 3. リポジトリ clone

```bash
git clone https://github.com/TomoOkuyama/fhir-jp-validator.git
cd fhir-jp-validator
```

以降のコマンドは全て repo ルートで実行します。

### 4. fhirserver ビルド

```bash
./scripts/setup-fhirserver.sh   # HealthIntersections/fhirserver clone + patches 適用 + Docker build (5-8 分)
```

### 5. Terminology 入手 & 配置

`docs/terminology-setup.md` を参照。要点:

- JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0 は `jpfhir.jp` から DL (CC0)
- LOINC 2.82 は https://loinc.org/ でアカウント作成 → 無料 DL、ライセンス受諾要
- SNOMED CT International は https://uts.nlm.nih.gov/uts/ で UMLS ライセンス取得 → RF2 DL、**個人ライセンスは商用配布・共有 NG**

### 6. 検証実行

```bash
docker compose up -d fhirserver
./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py path/to/fhir_r4_dir/ --output result.json --parallel 32 --chunk 50
./scripts/hapi-cluster.sh stop
```

出力:
- `result.ndjson` — OperationOutcome ストリーム (1 行 = 1 リソース分の検証結果)
- `result.meta.json` — メタ (成功数、失敗数、rps、port 別統計)
- `result.failed.ndjson` — timeout 等で失敗した Bundle 一覧

出力の読み方・issue パターンの解釈・集計 recipe は [docs/output-guide.md](docs/output-guide.md) を参照。

## パフォーマンス

`docs/benchmarks.md` に詳細。実測 (343,478 res, 1/10 sample of a 3.43M dataset):

| 構成 | success | 総 issue | 平均 rps | 時間 |
|---|:---:|---:|---:|---:|
| HL7 + JP Core + LOINC + SNOMED (base) | 95.7% | 3.88M | 212 | 25.8 分 |
| +JP-CLINS | 100.0% | 4.55M | 174 | 32.9 分 |
| +jpfhir-terminology (cache warm) | **100.0%** | 3.95M | **205** | **28.0 分** |

## ライセンス

- 本リポジトリ (scripts, docs, patches): [MIT](LICENSE)
- fhirserver: BSD-3-Clause (HealthIntersections/fhirserver、patches は同ライセンス派生)
- HAPI Validator: Apache-2.0
- JP Core / JP-CLINS / jpfhir-terminology: CC0-1.0
- LOINC: LOINC License (無料、要ユーザ登録)
- SNOMED CT: UMLS Metathesaurus License (Affiliate または個人 UMLS ライセンス、**再配布不可**)

詳細は [docs/licensing.md](docs/licensing.md)。

## Contributing

Issues / PRs 歓迎。ただし SNOMED cache 等のライセンス制約対象データを含む PR は受け付けません。
