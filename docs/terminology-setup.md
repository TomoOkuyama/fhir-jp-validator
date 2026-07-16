# Terminology セットアップ手順

以下の順で入手・配置します。所要時間 (Rosetta 有効時): **合計 30-40 分** (SNOMED import が最も長い ~10 分)。

## 1. JP 系 FHIR IG (無料、CC0)

### JP Core 1.2.0

```bash
mkdir -p jp_core && cd jp_core
curl -sSL https://jpfhir.jp/fhir/core/pkghistory/jp-core.r4-1.2.0.tgz | tar xz
# → jp_core/package/ に展開
```

### JP-CLINS (clinical-information-sharing) 1.12.0

```bash
mkdir -p tx-server-build/terminology/fhir-server
cd tx-server-build/terminology/fhir-server
mkdir -p 'clinical-information-sharing#1.12.0'
curl -sSL https://jpfhir.jp/fhir/clins/igv1/package.tgz \
  | tar xz -C 'clinical-information-sharing#1.12.0/'
```

注: `/pkghistory/jp-eCSCLINS.r4-1.12.0.tgz` (152 KB) は差分版で不完全。**`/igv1/package.tgz` (2.5 MB)** が完全版です。

### jpfhir-terminology 2.2606.0

```bash
cd tx-server-build/terminology/fhir-server
mkdir -p 'jpfhir-terminology#2.2606.0'
curl -sSL https://jpfhir.jp/fhir/core/terminology/igv-2.2606.0/package.tgz \
  | tar xz -C 'jpfhir-terminology#2.2606.0/'
```

これで UCUM + JP Core Common ValueSet (JP_MedicationCode_VS, JP_SimpleObservationCategory_VS 等) の検証が可能になります。

## 2. LOINC (無料、要ユーザ登録)

1. https://loinc.org/ でアカウント作成
2. LOINC License 受諾
3. **LOINC Table (LOINC_2.82_Text.zip 相当)** を DL — RELMA ではなく Text 版
4. 展開:

```bash
mkdir -p tx-server-build/loinc-src
unzip Loinc_2.82.zip -d tx-server-build/loinc-src/
```

### fhirserver 内蔵 cache 形式に変換

```bash
# fhirserver image を使って import (~2-3 分)
docker run --rm --platform linux/amd64 \
  -v $(pwd)/tx-server-build/loinc-src:/loinc:ro \
  -v $(pwd)/tx-server-build/terminology:/out \
  iris4h-ai/fhirserver:local \
  /fhirserver/fhirserver -cmd loinc-import \
    -source /loinc/Loinc_2.82 \
    -version 2.82 \
    -date 2026-02-24 \
    -dest /out/loinc-2.82.cache
```

生成物: `tx-server-build/terminology/loinc-2.82.cache` (841 MB、252k concepts)

## 3. SNOMED CT International (UMLS ライセンス、要申請)

### 3.1. UMLS ライセンス取得

1. https://uts.nlm.nih.gov/uts/ でアカウント作成
2. UMLS License Request → 個人利用の場合 数日〜1週間で承認 (2026-07 時点、平均 3-4 営業日)
3. 承認メール到着後、UTS にログインしてダウンロード権限が付与される

**個人ライセンス制約 (重要)**:

- 用途 A: 個人研究 / 個人開発マシンでのみ利用可
- 共有クラウド (AWS EC2、GCP 等) への配置、他人と共有、社内 shared server に配置は **ライセンス違反**
- 商用製品への組込みは Affiliate 契約 (法人契約) が必要

### 3.2. SNOMED CT International Edition DL

1. https://download.nlm.nih.gov/umls/kss/IHTSDO*/SnomedCT_InternationalRF2_PRODUCTION_*.zip
2. 2026-06-01 版 (20260601) 推奨、~1.4 GB

```bash
mkdir -p tx-server-build/snomed-src
unzip SnomedCT_InternationalRF2_PRODUCTION_20260601T120000Z.zip -d tx-server-build/snomed-src/
```

### 3.3. fhirserver 内蔵 cache 形式に変換

```bash
docker run --rm --platform linux/amd64 \
  -v $(pwd)/tx-server-build/snomed-src:/snomed:ro \
  -v $(pwd)/tx-server-build/terminology:/out \
  iris4h-ai/fhirserver:local \
  /fhirserver/fhirserver -cmd snomed-import \
    -source /snomed/SnomedCT_InternationalRF2_PRODUCTION_20260601T120000Z/Snapshot \
    -uri http://snomed.info/sct/900000000000207008/version/20260601 \
    -lang 1 \
    -dest /out/snomed-int-20260601.cache
```

所要 (Rosetta 有効): **9 分 50 秒**、生成物: **846 MB**

## 4. HL7 terminology / FHIR core

fhirserver 起動時に auto load (packages.fhir.org から DL、初回のみ):

- `hl7.terminology.r4` (7.1/7.2)
- `fhir.tx.support.r4` (0.37)
- `hl7.fhir.uv.extensions.r4` (5.2/5.3)

これらは `packages.ini` に register 済みなので明示 DL 不要です。

## 5. 最終確認

```bash
docker compose up -d fhirserver
sleep 40   # 全 terminology load 待ち

# LOINC 検証
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://loinc.org&code=2951-2" \
  -H "Accept: application/fhir+json" | jq .
# → "result": true, display="Sodium [Moles/volume] in Serum or Plasma"

# SNOMED 検証
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://snomed.info/sct&code=105542008" \
  -H "Accept: application/fhir+json" | jq .
# → "result": true, display="Abstinent"

# JP-CLINS ValueSet expansion
curl -sS "http://localhost:8181/r4/ValueSet/\$expand?url=http://jpfhir.jp/fhir/core/ValueSet/JP_SimpleObservationCategory_VS&count=3" \
  -H "Accept: application/fhir+json" | jq '.expansion.total, .expansion.contains'
```

全て成功したら準備完了。次は `scripts/hapi-cluster.sh start` で HAPI cluster を起動して検証実行。
