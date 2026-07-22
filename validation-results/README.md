# validation-results/

当 validator で実施した参考検証の **結果と分析** を run 単位で格納します。合成データに対する
実測記録で、分析文 (README) と少量のメタは commit、大きい raw NDJSON は gitignore。

## ディレクトリ構成

```
validation-results/
├── README.md                             # このファイル
└── <YYYY-MM-DD>_<label>/                 # 1 run = 1 フォルダ
    ├── README.md                         # 実測数値・issue 分析・結論 (人間可読)
    └── raw/                              # parallel-validate.py の生出力
        ├── rest.meta.json                # run メタ (rps, 件数、port 別統計) — commit 対象
        ├── rest.stdout.log               # 実行時 stdout — commit 対象
        ├── rest.ndjson                   # OperationOutcome NDJSON — gitignore (数百 MB〜数 GB)
        ├── rest.failed.ndjson            # HTTP 失敗 Bundle (成功時は空) — gitignore
        ├── obs.meta.json / .stdout.log   # obs pass 同上
        ├── generator-metadata-snapshot.json  # data 生成側のメタ (commit)
        └── enumeration_manifest.json     # enumerate mode 時のみ、patient → scenario 逆引き
```

## 命名規約

- **フォルダ名**: `<YYYY-MM-DD>_<label>` — 日付 + データ規模やバリエーションを示す label
  - population run: `2026-07-22_full_v19_p1000` (patients=1000)
  - enumerate run: `2026-07-22_full_v18_enumerate`
- **raw ファイル**: `parallel-validate.py --output <name>.json` の name を残す
  - 分割検証なら `rest.*` / `obs.*` (現行標準)

## commit / gitignore ポリシー

| ファイル | commit | 理由 |
|---|:---:|---|
| `README.md` | ✅ | run 全体の構成説明 |
| `<run>/README.md` | ✅ | 実測数値と結論の記録 |
| `<run>/raw/*.meta.json` | ✅ | 小さい (~1KB)、再現性のため |
| `<run>/raw/*.stdout.log` | ✅ | 小さい、実行時挙動記録 |
| `<run>/raw/generator-metadata-snapshot.json` | ✅ | data 生成元の同定 |
| `<run>/raw/enumeration_manifest.json` | ✅ | enumerate 時の patient 分類逆引き |
| `<run>/raw/*.ndjson` | ❌ | 数百 MB〜数 GB、gitignore |
| `<run>/raw/*.failed.ndjson` | ❌ | 同上 |

`.gitignore` は repo ルートで `validation-results/**/raw/*.ndjson` を除外しています。
**ndjson 本体は各自ローカルで保持** (再検証で再生成可能)。長期間残す必要はないため、
`find validation-results -name "*.ndjson" -delete` で任意タイミングで削除して構いません。

## 新しい run を追加する手順

```bash
# 1. 検証実行 (docs/real-world-validation.md 参照、分割検証パターン)
RUN=validation-results/$(date +%F)_<label>
mkdir -p "$RUN/raw"

# rest pass (tx=8181、sticky Organization 前置)
HAPI_TX="http://localhost:8181/r4" HAPI_EXTRA_ARGS="-best-practice ignore -check-display Ignore" \
  ./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py <input_dir> --output "$RUN/raw/rest.ndjson" \
  --chunk 30 --parallel 24 --include-file <input_dir>/Organization.ndjson \
  > "$RUN/raw/rest.stdout.log" 2>&1

# obs pass (tx=n/a、fresh cluster 推奨)
./scripts/hapi-cluster.sh stop
HAPI_TX="n/a" ./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py <input_dir>/Observation.ndjson --output "$RUN/raw/obs.ndjson" \
  --chunk 30 --parallel 24 > "$RUN/raw/obs.stdout.log" 2>&1
./scripts/hapi-cluster.sh stop

# 2. 分析 README を書く (直近の run を template として参照可)
$EDITOR "$RUN/README.md"

# 3. commit (raw の ndjson は自動除外、stdout.log/meta.json/README.md のみ track)
git add "$RUN"
git commit -m "Add validation run: $(basename $RUN)"
```

## 参考

- 出力形式の解釈: [../docs/output-guide.md](../docs/output-guide.md)
- 実データ検証の推奨手順 (分割戦略、sticky Reference): [../docs/real-world-validation.md](../docs/real-world-validation.md)
- ベンチマーク結果: [../docs/benchmarks.md](../docs/benchmarks.md)
- HAPI validator on-disk txCache 汚染 (既知の upstream bug): [../docs/hapi-txcache-poisoning.md](../docs/hapi-txcache-poisoning.md)
