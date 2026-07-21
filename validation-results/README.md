# validation-results/

このディレクトリには、当 validator で実施した検証の**結果 (raw output + まとめ + 生成者向けフィードバック)** を run 単位で格納します。

## ディレクトリ構成

```
validation-results/
├── README.md                             # このファイル
└── <YYYY-MM-DD>_<label>/                 # 1 run = 1 フォルダ
    ├── raw/                              # parallel-validate.py の生出力
    │   ├── *_result.meta.json            # run メタ (rps, 件数、port 別統計) — commit 対象
    │   ├── *_result.ndjson               # OperationOutcome NDJSON — gitignore (~数百 MB)
    │   └── *_result.failed.ndjson        # HTTP 失敗 Bundle (成功時は空) — gitignore
    ├── summary.md                        # 実測数値・issue 分布・所要時間のまとめ (人間可読)
    └── generator-feedback.md             # データ生成者向けフィードバック (現状→あるべき姿)
```

## 命名規約

- **フォルダ名**: `<YYYY-MM-DD>_<label>` — 日付 + データ規模やバリエーションを示す label
  - 例: `2026-07-16_1of20` (2026-07-16 に 1/20 sample で検証)
  - 例: `2026-08-01_full` (フル検証)
- **ファイル名**: `parallel-validate.py --output <name>.json` の name を残す
  - 例: 分割検証なら `rest_result.*` `obs_result.*`

## commit / gitignore ポリシー

| ファイル | commit | 理由 |
|---|:---:|---|
| `README.md` | ✅ | 構成説明 |
| `<run>/summary.md` | ✅ | 実測数値・結論の記録 (人間可読) |
| `<run>/generator-feedback.md` | ✅ | データ生成側への提案書 |
| `<run>/raw/*_result.meta.json` | ✅ | 小さい (~1KB)、再現性のため |
| `<run>/raw/*_result.ndjson` | ❌ | 数百 MB〜数 GB、gitignore |
| `<run>/raw/*_result.failed.ndjson` | ❌ | 同上 |

`.gitignore` は repo ルートで `validation-results/**/raw/*.ndjson` を除外しています。**ndjson 本体は各自ローカルで保持** (再検証するか、必要なら別途アーカイブ・共有)。

## 新しい run を追加する手順

```bash
# 1. 検証実行 (docs/real-world-validation.md 参照、分割検証パターン)
./scripts/parallel-validate.py <input> --output /tmp/rest_result.json ...
./scripts/parallel-validate.py <input_obs> --output /tmp/obs_result.json ...

# 2. run フォルダを作成
RUN=validation-results/$(date +%F)_<label>
mkdir -p "$RUN/raw"

# 3. raw を配置
cp /tmp/rest_result.* /tmp/obs_result.* "$RUN/raw/"

# 4. summary と feedback を書く (テンプレートは 2026-07-16_1of20/ を参照)
$EDITOR "$RUN/summary.md" "$RUN/generator-feedback.md"

# 5. commit (raw の ndjson は自動除外)
git add "$RUN"
git commit -m "Add validation run: $(basename $RUN)"
```

## 参考

- 出力形式の解釈: [docs/output-guide.md](../docs/output-guide.md)
- 実データ検証の推奨手順 (分割戦略等): [docs/real-world-validation.md](../docs/real-world-validation.md)
- ベンチマーク結果: [docs/benchmarks.md](../docs/benchmarks.md)
- HAPI validator on-disk txCache 汚染の詳細: [docs/hapi-txcache-poisoning.md](../docs/hapi-txcache-poisoning.md)
  (v12 / v14 の before/after 実測を英語で canonical 化)
