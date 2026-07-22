# アーキテクチャ詳細

## Validation ロジック概要

本 repo が行う validation は **FHIR 準拠性検証** — リソースが「structure」「binding」
「invariant」を満たすかの機械判定です。実施される check の categories:

| category | 例 | 主体 |
|---|---|---|
| **structure** | Element の datatype、cardinality (min/max)、必須 (`min=1`)、`extension` URL の位置 | HAPI |
| **profile 適合** | `meta.profile` または base R4 + JP Core が要求する slice discriminator、`patternCoding`、`fixedValue` | HAPI |
| **datatype rule** | `id` = `[A-Za-z0-9\-\.]{1,64}`、`code` = `[^\s]+` 等の spec 上の型制約 | HAPI |
| **invariant** | FHIRPath 式による制約 (`ele-1: @value or children`、`dom-6: narrative`、`con-4` 等) | HAPI |
| **Reference resolve** | `Reference.reference` が Bundle 内 (もしくは include 済 sticky) で解決できるか | HAPI |
| **code 実在** | `coding.code` が指定 `system` の CodeSystem に登録されているか | fhirserver |
| **display 名一致** | `coding.display` が CodeSystem の canonical display と一致するか | fhirserver |
| **binding conformance** | required / extensible binding の ValueSet に code が含まれるか | HAPI + fhirserver |
| **ValueSet 展開整合性** | ValueSet 展開結果に対する membership check | fhirserver |

本 repo が行わない check:
- 業務ロジック (投薬量、診療報酬計算、レセプト整合、臨床的妥当性)
- Bundle Type validation (`transaction` / `document` の追加制約)
- FHIR R4 以外の版 (R4B / R5 / DSTU2)
- CDA / HL7 v2 / DICOM 等の非 FHIR フォーマット

