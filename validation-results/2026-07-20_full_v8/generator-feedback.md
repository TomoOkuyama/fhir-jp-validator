# 生成者向けフィードバック — 2026-07-20 v8 (session 60→61 continuation 11 chain merge 後)

対象: clinosim 側 (workspace:1)。次サイクル (v9) で対応すべき事項を優先度順に整理。

## 🏆 総評

- **fail 率 v6.1 0.190% → v8 0.0063%** (-97%、実質完全準拠水準)
- **error 総数 v6.1 1,247 → v8 48** (-96%)
- **generator 由来の error は全て解消**、残 48 error は 42 = validator infra artifact (cross-bundle resolve()) + 6 = HTTP timeout
- **Session 61 の 6 chain は全て期待通り機能**、Chain #329 も data は完璧 (Composition が Organization/hospital-main-ecs を正しく参照、Organization は eCS profile を宣言)

## Chain 別実測

### 完全解決 (5 chain)

| PR | 対象 | 期待 | 実測 |
|---:|---|---:|---|
| #320 | ImagingStudy.procedureCode 省略 | -589 | **-589 (完全消滅、rate 77.3% → 0%)** ✅✅✅ |
| #322 | Observation code.text + valueCC display | -352 | **-352 (完全消滅)** ✅✅✅ |
| #324 | valueQuantity 空文字列 omit | -44 | **-44** ✅✅ |
| #326 | LAB_UNITS PT/APTT 追加 | -22 | **-22** ✅✅ |
| #328 | Location OR text-only | -2 | **-2** ✅ |

### 【重要】 Chain #329 — data は完璧、残 42 件は validator infra 由来

Composition → `Organization/hospital-main-ecs` 参照、Organization は eCS profile 保持を確認済み。

**42 件の error が残るのは client 側 (parallel-validate.py) の cross-bundle 制約**:
- スライス discriminator は `resolve().meta.profile`
- parallel-validate.py は 50 res/Bundle でチャンク化 → Composition と Organization が別 Bundle
- HAPI validator の `resolve()` は同一 Bundle 内探索 → null 返却 → slice 不一致

**この件は generator 側で追加対処不要**。validator repo 側で `parallel-validate.py --include-file fhir_r4/Organization.ndjson` 相当を実装予定 (次 cycle でこちら側 fix)。

もし clinosim 側でも保険的に対策するなら以下いずれか (非必須):
- 選択肢1: 何もしない (推奨、data は既に正しい)
- 選択肢2: Composition emit 時に referenced Organization を `contained` 化 (contained は避けるべき pattern なので非推奨)

## 【問題無し】全種別 fail 率

| 種別 | v8 fail | v6.1 fail | 変化 |
|---|---:|---:|---:|
| Observation | **0%** | 0.079% | -0.079pp ✅✅✅ |
| ImagingStudy | **0%** | 77.30% | -77.30pp ✅✅✅ |
| Location | **0%** | 2.82% | -2.82pp ✅ |
| MedicationAdministration | 0% | 0% | ↔ ✅ (v6.1 継続) |
| MedicationRequest | 0% | 0% | ↔ ✅ (v6.1 継続) |
| Composition | 0.60% | 0.60% | ↔ (残 27 は infra artifact、data 正しい) |
| その他 21 種 | 0% | 0% | ↔ ✅ |

**Session 60→61 累計改善**: v5 (0.692%) → v6 regression (3.554%) → v6.1 (0.190%) → **v8 (0.0063%)**、v5 比 **-99%**。

## Session 61 教訓の実測確認

1. **required binding は text-only で回避できない**: Ch#315 の text-only approach は 589 件残存、Ch#320 で `procedureCode` 要素そのものを省略した瞬間に完全解決。教訓通り。
2. **English-only CS への JP display emit は無意味**: builder 側で English 直接 emit した Ch (LAB_UNITS/Location OR 系) が全て 0 件到達。walker との pipeline invariant が働いた。
3. **sibling sweep で cross-file consistency 確認**: Ch#326 (LAB_UNITS × reference_range_lab.yaml) の追加漏れが sweep で発見され PT/APTT 追加、これも 0 件到達。

## 次サイクル (v9) の generator 側優先度

**generator 由来の error は 0**。追加 chain は基本不要。ただし以下は monitoring 対象:

### モニタリング項目 (regression 防止)

- Session 60 の 5 chain (#306/#308/#310/#312/#320) が今後も 0 件維持されるか
- Session 61 の 5 完全解決 chain (#320/#322/#324/#326/#328) が今後も 0 件維持されるか
- Framework Phase 1/3/3-b (YJ/LOINC drift 検知) の動作継続

### 探索候補 (機会があれば)

- **Bundle validation** の対応: 現状 client は `collection` 型で valdiator を使うが、実運用は `document` (JP-CLINS Composition-driven Bundle) や `transaction`。document 型準拠検証は今後の課題
- **業務ロジック検証**: 診療報酬点数整合、レセプト整合、時系列整合 (validator では未対応、生成側で自己検証も可)
- **より多くの JP-CLINS profile カバー**: 現在 eDS/eReferral 主体、eRP/e処方箋等の追加

## validator 側 (この repo で対処予定) の TODO

1. `parallel-validate.py --include-file` 実装 (sticky reference resources) — eReferral 42 件、その他 cross-bundle references 解消
2. timeout 削減: `--retries 4 --chunk 30` チューニング検証
3. `docs/real-world-validation.md` に「cross-bundle Reference 検証の限界」節を追加

**これらで validator 側から fail 率 0.0063% → ~0% に到達可能**。

## Session 60→61 の総括

- **8 サイクル (v1→v8) で fail 率 65% → 0.006% (-99.99%)**
- **judgement recovery pattern が確立**: v6 regression から v6.1 に完全回復、その後 v6.1 → v8 で残余ほぼ全消
- **generator design invariants の確認**:
  - fixed-display CS の fallback は text で情報伝達
  - required binding VS 非該当時は要素省略
  - Reference 越しの slice 検証は Bundle 制約に注意 (v8 で判明)
- **validator repo との共同運用が定着**: cmux 経由の feedback ループで 1 cycle 25-35 分、11 chain を 2 セッションで完了

**generator コンプライアンスは事実上完了フェーズ**。今後は monitoring と validator 側の残作業。
