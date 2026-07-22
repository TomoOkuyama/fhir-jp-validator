# ベンチマーク結果

## 検証環境

- Host: Apple MacBook Pro M3 Max 14-core、Docker Desktop 4.36、Rosetta 2 有効
- Memory: Docker Desktop に 18 GB 割当、HAPI cluster は 6 JVM × 3g heap = 18 GB
- Data: 合成 FHIR data (26 リソース種、3.43M resources、4.7 GB NDJSON)
- Sample: `awk 'NR%10==1'` で 1/10 stride 抽出、343,478 res / 486 MB
- Validator: HAPI FHIR Validator 6.9.12
- fhirserver: HL7 4.0.8-SNAPSHOT (Pascal)、LOINC 2.82 + SNOMED Int 20260601 全 load
- JP Core: 1.2.0 / JP-CLINS: 1.12.0 / jpfhir-terminology: 2.2606.0

## 主要結果

1/10 sample (343,478 res) を、terminology load 構成を段階的に増やして検証:

| 構成 (load 内容) | success | 総 issue | 平均 rps | 時間 |
|---|:---:|---:|---:|---:|
| **A: 基本セット** — HL7 + JP Core + LOINC + SNOMED | 95.7% | 3,882,468 | 212 | 25.8 分 |
| **B: A + JP-CLINS 1.12.0** | 100.0% | 4,549,232 | 174 | 32.9 分 |
| **C: B + jpfhir-terminology 2.2606.0 (cache cold)** — 初回起動、IG on-demand DL 発生 | 98.7% | 3,784,619 | 165 | 34.2 分 |
| **C-warm: 同 (cache warm)** — 2 回目以降、IG cache 済で on-demand DL なし | **100.0%** | **3,952,669** | **205** | **28.0 分** |

**推奨構成: C-warm** — 28 分、205 rps、100% success。以降のセクションでは各段階を「A / B / C / C-warm」と呼びます。

### 主な効果

#### JP-CLINS 追加の効果 (A → B)

- eCS プロファイル (JP_Observation_LabResult_eCS 等) の canonical resolution が成功、`Meta.profile` 宣言と実データの乖離を露見
- +666k issue (Error +345k、Warning +141k、Info +181k)
- 内訳: identifier/lastUpdated/category slice 等の必須要素欠如

#### jpfhir-terminology 追加の効果 (B → C-warm)

- **UCUM CodeSystem の code 検証が可能に** — `http://unitsofmeasure.org` に code 定義提供、`検証できません` info **-593k**
- JP Core Common ValueSet 3 種解消 (`JP_MedicationCode_VS`、`JP_SimpleObservationCategory_VS`、`JP_ObservationLabResultCode_VS`) — warn **-135k**
- JP_ConditionSeverity_VS 解消 — warn -11k
- 一部 OID CodeSystem 認識 (`urn:oid:1.2.392.200119.4.1005`) — warn -5k
- 合計 **-596k issues** (B の 4.55M → C-warm の 3.95M)

## Rosetta 2 の効果

| 処理 | QEMU (Rosetta 無効) | Rosetta 有効 | 高速化 |
|---|---:|---:|---:|
| fhirserver Docker build | 25 分 | **5-8 分** | 3-5x |
| SNOMED CT International import | 4-8 時間 | **9 分 50 秒** | 25-50x |
| LOINC import | ~15 分 | ~2-3 分 | 5-7x |

**Rosetta 2 の有効化は必須**。無効時は SNOMED import 1 回で 1 日仕事になります。

## Cache warm 化の効果

構成 C (cache cold) と C-warm は load 内容が同じにも関わらず **34 分 / 165 rps → 28 分 / 205 rps** に高速化。

**原因**: `hl7.terminology.r4#7.0.0` が cache cold の初回実行時に on-demand DL され、port 3006 (当時 3008) で 1 分 41 秒フリーズ → circuit breaker 発動、4,500 res が timeout。

**対処**: `~/.fhir/packages/` に必要 IG (us.nlm.vsac、us.cdc.phinvads 等) が cache 済であれば以降 restart で on-demand DL 不要、全 JVM が cache から即 load。

**運用推奨**: cluster start 前に一度 fhirserver + cluster の初回起動を試し、必要 IG を prime しておく。

## スケーリング考察

### JVM 数

- **default 6 JVM**、実用上の上限 8 JVM。12 以上は JVM 間の CPU 争奪で総 rps 低下
- 各 JVM は `-Xmx3g`、6 JVM で 18 GB、8 JVM で 24 GB RAM 消費。マシン仕様と他プロセス負荷に
  応じて `PORTS` を調整
- 長時間 obs pass (~500k res 級) 実行後は per-JVM heap 蓄積で rps が劣化することがある。
  複数回検証の間で `hapi-cluster.sh stop && start` を挟むと fresh JVM で復旧

### `parallel` パラメータ (client 側 in-flight)

- `parallel=24` (chunk=30) が総合バランス最良、profile 依存度の高いデータでも安定
- `parallel=32` は fhirserver への同時 tx リクエスト増、cache warm 時なら高速化するが tx-heavy
  では circuit breaker リスク
- `parallel=64` は circuit breaker 発動リスクが高い、cache cold 時は特に注意

### fhirserver bottleneck

- Clinosim data のように code が全て有効な場合、fhirserver 側の terminology validation が CPU bound (実測 fhirserver CPU 200% 到達)
- 一方 code が未登録 CodeSystem 中心なら validator が terminology check を即 skip、rps は 2-3 倍出る
- **rps は data の terminology 充実度に依存**