処理の詳細フロー (HAPI と fhirserver の責務境界) は
[Validation 中の役割分担](#validation-中の役割分担-hapi--fhirserver) 節を参照。

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

なお本 repo の `docker-compose.yml` には `profiles: ["tx"]` で **HAPI FHIR JPA server** (port 3010) も同梱しています。これは **validator の `-tx` としては使えません** (上表の通り tx-compat test 失敗) が、以下の用途では有用です:

- REST で `$expand` / `$validate-code` / `$lookup` を対話的に叩いて terminology を探索
- JP Core / JP-CLINS の ValueSet や CodeSystem の内容を human-readable に確認
- `application.yaml` を差し替えて `hapi.fhir.narrative_enabled` 等の実験

起動: `docker compose --profile tx up -d hapi-tx`。停止: `docker compose --profile tx down`。通常の validation 実行時は起動不要です。

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

## Validation 中の役割分担 (HAPI ↔ fhirserver)

「なぜ 2 プロセス必要か」「1 リソースの検証で何が起きているか」を最短で理解するための節。

### 一言まとめ

- **HAPI Validator (JVM)** = 検証の司令塔・実行主体。**「構造の理屈」** を全担当
- **fhirserver** = 用語 DB 専任。**「用語の辞書引き」** だけを担当
- HAPI は code 実在確認が必要になった瞬間だけ fhirserver に HTTP で問い合わせる

### 1 リソース検証の流れ

```
[ 入力リソース (Observation, Composition, ...) ]
        ↓
┌────────────────────────────────────────────────────────────┐
│ HAPI Validator (JVM)                                       │
│                                                            │
│ ① meta.profile または base R4 + JP IG から profile 選択      │
│ ② StructureDefinition を辿って要素を検査:                    │
│    - cardinality (min/max 出現数)                            │
│    - datatype (id, code, CodeableConcept, Reference, ...)   │
│    - slice discriminator (どの slice に属するか)              │
│    - invariant (FHIRPath 式、例: con-4, dom-6, ele-1)        │
│    - extension URL の位置と型                                 │
│    - Reference の型と Bundle 内 resolve()                    │
│ ③ 各 coding フィールドで code 実在/display 一致の判定が要     │
│    → tx server に HTTP call                                  │
│                                                            │
│ ⑤ tx から結果受領 → issue リストに反映                        │
│ ⑥ 全 issue を集約して OperationOutcome を返す                 │
└────────────────────────────────────────────────────────────┘
              ↓ ③ HTTP POST            ↑ ④ 結果 JSON
┌────────────────────────────────────────────────────────────┐
│ fhirserver (Pascal, port 8181)                             │
│                                                            │
│ ・$validate-code (CodeSystem/ValueSet 内の code 実在 + display) │
│ ・$expand (ValueSet 展開、メンバー列挙)                        │
│ ・$lookup (code の親子関係、display 名、property)              │
│                                                            │
│ 応答 latency: 単純 code = 5-16ms、JP 日本語 display 系 = ~700ms │
└────────────────────────────────────────────────────────────┘
```

### 責務境界表

| 判定内容 | HAPI Validator | fhirserver |
|---|:---:|:---:|
| profile 適合 (slice / cardinality / extension / invariant) | ✅ | ❌ |
| datatype rule (id は 1-64 字、code は `[^\s]+` 等) | ✅ | ❌ |
| Bundle 内 `Reference.resolve()` | ✅ | 対象外 |
| FHIRPath invariant 評価 (con-4 等) | ✅ | 対象外 |
| **code 実在確認** (LOINC 1751-7 は本当にある?) | ❌ | ✅ |
| **display 名一致** (「アスパラギン酸アミノトランスフェラーゼ」正解?) | ❌ | ✅ |
| **ValueSet メンバーシップ** (MimeType VS に text/plain が含まれる?) | ❌ | ✅ |
| ValueSet 展開の中身取得 | ❌ | ✅ |

**HAPI 側単独では、code / display / ValueSet に関する判定は一切できない**。
逆に、**fhirserver 単独では profile 適合性を判定できない**。両者は相補的で、片方だけでは
不完全な validation にしかならない。

### 分割戦略 (`-tx n/a`) が有効な理由

`hapi-cluster.sh start` 時に `HAPI_TX=n/a` を指定すると、HAPI は tx への call を全て skip:

- **消える判定**: code 実在確認、display 一致、ValueSet メンバーシップ
- **残る判定**: profile 適合、datatype、slice discriminator (code system を問わない部分)、
  invariant、extension、Reference resolve

日本の EHR データでは Observation の日本語 LOINC display 検証が fhirserver 側で per-code
~700ms かかり全体の律速要因になる。**Observation だけを `-tx n/a` で構造検証、他 25 種を
`-tx` 有効で完全検証** という 2 phase 分割で全体スループットが大きく改善する (単一 pass 全 tx
有効では 200k res 級で完走困難、分割で ~200-300 rps を安定維持)。

### error 分類例

| error 種 | 判定した主体 | tx call 発生? |
|---|---|:---:|
| `Slice X: minimum required = 1, but only found 0` | HAPI (slice discriminator) | ❌ |
| `Constraint failed: ele-1 (@value or children)` | HAPI (invariant) | ❌ |
| `Unknown code 'X' in the CodeSystem 'Y'` | fhirserver → HAPI に伝達 | ✅ |
| `code 'X' not in ValueSet 'Y'` (required binding 違反) | fhirserver → HAPI | ✅ |
| `無効なリソースID: 長すぎます N 文字` (id max 64) | HAPI (datatype rule) | ❌ |
| `SocketTimeoutException: Read timed out` | HAPI (tx 応答なし判定) | ✅ |

「なぜこの error が消えないか」を追う際に、まず **HAPI 側の rule** か **tx 側の判定** かを
切り分けると調査効率が上がる。前者なら data 側 fix、後者なら fhirserver 側の CodeSystem 版差や
cache 状態を疑う。

## HAPI Validator クラスタ設計

### JVM 並列数の設計

- HAPI Validator CLI (`validator_cli.jar`) は HTTP server モードで 1 プロセス = 1 JVM
  (`java -jar ... server <port>`)
- 単一 JVM は CPU 1 core しか使わない (validation 処理は主にシングルスレッド内で完結)
- **default は 6 JVM** — Apple Silicon M3 Max (14 core、Docker Desktop 18 GB) で最適 (rps は
  4 → 6 で増加、8 で coordination overhead が発生して微減)
- マシン性能とバックグラウンド負荷に応じて `scripts/hapi-cluster.sh` の `PORTS` と
  `parallel-validate.py --ports` を増減。実用上の上限は 8 JVM
- JVM 1 個あたり `-Xmx3g` (default 6 JVM で合計 18 GB、上限 8 JVM で 24 GB)
- 長時間 obs pass (~500k res 級) 実行後は per-JVM heap 蓄積で rps が劣化することがある。同一
  cluster で複数回検証を回す場合、間に `hapi-cluster.sh stop && start` を挟むと fresh JVM で
  復旧

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
