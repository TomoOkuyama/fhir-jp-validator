# 検証まとめ — 2026-07-20 v8.1 (parallel-validate.py A+E 適用の実測)

## 概要

v8 と同一データ (master cbfacc6e、431,783 res / p=1000 seed=300) を、`parallel-validate.py` の
新機能 (**A: sticky include** + **E: retry/timeout 増強**) で再検証。

- A: `--include-file fhir_r4/Organization.ndjson` で 17 Organization を全 Bundle に前置
- E: DEFAULT_RETRIES 2→4、DEFAULT_TIMEOUT 60→120

## 結果 (rest のみ実行、obs は Reference 非依存で回避)

| メトリック | v8 rest | v8.1 rest | 変化 |
|---|---:|---:|---|
| resources | 178,818 | 178,801 | -17 (sticky 除外) |
| elapsed | 6:54 | 7:12 | +5% |
| rps | 432 | 414 | -4% |
| error 件数 | 48 | **332** | **+284** (!) |
| unique errored | 27 (Composition) | 169 (Composition) | +142 |

## 分析: 42 件解消 + 163 件 latent 露出

### ✅ Chain #329 の 42 件は完全解消

`Slice 'Composition.section:referralFromSection/referralToSection.entry:*Organization': min=1 found=0`
→ v8.1 で **0 件**。sticky で `Organization/hospital-main-ecs` が Composition と同一 Bundle に入り、
`resolve()` が eCS profile を確認可能に。**Chain #329 の data 側実装は完璧と確定**。

### ⚠️ 163 Composition で新規 latent error 露出

```
選択肢 http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Organization_eCS|1.12.0
の中から profile Organization/hospital-main のマッチを見つけることができません
```

- 163 unique Composition × 2 slot = 326 error 発火
- 発火 slot: `Composition.author[1]` と `Composition.custodian`
- 参照先が `Organization/hospital-main` (base JP_Organization のみ) だが、eCS profile が要求される
- v8 では resolve() 失敗で **無音 pass**、sticky で resolve 成立し初めて validator が profile mismatch を検出

**これは data 側で潜在的に非準拠 (Chain #329 の完全化不足)**。generator は eCS Composition の author/custodian が eCS-flavored Organization を参照するよう修正が必要 (仮称 Chain #330)。

### timeout は変化なし (retries=4/timeout=120 でも 6 件残)

`java.net.SocketTimeoutException: Read timed out` — HAPI ↔ fhirserver 間の応答遅延。retry では
吸収しきれない極端に遅い code が数件存在する。根本解は fhirserver の Display() cache 化 patch
(未実装、~2-5x 期待、`entities/proj-fhir-jp-validator.md` 参照)。

## 教訓

- **sticky include は「validator 挙動を強化」ではなく「data の隠れた non-compliance を可視化」する tool**
- Cross-bundle resolve() 制約は「validator 側を優しくしていた」側面もあり、実際の compliance
  を厳格に検証するには generator 側の Reference target profile 完全化が必須
- 「エラー 0 は data 修正 + client 修正の両方が必要」— A+E だけでは真の 0 に到達できない

## client 側改修は commit 済み

`scripts/parallel-validate.py`:
- `--include-file` (repeatable) 追加
- `DEFAULT_RETRIES=4`, `DEFAULT_TIMEOUT=120` に変更
- Sticky 前置後の OperationOutcome から sticky resource 関連 issue を除外

CLI 変更は back-compat (default 動作は sticky なし)。

## 次のステップ

1. **generator 側 Chain #330**: eCS Composition (`author[1]`, `custodian`) の Organization 参照を
   `hospital-main-ecs` (eCS profile 保持) に切替
2. **timeout 削減**: fhirserver Display() cache 化 patch (中期)
3. **v9 (p=5000 seed=500) では sticky を使わない**: v8 baseline との公平比較のため、sticky なしで走らせて chain robustness を確認

## raw ファイル

- `raw/rest.meta.json` / `raw/rest.stdout.log` — commit 対象
- `raw/rest.ndjson` (~810MB) — gitignore
- `generator-metadata-snapshot.json` — commit 対象
- obs は Reference 依存が薄く sticky 効果薄いためスキップ
