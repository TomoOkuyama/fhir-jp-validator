# fhirserver Docker ビルド手順 (Rosetta 2 最適化)

## 環境準備 (Apple Silicon Mac)

### 1. Rosetta 2 install (未実施なら)

```bash
softwareupdate --install-rosetta --agree-to-license
```

### 2. Docker Desktop の Rosetta emulation を有効化

1. Docker Desktop アイコン → Settings
2. General タブ → **Use Rosetta for x86/amd64 emulation on Apple Silicon** をチェック
3. Apply & Restart

### 3. 検証 (Rosetta で amd64 が動くか)

```bash
docker run --rm --platform linux/amd64 alpine uname -m
# 出力が "x86_64" なら OK
```

## fhirserver ビルド (自動)

```bash
./scripts/setup-fhirserver.sh
```

このスクリプトは:

1. `HealthIntersections/fhirserver` を `tx-server-build/fhirserver/` に clone
2. `patches/*.patch` を適用 (LOINC/SNOMED import CLI 追加、SNOMED DateSeparator fix)
3. `docker buildx build --platform linux/amd64` で `fhir-jp-validator/fhirserver:local` タグで image 作成

所要時間目安 (Rosetta 有効時):

| ステップ | 時間 |
|---|---:|
| Free Pascal + MySQL ODBC install | 2-3 分 |
| fhirserver source compile | 3-5 分 |
| Docker image finalize | 1 分 |
| **合計 (cache miss、初回)** | **5-8 分** |
| **2 回目以降 (cache hit)** | **< 1 分** |

Rosetta 無効時 (QEMU fallback) は 25-30 分かかります。

## Docker Compose での起動

```yaml
# docker-compose.yml (fhirserver 部分)
services:
  fhirserver:
    image: fhir-jp-validator/fhirserver:local
    container_name: fhir-jp-validator-fhirserver
    platform: linux/amd64
    ports:
      - "8181:80"
    volumes:
      - ./tx-server-build/terminology:/var/cache/txcache
      - ./tx-server-build/fhirserver-config/config.json:/config/zero-config.json:ro
    environment:
      - FHIRSERVER_LOG_LEVEL=info
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/r4/metadata"]
      interval: 30s
      timeout: 5s
      retries: 3
```

起動:

```bash
docker compose up -d fhirserver
docker logs -f fhir-jp-validator-fhirserver   # 起動ログを追う
curl http://localhost:8181/r4/metadata # CapabilityStatement が返ればOK
```

初回起動は terminology の load で ~40 秒、以降 restart は ~15 秒。

## トラブルシューティング

### `EConvertError: "20260601" is not a valid date`

SNOMED import 時に発生する場合、POSIX locale で `DateSeparator` が未初期化のバグ (upstream fhirserver v4.0.7 現在)。本 repo の `patches/ftx_sct_services.pas.patch` で修正済。パッチ適用忘れていないか `git diff` で確認。

### `Rosetta が有効なはずなのに遅い`

- Docker Desktop 再起動
- `docker info | grep -i rosetta` で Rosetta 認識状態を確認
- macOS system extension が承認済かも確認 (`softwareupdate` の再実行)

### `docker buildx build` が `no space left on device`

build cache が肥大化 (fhirserver Docker build で 27 GB 使う場合あり):

```bash
docker buildx prune -a -f   # 全 build cache 削除、image は残る
```

次回 build 時は cache miss で ~30 分再 build 必要になる点に注意。
