# fhirserver セットアップ入門 (初学者向け)

このドキュメントは以下の方を対象に、`fhirserver` を自分の Mac に立ち上げるまでの全手順を、
コマンド 1 行ずつ何をしているか説明しながらガイドします。

- FHIR や医療用語集 (SNOMED CT、LOINC 等) を初めて扱う方
- ターミナル / Docker / `git` / `curl` などの Linux 系コマンドに不慣れな方

すでに実務経験がある方は、より簡潔な [`terminology-setup.md`](terminology-setup.md) /
[`build-rosetta.md`](build-rosetta.md) / [`licensing.md`](licensing.md) を直接お使いください。

---

## 目次

- [0. このガイドで何を作るか](#0-このガイドで何を作るか)
- [1. 前提知識: 用語のかんたん説明](#1-前提知識-用語のかんたん説明)
- [2. 環境を用意する](#2-環境を用意する)
- [3. リポジトリを取得する](#3-リポジトリを取得する)
- [4. fhirserver の Docker イメージをビルドする](#4-fhirserver-の-docker-イメージをビルドする)
- [5. 無料の日本 IG を取得する (JP Core / JP-CLINS / jpfhir-terminology)](#5-無料の日本-ig-を取得する-jp-core--jp-clins--jpfhir-terminology)
- [6. LOINC を取得する (無料、要ユーザ登録)](#6-loinc-を取得する-無料要ユーザ登録)
- [7. SNOMED CT を取得する (無料だが UMLS ライセンス申請要、注意事項多い)](#7-snomed-ct-を取得する-無料だが-umls-ライセンス申請要注意事項多い)
- [8. 用語集を fhirserver 用の cache に変換する](#8-用語集を-fhirserver-用の-cache-に変換する)
- [9. fhirserver を起動して動作確認する](#9-fhirserver-を起動して動作確認する)
- [10. うまくいかないとき (よくあるトラブル)](#10-うまくいかないとき-よくあるトラブル)
- [11. ライセンス上の重要な注意事項まとめ](#11-ライセンス上の重要な注意事項まとめ)
- [12. よくある質問 (FAQ)](#12-よくある質問-faq)

---

## 0. このガイドで何を作るか

**最終ゴール**: 自分の Mac の中に「用語集を全部載せた FHIR terminology server (fhirserver)」を
Docker で起動し、`curl` (URL を叩くコマンド) で用語を問い合わせできる状態にする。

これができると:

- HL7 の FHIR 検証ツール (HAPI Validator) に組み合わせて、日本の医療データが
  JP Core / JP-CLINS 準拠かどうかチェックできる
- LOINC や SNOMED CT のコードが実在するか、日本語 display が正しいかを確認できる

**所要時間の目安** (初回、ライセンス申請の待ち時間を除く):

| フェーズ | 時間 |
|---|---:|
| 環境準備 (Docker、Rosetta) | 30 分 |
| 無料 IG の DL | 5 分 |
| LOINC の DL + 変換 | 30 分 (アカウント作成含む) |
| SNOMED の DL + 変換 | UMLS 承認まで **3-5 営業日**、承認後の作業は 30 分 |
| fhirserver の Docker build | 5-8 分 |
| **合計 (SNOMED 抜き最初の作業だけ)** | **約 2 時間** |
| **合計 (SNOMED 込み、UMLS 承認待ち除く)** | **約 3 時間** |

**必要なディスク空き容量**: 約 40 GB (fhirserver image + terminology cache + Docker build cache)

**必要なメモリ**: 8 GB 以上を推奨 (Docker Desktop に 4-8 GB 割り当てる)

---

## 1. 前提知識: 用語のかんたん説明

コマンドを実行する前に、何を扱っているかを一度整理します。分からない用語が出てきたらここに
戻ってきてください。

### FHIR (ふぁいあ)

Fast Healthcare Interoperability Resources — 医療データを JSON でやり取りするための国際規格。
「患者」「診察」「検査結果」等が Resource として定義されています。R4 と呼ばれる 4 番目のメジャー
バージョンが日本でも標準です。

### IG (アイジー、Implementation Guide)

FHIR の仕様は世界共通ですが、国ごと・目的ごとに「必須項目」「使うべき用語コード」等の追加ルール
があります。それらをパッケージ化したのが Implementation Guide。本ガイドでは:

- **JP Core**: 日本の基本 FHIR プロファイル (患者、診察、検査結果等の共通ルール)
- **JP-CLINS**: 電子カルテ情報共有サービスの実装ガイド (退院時サマリ、診療情報提供書等)
- **jpfhir-terminology**: 日本独自の用語コード集 (医薬品コード、日本の CodeSystem 等)

の 3 つを使います。すべて **CC0 (パブリックドメイン相当)** で無償配布されています。

### 用語集 (Terminology / CodeSystem / ValueSet)

「肝機能検査」を表すコードとして LOINC は `1751-7`、SNOMED CT は `250731003` を割り当てる、
のように「コードの意味を辞書として持つ体系」を CodeSystem、「特定のフィールドに入れて良い
コード集合の指定」を ValueSet と呼びます。本ガイドで揃える主要な CodeSystem:

- **LOINC**: 検査項目 (Sodium in Serum 等) の国際コード。無料、要ユーザ登録
- **SNOMED CT**: 病名・手技等の国際コード。**UMLS ライセンス申請が必要**、個人利用制約あり
- **UCUM**: 単位コード (mg/dL 等)。jpfhir-terminology に同梱

### terminology server (tx server)

FHIR の Validator は「このコードは LOINC の中に本当にある?」等を毎回問い合わせる先が必要で、
それが terminology server (略称: tx server)。本 repo では `HL7 fhirserver` (Pascal で書かれた
軽量な公式実装) をローカルで動かします。

### Validator と tx server の役割分担

本 repo の検証構成は 2 つのプロセスに分かれています:

- **HAPI Validator (JVM)** = 検証の「司令塔」。「このリソースは JP Core Composition のルールを
  守れているか」「必須項目 (min=1) は入っているか」「slice はどれに属するか」など、
  **構造やルール** のチェックを全部担当
- **fhirserver (tx server)** = 「用語辞書」。「LOINC 1751-7 は本当に存在する?」
  「日本語 display 名は正しい?」「ValueSet に含まれる?」など、**コードの実在確認と辞書引き**
  だけを担当

HAPI がリソースを検査する途中で「このコードって有効?」と判定が必要になった瞬間だけ、
fhirserver に HTTP で問い合わせます。**HAPI 単独ではコード実在は判定できず、fhirserver 単独
ではリソース構造は判定できない**、両者は補完関係です。

詳細フローと責務境界表は [`architecture.md`](architecture.md#validation-中の役割分担-hapi-↔-fhirserver) に。

### Docker と Docker Desktop

「アプリと必要なライブラリを一つの箱 (コンテナ) にまとめて、どの Mac でも同じ動きをさせる」
仕組みが Docker。Mac では **Docker Desktop** というアプリを入れると、Docker のコマンドが使える
ようになります。

### Apple Silicon (M1/M2/M3/M4 Mac) と Rosetta 2

Apple Silicon は arm64 アーキテクチャ、fhirserver は amd64 (x86_64) 向けにビルドされています。
そのままだと動かないので、**Rosetta 2** という Apple 提供の変換レイヤーを使って amd64 の
コンテナを動かします。有効化しないと **10 倍以上遅くなる** ので必ず有効化してください
(手順は次章)。

### ターミナル

macOS 標準アプリ。`Finder` → `アプリケーション` → `ユーティリティ` → `ターミナル.app`。
このガイドに書かれているコマンドは、すべてターミナルに 1 行ずつコピペして Enter を押します。

**ターミナル記号の意味**:

- 行頭の `$` は「ここからコマンド」の目印。コピペするときは `$` を含めません
- コマンドの後の `#` から行末まではコメント (説明)、実行しても影響しません
- `\` で終わる行は「次の行に続く」意味。1 つの長いコマンドを見やすく分けているだけ

例:

```bash
$ mkdir jp_core   # jp_core という名前のフォルダを作る
```

の場合、実際にターミナルに入れるのは `mkdir jp_core` の 6 文字だけです。

---

## 2. 環境を用意する

### 2.1 Docker Desktop をインストール

1. https://www.docker.com/products/docker-desktop/ にアクセス
2. `Download for Mac – Apple Chip` (Apple Silicon の場合) をクリックして DL
3. `Docker.dmg` をダブルクリック → `Docker.app` を `アプリケーション` にドラッグ
4. `アプリケーション` から `Docker` を起動、指示に従ってセットアップ完了
5. メニューバー右上にクジラのアイコンが表示され、`Docker Desktop is running` になれば OK

**メモリ設定**: `Docker Desktop` → `Settings` → `Resources` → `Memory` を 4 GB 以上に。
今回は 8 GB を推奨します。

### 2.2 Rosetta 2 を有効化 (Apple Silicon 必須)

ターミナルで以下を実行:

```bash
softwareupdate --install-rosetta --agree-to-license
```

`softwareupdate` は macOS のアップデート管理コマンド、`--install-rosetta` オプションで
Rosetta 2 を導入、`--agree-to-license` でライセンス同意 (これを付けないと途中で対話待ちに
なります)。既に入っていれば数秒で終わります。

次に **Docker Desktop の設定**でも Rosetta を有効にします:

1. Docker Desktop 右上メニュー (⚙︎) → `Settings`
2. `General` タブを開く
3. **`Use Rosetta for x86/amd64 emulation on Apple Silicon`** にチェック
4. 右下の `Apply & Restart` をクリック

**確認方法** — Rosetta で amd64 コンテナが動くかテスト:

```bash
docker run --rm --platform linux/amd64 alpine uname -m
```

出力が `x86_64` なら OK。エラーが出る場合は Docker Desktop を一度終了 → 再起動。

**この設定を忘れると**:
- fhirserver の Docker build が 8 分 → **数時間**
- SNOMED import が 10 分 → **4-8 時間**
になるので、必ず有効化してください。

### 2.3 Homebrew と git をインストール (未導入なら)

Mac には `git` (ソースコード管理コマンド) が標準では入っていないので、**Homebrew** という
パッケージ管理ツール経由で入れます。

Homebrew を入れる (未導入なら):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- `curl -fsSL <URL>` — 指定 URL の中身を取得 (`-f` fail on error、`-s` silent、`-S` show error、
  `-L` follow redirects)
- `$(...)` の部分は「実行してその出力を得る」意味
- `/bin/bash -c "..."` — 得たスクリプトを bash で実行

インストール完了後、指示された `eval "$(...)"` のような追加コマンドがあれば従います。

`git` を入れる:

```bash
brew install git
```

確認:

```bash
git --version
# → git version 2.x.x のように出れば OK
```

### 2.4 Python 3 の確認

macOS 標準で入っています。バージョン確認:

```bash
python3 --version
# → Python 3.9 以上なら OK (このプロジェクトは 3.10+ 推奨)
```

古い場合は `brew install python@3.12` で最新版を入れてください。

### 2.5 Java の確認

HAPI Validator (後で使う) が Java 11 以上を必要とします。

```bash
java --version
# → openjdk 11 以上なら OK
```

未インストールなら:

```bash
brew install openjdk@17
```

インストール後、Homebrew の指示に従って `~/.zshrc` に PATH を追加してください。

### 2.6 ディスク空き容量の確認

```bash
df -h ~
```

`Avail` 列を確認して 40 GB 以上あれば OK。

---

## 3. リポジトリを取得する

好きなディレクトリで実行:

```bash
mkdir -p ~/workspace
cd ~/workspace
git clone https://github.com/TomoOkuyama/fhir-jp-validator.git
cd fhir-jp-validator
```

- `mkdir -p ~/workspace` — `workspace` フォルダを作る (`-p` は「既にあれば何もしない」)
- `cd ~/workspace` — そのフォルダに移動 (`~` は自分のホームフォルダ)
- `git clone <URL>` — リポジトリをコピー、`fhir-jp-validator` フォルダが作られる
- `cd fhir-jp-validator` — その中に入る

これ以降のコマンドはすべて **`fhir-jp-validator/` フォルダの中** で実行することを前提とします。
現在位置が不安になったら `pwd` を打つと今いるフォルダが表示されます。

---

## 4. fhirserver の Docker イメージをビルドする

fhirserver は HL7 公式の Pascal 実装で、Linux ビルド済みバイナリが配布されていないので
Docker の中で自前ビルドします。本 repo に自動化スクリプトが用意されています。

```bash
./scripts/setup-fhirserver.sh
```

このスクリプトは内部で:

1. `HealthIntersections/fhirserver` (公式 リポジトリ) を `tx-server-build/fhirserver/` に
   `git clone` する
2. `patches/*.patch` を適用する
   - LOINC / SNOMED を CLI からインポートできるようにする追加
   - SNOMED インポート時の日付フォーマットバグ修正
3. `docker buildx build --platform linux/amd64` で amd64 の Docker イメージを作成
   (`fhir-jp-validator/fhirserver:local` というタグ)

**所要時間** (Rosetta 有効時、初回):

- Free Pascal + MySQL ODBC ライブラリを Docker 内でインストール: 2-3 分
- fhirserver のソースコード compile: 3-5 分
- Docker image 完成: 1 分
- **合計: 5-8 分**

進捗が見えないと不安になりますが、ログは `tx-server-build/build.log` にも書き込まれるので
別のターミナルタブで:

```bash
tail -f tx-server-build/build.log
```

を実行しておくと リアルタイム で進行が見えます (`tail -f` は「ファイル末尾を追いかける」)。

### 完了確認

ビルドが成功したら以下でイメージが作られたことを確認:

```bash
docker images fhir-jp-validator/fhirserver
```

`fhir-jp-validator/fhirserver   local   xxxxx   数分前   486MB` のような行が出れば OK。

---

## 5. 無料の日本 IG を取得する (JP Core / JP-CLINS / jpfhir-terminology)

これらはすべて **CC0 ライセンス** (パブリックドメイン相当) で無償配布されています。
再配布や商用利用も自由で、帰属表記も不要 (推奨はされる)。

### 5.1 JP Core 1.2.0

```bash
mkdir -p jp_core
cd jp_core
curl -sSL https://jpfhir.jp/fhir/core/pkghistory/jp-core.r4-1.2.0.tgz | tar xz
cd ..
```

- `mkdir -p jp_core` — `jp_core` フォルダを作る
- `cd jp_core` — そこに移動
- `curl -sSL <URL>` で `.tgz` (圧縮ファイル) をダウンロード
- `|` (パイプ) で `tar xz` に渡し、その場で展開 (`x` extract、`z` gzip 対応)
- `cd ..` で 1 つ上のフォルダ (repo ルート) に戻る

展開されるフォルダ: `jp_core/package/` (~2 MB)。

### 5.2 JP-CLINS 1.12.0

```bash
mkdir -p 'tx-server-build/terminology/fhir-server/clinical-information-sharing#1.12.0'
curl -sSL https://jpfhir.jp/fhir/clins/igv1/package.tgz \
  | tar xz -C 'tx-server-build/terminology/fhir-server/clinical-information-sharing#1.12.0/'
```

- `-C <folder>` は tar の「展開先フォルダを指定」オプション
- フォルダ名にシングルクォート `'...'` を使っているのは、`#` がシェルでコメント記号扱いに
  ならないようにするため (`#` 以降が消えないように守る)
- **重要**: `/pkghistory/` にある `.tgz` (152 KB) は差分版で不完全です。必ず `/igv1/package.tgz`
  (2.5 MB、完全版) を使ってください

### 5.3 jpfhir-terminology 2.2606.0

```bash
mkdir -p 'tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0'
curl -sSL https://jpfhir.jp/fhir/core/terminology/igv-2.2606.0/package.tgz \
  | tar xz -C 'tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/'
```

これで日本独自の CodeSystem・ValueSet (JP_MedicationCode_VS、JP_SimpleObservationCategory_VS
等) と UCUM (単位コード) が揃います。

---

## 6. LOINC を取得する (無料、要ユーザ登録)

LOINC は検査項目・観察項目の国際コード。**LOINC License** は無料 (商用利用も OK、要帰属表記)
ですが、DL には loinc.org のアカウント作成 + ライセンス受諾が必要です。

### 6.1 アカウント作成 + ライセンス受諾

1. https://loinc.org/downloads/loinc-table/ にブラウザでアクセス
2. `Sign up for LOINC` からアカウント作成 (メールアドレス、氏名、所属を入力)
3. 確認メールに従い、メールアドレスを検証
4. ログインして LOINC License Terms of Use を受諾

### 6.2 LOINC Text 版を DL

同じページから **LOINC Table File (Text version)** の zip をダウンロード。

- ファイル名例: `Loinc_2.82.zip` (~ 100 MB)
- **RELMA (Windows 検索ツール) 版ではなく Text 版** を選ぶこと。RELMA では import に失敗します

### 6.3 展開

ブラウザの DL フォルダにある zip を repo に移動して展開:

```bash
mkdir -p tx-server-build/loinc-src
mv ~/Downloads/Loinc_2.82.zip tx-server-build/loinc-src/
cd tx-server-build/loinc-src
unzip Loinc_2.82.zip
cd ../..
```

- `mv <src> <dest>` — ファイル移動
- `unzip <file>` — zip ファイル展開
- `cd ../..` — 1 つ上 → さらに 1 つ上 (repo ルートに戻る)

展開後の中身: `tx-server-build/loinc-src/Loinc_2.82/` フォルダに `LoincTable/`、
`AccessoryFiles/` 等が入っていれば OK。

LOINC の cache 変換は次章 (`8. 用語集を fhirserver 用の cache に変換する`) で行います。

---

## 7. SNOMED CT を取得する (無料だが UMLS ライセンス申請要、注意事項多い)

このステップが本ガイドの中で **一番注意が必要** です。SNOMED CT は無料ですが、
UMLS ライセンスという申請制のライセンスが必要で、**個人ライセンスには利用制約があります**。

### 7.1 UMLS ライセンス申請

1. https://uts.nlm.nih.gov/uts/ にアクセスして `Sign Up` からアカウント作成
2. UMLS License Request フォームで **利用目的** を明記して申請
   - 個人研究や学習であれば「FHIR JP Core / JP-CLINS 準拠性検証のための terminology 検証」
     のように書けば通ります
3. **承認まで平均 3-5 営業日** (2026-07 時点)、承認メールが届くまで待つ

**申請が承認されないと SNOMED は DL できません**。承認待ちの間は SNOMED 抜き構成でセット
アップを進めることも可能 (後述 FAQ 参照)。

### 7.2 個人ライセンスの利用制約 (重要)

UMLS Individual License の場合、**以下は違反** です:

- **共有クラウド (AWS EC2、GCP、Azure 等) に SNOMED を含むデータ / image を配置**
- **他人と共有** (社内 shared server、team メンバーへの image 配布、Docker Hub への push 等)
- **商用製品への組込み** (別途 Affiliate 契約=法人契約が必要)

**OK なのは**:

- 個人研究用途で自分の Mac / 自宅の 個人開発マシンで使う
- 本 repo は絶対に SNOMED cache をコミットしません (`.gitignore` で除外済)

商用製品に組み込みたい場合は、SNOMED International の Affiliate 契約に切り替えてください
(法人向け、有償)。

**日本での利用のポイント**:

- 日本は SNOMED International Member ではない (2026-07 時点)
- そのため **SNOMED CT Japan Edition は存在しません**、International Edition (英語版) を使います
- JP Core / JP-CLINS の SNOMED 参照はすべて International Edition のコードです

### 7.3 SNOMED CT International Edition を DL

UMLS 承認後:

1. https://uts.nlm.nih.gov/uts/ にログイン
2. `Download UMLS` → `SNOMED CT International` セクション
3. `SnomedCT_InternationalRF2_PRODUCTION_YYYYMMDDT120000Z.zip` (~ 1.4 GB) を DL
4. 推奨バージョン: 2026-06-01 リリース (`20260601`)

### 7.4 展開

```bash
mkdir -p tx-server-build/snomed-src
mv ~/Downloads/SnomedCT_InternationalRF2_PRODUCTION_20260601T120000Z.zip \
  tx-server-build/snomed-src/
cd tx-server-build/snomed-src
unzip SnomedCT_InternationalRF2_PRODUCTION_20260601T120000Z.zip
cd ../..
```

**時間がかかります** (数分)。zip の中身が 3 GB 近くあるため。

---

## 8. 用語集を fhirserver 用の cache に変換する

fhirserver は起動時に大量のテキストファイルを読むと遅いので、**自分専用のバイナリ cache 形式**
に事前変換します。この変換は Chapter 4 で作った `fhirserver` Docker image に含まれている
専用 CLI (patches で追加された `-cmd loinc-import` / `snomed-import`) で行います。

### 8.1 LOINC を cache に変換 (2-3 分)

```bash
docker run --rm --platform linux/amd64 \
  -v $(pwd)/tx-server-build/loinc-src:/loinc:ro \
  -v $(pwd)/tx-server-build/terminology:/out \
  fhir-jp-validator/fhirserver:local \
  /fhirserver/fhirserver -cmd loinc-import \
    -source /loinc/Loinc_2.82 \
    -version 2.82 \
    -date 2026-02-24 \
    -dest /out/loinc-2.82.cache
```

コマンド 1 行ずつの説明:

- `docker run --rm --platform linux/amd64` — amd64 コンテナを起動、終わったら削除 (`--rm`)
- `-v <ホスト側>:<コンテナ内>` — フォルダを共有 (`:ro` は read-only)
  - `$(pwd)` は「現在のフォルダの絶対パス」
  - `tx-server-build/loinc-src` (LOINC のソース) を コンテナの `/loinc` として見せる
  - `tx-server-build/terminology` (cache 出力先) を コンテナの `/out` として見せる
- `fhir-jp-validator/fhirserver:local` — 使う image
- `/fhirserver/fhirserver -cmd loinc-import ...` — image 内の CLI を実行
- `-source /loinc/Loinc_2.82` — LOINC の展開先 (コンテナ視点のパス)
- `-version 2.82 -date 2026-02-24` — LOINC のバージョン情報 (`Loinc_2.82.zip` のリリース日)
- `-dest /out/loinc-2.82.cache` — 出力先 (コンテナ視点、ホストでは `tx-server-build/terminology/loinc-2.82.cache`)

**成功すると**: `tx-server-build/terminology/loinc-2.82.cache` (~ 841 MB、252k コンセプト)

### 8.2 SNOMED を cache に変換 (Rosetta 有効時 約 10 分)

```bash
docker run --rm --platform linux/amd64 \
  -v $(pwd)/tx-server-build/snomed-src:/snomed:ro \
  -v $(pwd)/tx-server-build/terminology:/out \
  fhir-jp-validator/fhirserver:local \
  /fhirserver/fhirserver -cmd snomed-import \
    -source /snomed/SnomedCT_InternationalRF2_PRODUCTION_20260601T120000Z/Snapshot \
    -uri http://snomed.info/sct/900000000000207008/version/20260601 \
    -lang 1 \
    -dest /out/snomed-int-20260601.cache
```

- `-source` に指定するのは zip 展開後の `Snapshot/` フォルダ (Full/ ではない、Snapshot/ を選ぶ)
- `-uri` は SNOMED CT International Edition の canonical URI + 版
  (`900000000000207008` は International Edition の module ID、`20260601` はリリース日)
- `-lang 1` は英語 (SNOMED CT の language code)
- `-dest` は出力先

**成功すると**: `tx-server-build/terminology/snomed-int-20260601.cache` (~ 846 MB)

**Rosetta 未有効だと 4-8 時間かかります**。10 分を超えても終わらない場合は Chapter 2.2 に
戻って Rosetta 設定を確認してください。

### 8.3 HL7 terminology / FHIR core

これらは fhirserver が起動時に `packages.fhir.org` から自動 DL するので、事前準備は不要です。
初回起動時にネットワーク接続が必要な点だけ注意。

---

## 9. fhirserver を起動して動作確認する

いよいよ起動です。

### 9.1 起動

```bash
docker compose up -d fhirserver
```

- `docker compose` — 複数コンテナの起動管理コマンド
- `up` — 起動
- `-d` — バックグラウンドで実行 (ターミナルを占有しない)
- `fhirserver` — 起動する service 名 (`docker-compose.yml` に定義済み)

### 9.2 起動ログを確認

```bash
docker logs -f fhir-jp-validator-fhirserver
```

- `-f` は「ログを追いかける」(`Ctrl+C` で抜けられます)

`All packages loaded` や `HTTP listening on port 80` のような行が出れば起動完了です。
初回起動は terminology 全 load で **約 40 秒**、以降 restart は約 15 秒。

### 9.3 動作確認 — CapabilityStatement 取得

新しいターミナルタブで:

```bash
curl http://localhost:8181/r4/metadata
```

大量の JSON が返れば OK。読みやすくしたい場合は末尾に `| jq .` を付けます (`jq` は
`brew install jq` で導入)。

### 9.4 動作確認 — LOINC コード検証

```bash
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://loinc.org&code=2951-2" \
  -H "Accept: application/fhir+json" | jq .
```

- `\$` はシェルで `$` を「そのまま送る」ためのエスケープ (`$validate-code` は FHIR の Operation)
- `-H` はリクエストヘッダー追加
- 期待出力: `"result": true`、`display: "Sodium [Moles/volume] in Serum or Plasma"`

### 9.5 動作確認 — SNOMED コード検証

```bash
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://snomed.info/sct&code=105542008" \
  -H "Accept: application/fhir+json" | jq .
```

期待出力: `"result": true`、`display: "Abstinent"`

### 9.6 動作確認 — 日本の ValueSet 展開

```bash
curl -sS "http://localhost:8181/r4/ValueSet/\$expand?url=http://jpfhir.jp/fhir/core/ValueSet/JP_SimpleObservationCategory_VS&count=3" \
  -H "Accept: application/fhir+json" | jq '.expansion.total, .expansion.contains'
```

日本の ValueSet が展開されて、いくつかのコードが JSON で返れば全部 OK です。

### 9.7 停止

作業が終わったら停止:

```bash
docker compose down
```

`docker compose up -d fhirserver` で再起動可能 (terminology は cache 済みなので早い)。

---

## 10. うまくいかないとき (よくあるトラブル)

### 10.1 `EConvertError: "20260601" is not a valid date`

SNOMED import 中に発生する場合、POSIX locale の日付フォーマットバグに引っかかっています。
本 repo の `patches/ftx_sct_services.pas.patch` で修正されているはずなので、パッチ適用忘れ
の可能性があります。以下で確認:

```bash
cd tx-server-build/fhirserver
git diff library/ftx/ftx_sct_services.pas
cd ../..
```

diff が空だったら patch 未適用、`./scripts/setup-fhirserver.sh` を再実行してください。

### 10.2 Rosetta が有効なはずなのに build / import が遅い

- Docker Desktop を完全終了 → 再起動
- ターミナルで `docker info | grep -i rosetta` を実行、`Rosetta` に関する行が出るか確認
- macOS のセキュリティ設定で Docker system extension が承認されていない可能性:
  `システム設定 → プライバシーとセキュリティ → 一般` を確認

### 10.3 `docker buildx build` が `no space left on device`

Docker の build cache が肥大化しています (fhirserver ビルドで 27 GB 使う場合あり):

```bash
docker buildx prune -a -f
```

これで build cache を全削除。ただし次回 build は cache miss で 30 分程度かかる点に注意。

### 10.4 `docker compose up` で「port 8181 already in use」

既に何かが port 8181 を使っています。使用中のプロセスを確認:

```bash
lsof -iTCP:8181 -sTCP:LISTEN
```

出てきた PID を `kill <PID>` で停止するか、`docker-compose.yml` の port を別の番号
(例: `8282:80`) に変えます。

### 10.5 `curl http://localhost:8181/r4/metadata` が connection refused

- コンテナが起動しているか確認: `docker ps` に `fhir-jp-validator-fhirserver` が出るか
- ログを確認: `docker logs fhir-jp-validator-fhirserver | tail -50`
- terminology cache が壊れている可能性: `tx-server-build/terminology/` の cache ファイルの
  サイズが 0 でないか確認

### 10.6 `docker compose` コマンドが「command not found」

古い Docker では `docker-compose` (ハイフンあり) でした。新しい Docker Desktop なら
`docker compose` (スペース) が正解。Docker Desktop を最新版に更新してください。

### 10.7 LOINC import が「LoincTable/Loinc.csv not found」

LOINC の展開先が間違っている可能性。`ls tx-server-build/loinc-src/Loinc_2.82/LoincTable/`
を実行して `Loinc.csv` が見えるか確認。zip の中身が二重フォルダになっている場合があるので
`find tx-server-build/loinc-src -name Loinc.csv` で場所を突き止めて `-source` を調整。

### 10.8 UMLS ライセンス申請が承認されない

- 申請理由に「学術/技術用途」であることを明記 (テンプレでなく自分の言葉で)
- 個人プロフィールを充実させる (所属機関、研究テーマ等)
- 商用検討中の場合は Affiliate 契約に切り替え

---

## 11. ライセンス上の重要な注意事項まとめ

**再配布 / 共有をする前に必ず確認してください**。

| コンポーネント | ライセンス | 個人利用 | 共有 / クラウド配置 | 商用 |
|---|---|:---:|:---:|:---:|
| このプロジェクトのコード | MIT | ✅ | ✅ | ✅ |
| fhirserver source (HealthIntersections) | BSD-3-Clause | ✅ | ✅ | ✅ (帰属表記要) |
| HAPI Validator | Apache-2.0 | ✅ | ✅ | ✅ |
| JP Core / JP-CLINS / jpfhir-terminology | CC0-1.0 | ✅ | ✅ | ✅ |
| LOINC | LOINC License | ✅ | ✅ | ✅ (帰属表記要) |
| **SNOMED CT (Individual UMLS)** | UMLS License | ✅ | ❌ | ❌ |
| SNOMED CT (Affiliate 契約) | Affiliate | ✅ | ✅ (要契約条件確認) | ✅ (要契約) |
| UCUM | UCUM License | ✅ | ✅ | ✅ |

**特に気をつけるべき点**:

1. **SNOMED を含む Docker image をチームで共有しない、Docker Hub に push しない、GitHub にコミット
   しない**。本 repo は `.gitignore` で `tx-server-build/snomed-src/`、`tx-server-build/terminology/snomed*.cache` を
   除外していますが、自分で新規ファイルを作る際は要注意
2. **AWS EC2 等の共有クラウドに個人 UMLS 由来の SNOMED cache を置かない**。個人ライセンス違反
3. LOINC は商用利用も再配布も可ですが、帰属表記 (`This product includes all or a portion of the LOINC® table ...`) が
   必要
4. 本 repo は MIT ですが、生成される Docker image には BSD-3-Clause の fhirserver、LOINC License の
   LOINC 変換 cache 等が混在するので、image を配布する場合は各ライセンス条項の合成に注意

---

## 12. よくある質問 (FAQ)

### Q1. SNOMED 抜きで検証したい

可能です。JP Core / JP-CLINS の terminology の大半は LOINC + jpfhir-terminology の組み合わせで
カバーされています。SNOMED を skip する場合:

1. Chapter 7-8 (SNOMED 部分) を丸ごとスキップ
2. `docker-compose.yml` の fhirserver 設定は変更不要 (SNOMED cache が無ければ load しないだけ)
3. 検証時に「Unknown code in http://snomed.info/sct」等の warning が増えますが、structure / slice
   検証は問題なく行えます

### Q2. LOINC / SNOMED を最新版にしたい

各ソースから新版を DL し、Chapter 8 の変換を新しいバージョン番号で実行、`docker-compose.yml`
または fhirserver 設定で参照 cache パスを新版に切り替えてください。旧版 cache は削除して
ディスク節約可能。

### Q3. Linux (amd64) マシンで動かしたい

Rosetta 関連の設定 (Chapter 2.2) は不要で、他はすべて同じ手順です。ネイティブ amd64 なら
Rosetta emulation の overhead が無くなり、全体で 30-50% 高速化する見込み (未実測)。

### Q4. Windows で動かしたい

未検証ですが、WSL2 + Docker Desktop for Windows で理論的には動くはず。パスや curl の書式が
一部異なるので、コマンドは適宜読み替えてください。

### Q5. 何も出力されないまま止まっているように見える

Docker の pull や build は進捗が出にくいので、別ターミナルで:

```bash
docker stats
```

を実行すると各コンテナの CPU / メモリ使用率が見えます。CPU が動いていれば作業中です。

### Q6. すべて削除してやり直したい

```bash
# fhirserver コンテナ停止 + 削除
docker compose down

# 生成物削除
rm -rf tx-server-build/{fhirserver,loinc-src,snomed-src,terminology,build.log}
rm -rf jp_core

# Docker image 削除
docker rmi fhir-jp-validator/fhirserver:local

# Docker build cache も削除 (かなり空く)
docker buildx prune -a -f
```

その後 Chapter 3 からやり直せます (git clone 部分は不要、`git pull` で最新化)。

### Q7. 次のステップは?

fhirserver が動くようになったら、HAPI Validator と組み合わせて実際の FHIR データを検証できます:

```bash
./scripts/hapi-cluster.sh start        # HAPI Validator cluster 起動 (6 JVM)
./scripts/parallel-validate.py path/to/ndjson --output result.ndjson
./scripts/hapi-cluster.sh stop
```

- 検証結果の読み方: [`docs/output-guide.md`](output-guide.md)
- 実データ検証のノウハウ: [`docs/real-world-validation.md`](real-world-validation.md)
- 性能チューニング: [`docs/benchmarks.md`](benchmarks.md)

---

## 関連ドキュメント

- [`terminology-setup.md`](terminology-setup.md) — 熟練者向けの簡潔版
- [`build-rosetta.md`](build-rosetta.md) — Rosetta ビルドの詳細
- [`licensing.md`](licensing.md) — 各ライセンスの完全な一覧
- [`architecture.md`](architecture.md) — 全体のアーキテクチャ図と仕組み
- [`../README.md`](../README.md) — プロジェクト概要とクイックスタート
