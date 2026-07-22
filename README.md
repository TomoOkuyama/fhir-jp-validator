# fhir-jp-validator

日本の医療 FHIR データ (JP Core 1.2.0 / JP-CLINS 1.12.0) を local 環境で検証するための OSS
スタック。HL7 純正 `fhirserver` (LOINC/SNOMED import CLI patch 付き) + HAPI Validator の 6-JVM
並列 cluster + Bundle streaming client の 3 層構成。Apple Silicon Mac (Rosetta 2) で amd64
emulation に最適化。

代表的な性能: **1/10 サンプル 343k FHIR resource を約 28 分・平均 205 rps で 100% success 検証**
(cache warm、JP Core + JP-CLINS + jpfhir-terminology + LOINC + SNOMED 全 load、6 JVM × 3g heap)。
data の terminology 充実度により rps は変動 (詳細: [docs/benchmarks.md](docs/benchmarks.md))。

## 何を検証できるか

- FHIR R4 リソース (NDJSON) の JP Core 1.2.0 準拠性 (structure、slice、必須要素、拡張)
- JP-CLINS 1.12.0 (電子カルテ情報共有サービス実装ガイド) の eCS プロファイル制約
- LOINC 2.82 / SNOMED CT International の code 妥当性 + display 名一致
- JP Core / JP-CLINS の ValueSet メンバーシップ、日本 CodeSystem (`JP_MedicationCode_VS` 等)
- MHLW ICD-10 2013 版 (`ICD10-2013-full`) の code 参照 (fragment CS のため 2,000 concept まで
  完全 verify、それ以外は warning で通過)
- UCUM 単位 code

## 何を検証しないか

- **FHIR R4 のみ**。R4B / R5 / DSTU2 は非対応 (`-version` 引数変更 + IG 差し替えで拡張可)
- **業務ロジック検証は対象外** — 診療報酬点数計算、レセプト整合、投薬量チェック等の医療的
  妥当性は行わない
- **Bundle Type validation は行わない** — client (`parallel-validate.py`) が入力 NDJSON を
  `Bundle.type=collection` に強制ラッピングするため、`transaction` / `document` 等の Bundle
  制約はチェックされない
- **HL7 CDA / HL7 v2 / DICOM は対象外** — FHIR JSON リソースのみ
- **IG バージョンは固定** — JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0。
  他バージョンで検証する場合は `jp_core/package/` と `HAPI_IG_EXTRA_DIRS` を差し替え

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│ fhirserver (Docker, port 8181)                              │
│   HL7 純正 4.0.8-SNAPSHOT (Pascal 実装)                       │
│   HAPI Validator の tx-compat test を通る approved local tx  │
│   Load: HL7 terminology / JP Core / JP-CLINS /                │
│         jpfhir-terminology / LOINC / SNOMED                   │
└─────────────────────────────────────────────────────────────┘
                       ↑ localhost:8181/r4 (tx-compat REST)
