# ベンチマーク結果

## 検証環境

- Host: Apple MacBook Pro M3 Max 14-core、Docker Desktop 4.36、Rosetta 2 有効
- Memory: Docker Desktop に 18 GB 割当、JVM heap 3g × 8 = 24 GB 前提 (当時、8 JVM で測定。現行 default は 6 JVM = 18 GB)
- Data: 患者 FHIR data (26 リソース種、3.43M resources、4.7 GB NDJSON)
- Sample: `awk 'NR%10==1'` で 1/10 stride 抽出、343,478 res / 486 MB
- Validator: HAPI FHIR Validator 6.9.11
- fhirserver: HL7 4.0.8-SNAPSHOT (Pascal)、LOINC 2.82 + SNOMED Int 20260601 全 load
- JP Core: 1.2.0 Differential / JP-CLINS: 1.12.0 / jpfhir-terminology: 2.2606.0

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

- M3 Max 14 core での上限は 8 JVM (12 JVM 試行では JVM 間の CPU 争奪で総 rps 低下)。本 repo の default は余裕を持たせた **6 JVM**
- 各 JVM は -Xmx3g、6 JVM で 18 GB、8 JVM で 24 GB RAM 消費。マシン仕様と他プロセスの負荷に応じて `PORTS` を調整

### `parallel` パラメータ (client 側 in-flight)

- `parallel=32` (chunk=50) が総合バランス最良 (構成 C-warm)
- `parallel=64` は circuit breaker 発動リスク増 (構成 C の timeout パターン)
- `parallel=24` に下げると、profile 依存度が高く issue が大量に出るデータでも安定 (fhirserver への同時 tx リクエスト削減)

### fhirserver bottleneck

- Clinosim data のように code が全て有効な場合、fhirserver 側の terminology validation が CPU bound (実測 fhirserver CPU 200% 到達)
- 一方 code が未登録 CodeSystem 中心なら validator が terminology check を即 skip、rps は 2-3 倍出る
- **rps は data の terminology 充実度に依存**

## 参考: 全件検証 (1/1) の推定

1/10 sample が 28 分なら 1/1 = 3.43M res は理論上 4.7 時間。実測未検証だが、以下の条件で完了予測:

- ディスク I/O は問題無し (M3 Max SSD 上、48 GB データ)
- メモリは JVM 18 GB (default 6 JVM) + fhirserver 4 GB + client 数 GB で 26 GB 消費予測 (8 JVM なら 32 GB)
- fhirserver bottleneck が原因で 1/1 スケール時は rps が半減する可能性あり (実行時間 8-10 時間)
