# 生成者向けフィードバック — 2026-07-20 v10 (p=5000 seed=500、session 61+ 5 PR merged)

対象: clinosim 側 (workspace:1)。**generator 由来の error 完全 0 到達** を実測確認、compliance フェーズ完了報告。

## 🏆 総評

- **generator 由来 error: 0** (baseline 226 の全てが eReferral cross-bundle infra または timeout、data 由来 0)
- **fail 率 v9 0.0129% → v10 baseline 0.00771% → v10 sticky ON 0.00125%** (**史上最良**)
- **5 PR 全て期待通り完全解決** (84 data error + 163 Chain #330 latent → 全て 0)
- **JP-CLINS 実運用相当 (document Bundle) での完全準拠を実測確認**

## PR 別実測結果

| PR | 対象 | 期待 | 実測 | 判定 |
|---:|---|---:|---:|:---:|
| #331 (Chain #330) | eCS Composition author + custodian → hospital-main-ecs | -163 latent | **-163 完全** (v8.1 で 326 errors → v10 sticky で 0) | ✅✅✅ |
| #333 | admit-source `'hosp'` → `'other'` | -2 | **-2** | ✅ |
| #335 | ICD-10 `R53.1` → `R53` WHO fold | -78 (MR 75 + Enc 2 + Cond 1) | **-78** | ✅ |
| #338 | Observation walker mb-org HAI 3-identifier idempotent-prepend | -1 | **-1** | ✅ |
| #339 | LOS=1 でも progress_note 1 件 emit で `hospitalCourseSection.entry` min=1 | -3 | **-3** | ✅ |

**合計 84 data error + 163 Chain #330 latent = 247 → 全て 0**、100% 効果。

## 種別別 fail 率変化 (v10 vs v9)

| 種別 | v9 fail | v10 baseline fail | 変化 |
|---|---:|---:|---:|
| **MedicationAdministration** | 0.034% | **0%** | -0.034pp ✅ (Ch#335) |
| **Encounter** | 0.011% | **0%** | -0.011pp ✅ (Ch#333+#335) |
| **Condition** | 0.003% | **0%** | -0.003pp ✅ (Ch#335) |
| **Observation** | 0.0001% | **0%** | -0.0001pp ✅ (Ch#338) |
| Composition | 0.599% | 0.585% | ↔ (data 側 -3 消滅、残 = eReferral infra 206 + timeout 20) |

**26 種のうち error 発生は Composition のみ**、内訳も全て非 data 由来。

## sticky ON pass の意義 (Chain #330 検証)

`parallel-validate.py --include-file fhir_r4/Organization.ndjson` で全 Bundle に Organization 17 件を前置:
- Composition.author[1] / custodian の Reference target resolve() 成立
- eCS profile 保持を validator が確認
- **Chain #330 の PR #331 fix が正しく機能することを実測**

v8.1 (Chain #330 未適用) では sticky ON で 163×2 = 326 errors 発生していたが、v10 では **0** に到達。

これは semantically **document Bundle validation 相当**であり、JP-CLINS 実運用 (Composition + 全参照を document 型 Bundle で送受) に相当する厳格検証。

## 残 20 error (v10 sticky ON) の性質

全て `java.net.SocketTimeoutException: Read timed out`:
- HAPI validator ↔ fhirserver の tx call 応答遅延
- `retries=4 timeout=120s` でも吸収されない極端に遅い Composition validation
- 原因: LOINC 日本語 display の tx 検証で `Display()` 関数が毎リクエスト SQL クエリ発行 (proj-fhir-jp-validator vault entity 参照)

**generator 側は無関係**。validator infra 側で以下いずれか実装で消滅可能:
1. fhirserver `Display()` cache 化 patch (~2-5x 期待)
2. HAPI validator patch で `-check-display Ignore` を tx call payload まで伝播
3. client `--chunk 30 --retries 6` チューニング (workaround)

## generator compliance フェーズ完了報告

**Session 60/61/61+ 累計 16 PR merged** で以下達成:
- data-side profile compliance: **100%** (0 error)
- Reference target profile compliance: **100%** (Chain #330 で完全)
- 5x scale + 別 seed regression 耐性: **確認済**
- JP-CLINS 実運用相当 semantics での準拠: **実測確認**

**generator 側の compliance 追加作業は不要** (regression monitoring と long-tail rare pattern の pruning のみ)。

## 今後 (workspace:1 側で optional)

### モニタリング項目

- 今後の regen で 16 chain (#306-#339) が 0 件維持されるか
- 新規 rare pattern が seed 変更で露出したら即対応 (Chain #285/#335 パターン)

### 拡張余地 (機会があれば)

- **Bundle type=document 直接生成**: 現状は resource-level NDJSON を client が collection Bundle 化。実運用に一致する document Bundle を Composition ごとに生成する path
- **業務ロジック検証**: 診療報酬点数整合、レセプト整合、時系列整合 (validator では未対応)
- **JP-CLINS eRP/e処方箋等の追加 profile カバー**: 現在 eDS/eReferral 主体
- **US golden data の準拠向上** (現状 JP に絞って対応、US は未検証)

## validator repo 側の TODO (この repo で対応)

1. **fhirserver Display() cache 化 patch** — Pascal patch、~2-5x 期待、20 timeout → 0
2. **`--include-file` を docs/real-world-validation.md に追記** — sticky ON の使い方、Chain #330 の背景
3. **Bundle type=document 対応検証** — client が document Bundle を validator に投げる mode

## Session 60→61+ の総括 (v10 で確定)

- **fail 率 v1 65% → v10 sticky 0.00125% = -99.998%**
- **16 PR chain は全て scale + seed + document semantics で robustness 実証**
- **generator compliance work は事実上完了**
- **次フェーズ**: validator infra 最適化 + Bundle type/業務ロジック検証拡張

素晴らしい 8 サイクル (v1→v10)、お疲れさまでした。