┌─────────────────────────────────────────────────────────────┐
│ HAPI Validator cluster (6 JVM, port 3001-3006)              │
│   -ig jp_core -ig JP-CLINS -ig jpfhir-terminology            │
│   -tx=http://localhost:8181/r4 -txCache=.hapi-cache/tx-cache  │
│                                                              │
│   scripts/hapi-cluster.sh          — start/stop/status        │
│   scripts/parallel-validate.py     — Bundle streaming client  │
└─────────────────────────────────────────────────────────────┘
```

役割分担・分割戦略・検証フローの詳細は
[docs/architecture.md](docs/architecture.md#validation-中の役割分担-hapi--fhirserver)。

## リポジトリ構成

| 場所 | 内容 |
|---|---|
| `scripts/` | `setup-fhirserver.sh` (fhirserver Docker image build)、`hapi-cluster.sh` (HAPI validator cluster start/stop)、`parallel-validate.py` (NDJSON streaming client)、`reconcile-test-cases.py` (regression suite) |
| `patches/` | fhirserver source に適用する patch (LOINC/SNOMED import CLI 追加、SNOMED locale bug fix 等) |
| `docs/` | 全ドキュメント (setup / architecture / benchmarks / output 読解 / 実データ運用) |
| `jp_core/` | JP Core 1.2.0 FHIR IG (setup script 後に populate、setup-time で DL) |
| `tx-server-build/` | fhirserver source clone・IG cache・LOINC/SNOMED cache (build/setup script 生成、大半 gitignore) |
| `hapi-tx/` | オプションの HAPI FHIR JPA server 設定 (対話探索用、validation では使わない) |
| `test-cases/` | 意図的に問題を含む FHIR resource を並べた regression 監視スイート (200 case)。`reconcile-test-cases.py` で「期待通り error/warning が出るか」を判定 |
| `validation-results/` | 参考検証結果 (合成データに対する run の raw log と分析)、run 単位で格納 |
| `docker-compose.yml` | fhirserver container 定義 + オプションの HAPI FHIR JPA (`profiles: ["tx"]`) |

## クイックスタート

Docker / Linux コマンドや FHIR terminology 全般に不慣れな方は、
**先に [`docs/fhirserver-setup-for-beginners.md`](docs/fhirserver-setup-for-beginners.md)** を
参照してください。以下は概要のみです。

### 1. 前提

- macOS Apple Silicon (M1/M2/M3)、Docker Desktop 4.30+ (Use Rosetta for x86/amd64 emulation を ON)、または amd64 Linux host
- Java 11+ (HAPI Validator 用)
- Python 3.10+ (parallel-validate.py 用、標準 library のみ使用)
- 40 GB のディスク空き (fhirserver 486 MB、SNOMED cache 846 MB、LOINC cache 841 MB、その他)
- 24 GB RAM 推奨 (JVM 6 × 3 GB heap = 18 GB + fhirserver 4 GB + client 数 GB)

### 2. Rosetta 2 有効化 (Apple Silicon のみ)

```bash
softwareupdate --install-rosetta --agree-to-license
# Docker Desktop の Settings → General → Use Rosetta for x86/amd64 emulation を ON、再起動
```

**Rosetta 未有効時は build 5-8 分 → QEMU で ~2 時間、SNOMED import ~10 分 → 4-8 時間**
になるため必ず有効化してください。

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

[`docs/terminology-setup.md`](docs/terminology-setup.md) 参照。要点:

- JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0 は `jpfhir.jp` から DL (CC0)
- LOINC 2.82 は https://loinc.org/ でアカウント作成 → 無料 DL、ライセンス受諾要
- SNOMED CT International は https://uts.nlm.nih.gov/uts/ で UMLS ライセンス取得 → RF2 DL、
  **個人ライセンスは商用配布・共有 NG**

### 6. 検証実行

```bash
docker compose up -d fhirserver
./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py path/to/fhir_r4_dir/ --output result.json --parallel 24 --chunk 30
./scripts/hapi-cluster.sh stop
```

出力:
- `result.ndjson` — OperationOutcome ストリーム (1 行 = 1 Bundle 分、Bundle 内全リソースの
  issue が 1 OC に集約)
- `result.meta.json` — メタ (成功数、失敗数、rps、port 別統計)
- `result.failed.ndjson` — timeout 等で失敗した Bundle 一覧

出力の読み方・issue パターンの解釈・集計 recipe は
[`docs/output-guide.md`](docs/output-guide.md) を参照。

**実データ (Observation 主体の JP EHR) を通す際の推奨構成・落とし穴・頻出 issue** は
[`docs/real-world-validation.md`](docs/real-world-validation.md) に。Observation の
日本語 display validation が bottleneck になるため、rest / obs 分割 + sticky Reference の
運用パターンを推奨。

参考検証結果 (合成データに対する実測) は [`validation-results/`](validation-results/) に
run 単位で格納。

## パフォーマンス

[`docs/benchmarks.md`](docs/benchmarks.md) に詳細。1/10 sample (343,478 res) を、terminology
load を段階的に増やして検証:

| 構成 | success | 総 issue | 平均 rps | 時間 |
|---|:---:|---:|---:|---:|
| HL7 + JP Core + LOINC + SNOMED (base) | 95.7% | 3.88M | 212 | 25.8 分 |
| + JP-CLINS | 100.0% | 4.55M | 174 | 32.9 分 |
| + jpfhir-terminology (cache warm) | **100.0%** | 3.95M | **205** | **28.0 分** |

## ライセンス

- 本リポジトリ (scripts, docs, patches): [MIT](LICENSE)
- fhirserver: BSD-3-Clause (HealthIntersections/fhirserver、patches は同ライセンス派生)
- HAPI Validator: Apache-2.0
- JP Core / JP-CLINS / jpfhir-terminology: CC0-1.0
- LOINC: LOINC License (無料、要ユーザ登録)
- SNOMED CT: UMLS Metathesaurus License (Affiliate または個人 UMLS ライセンス、**再配布不可**)

詳細は [`docs/licensing.md`](docs/licensing.md)。

## Contributing

Issues / PRs 歓迎。SNOMED cache 等のライセンス制約対象データを含む PR は受け付けません。