## 参考: 全件検証 (1/1) の推定

1/10 sample が 28 分の場合、1/1 = 3.43M res は理論上 4.7 時間。以下の条件で完了予測:

- ディスク I/O は問題無し (M3 Max SSD 上、48 GB データ)
- メモリは JVM 18 GB (6 JVM) + fhirserver 4 GB + client 数 GB で計 ~26 GB 消費
- fhirserver bottleneck の影響で 1/1 スケールでは rps が半減する可能性 (実行時間 8-10 時間)

## 実データ検証結果と分割戦略

日本の EHR 由来 FHIR data (Observation 主体) を通した際の実測特性・rps・issue 分布・推奨構成は [docs/real-world-validation.md](real-world-validation.md) にまとめています。要点:

- Observation の LOINC 日本語 display 検証が per-code ~700ms かかり、単一 pass では完走困難
- `Observation` を分離し `HAPI_TX=n/a` で構造/slice のみ、残り 25 種を tx 有効で並行検証すると 179k res が 11 分で完走
- 実データの ~65% リソースに 1+ error (主因: eCS プロファイル必須 slice/要素の欠落)

## クラスタサイジング

Default 構成 (6 JVM × 1 fhirserver) の合理性を、JVM 数 × fhirserver 数の 2 軸で検証。
測定条件: 1/20 sample (176k res 中の `--limit 30000`)、chunk=50、cache warm、複数 run。

### 重要な測定上の注意 — JIT warmup が支配的

HAPI Validator (Java) の JIT compile が rps に強く影響します。JVM 再起動直後は、同一構成でも run 回数によって以下のように変動します (6 JVM × parallel 24、single fhirserver、30k res /run):

| run | rps | 備考 |
|---:|---:|---|
| 1 | 217 | JIT cold |
| 2 | 305 | 温まり中 |
| 3 | 378 | まだ伸びる |
| 4 | **511** | ほぼ steady state |

**単発測定は 2x 以上ずれるため、比較用の測定は必ず同条件で 3-4 回連続 run して steady state を取ってください**。

### JVM 数の最適値 (fhirserver は single)

各 JVM 数を **cache warm な状態**で測定:

| JVM 数 | parallel | rps | 相対 |
|---:|---:|---:|---:|
| 4 | 16 | 462 | 88% |
| **6** | **24** | **527** | **100%** |
| 8 | 32 | 481 | 91% |

- **6 JVM が最適** (M3 Max 14 core、Docker Desktop 18GB 割当)。default 設定と一致
- 8 JVM は JVM 間の coordination overhead で悪化 (RAM 24GB でも swap は発生せず)
- 4 JVM は CPU 使い切れずに rps 低下

### fhirserver 複数化 (LB) は逆効果

nginx (`least_conn`, keepalive) を LB として 2 fhirserver (それぞれ別の terminology volume に copy) 構成を測定:

| 構成 | run1 rps | run2 rps | run3 rps |
|---|---:|---:|---:|
| 6 JVM × 1 fs (直接) | 217 | 305 | 378 → 511 |
| 6 JVM × 2 fs (nginx LB) | 163 | 268 | 250 |

**LB steady state 250 rps vs single fs 500 rps — 半減**。原因分析:

- **fhirserver は bottleneck ではなかった** — LB run 2/3 中、fhirserver-1/2 の CPU は共に 0-1% 程度で idle。HAPI 側の txCache (disk) hit が支配的で、fhirserver への tx call が少ない
- **LB が加える proxy 遅延と cache 分散が逆効果** — 少ない tx call に対して nginx 経由 (1 hop 増)、さらに fhirserver 2 台に in-memory cache が分散されて hit ratio が下がる
- **HAPI txCache は URL 込みで keyed 可能性** — `-tx` URL を変えると (8181→8180) 既存 disk cache が事実上 fresh になる (要検証だが、LB run 1 の 163 rps はこれで説明可能)

### txCache warmup の実効性

「事前 warmup で JIT を温めておけば本測定が加速するか」を検証:

| 事前 warmup (res) | 本測定 30k の rps | baseline 比 |
|---:|---:|---:|
| 0 | 217 | - |
| 5,000 | 230 | +6% |
| 15,000 | 254 | +17% |

**効果は限定的** (最大 +17%)。理由: 本測定 30k 自体で JIT が十分進むため、事前 warmup 分だけ後から余分に温める効果しかない。また `.hapi-cache/tx-cache/` の disk cache は 2.5MB 前後で頭打ち (`all-systems.cache` `loinc.cache` `snomed.cache` 等の集約 index) で、run を重ねてもほぼ増えない → disk cache の warmup 余地はほぼゼロ。

一方、cluster を再起動せず前回 run の JIT 状態を保持すると、複数回の連続 run で **217 → 305 → 378 → 511 rps** に成長 (2.4x)。

### 推奨

- **default (6 JVM × 1 fhirserver) で十分**。LB は今回の設計 (nginx + separate volume) では改善なし
- **1 セッション内で複数回検証する場合、cluster を stop せず再利用する** (JIT 状態が保持され 2 回目以降が高速)
- **大規模検証 (100k+ res) では pre-warmup 不要** — JIT コストは全体に amortize され、無視できる範囲になる
- 短時間で多数の小規模ジョブを回す CI 用途では `--limit 15000` 程度の事前 warmup を検討 (+17% 程度期待)
- 1 台の fhirserver が真に CPU bound (`docker stats` で持続 200%+) になってから初めて LB を検討する余地あり
