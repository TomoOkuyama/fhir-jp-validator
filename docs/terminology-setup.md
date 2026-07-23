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
  fhir-jp-validator/fhirserver:local \
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
  fhir-jp-validator/fhirserver:local \
  /fhirserver/fhirserver -cmd snomed-import \
    -source /snomed/SnomedCT_InternationalRF2_PRODUCTION_20260601T120000Z/Snapshot \
    -uri http://snomed.info/sct/900000000000207008/version/20260601 \
    -lang 1 \
    -dest /out/snomed-int-20260601.cache
```

所要 (Rosetta 有効): **9 分 50 秒**、生成物: **846 MB**

## 3.5 MHLW ICD-10 2013 完全版 (optional、推奨)

jpfhir-terminology 2.2606.0 の `ICD10-2013-full` CS は fragment 版 (先頭 2,000 concept のみ)。
病名 code の実在確認を complete にするため、厚労省 統計情報から 15,586 concept 全部を
FHIR CodeSystem 化して override load する:

```bash
# 1. 厚労省 統計情報 (公共データ利用規約 PDL 1.0) から DL
mkdir -p tx-server-build/mhlw-icd10-src
curl -sSL -o tx-server-build/mhlw-icd10-src/kihon2013.xlsx \
  "https://www.mhlw.go.jp/toukei/sippei/xls/kihon2013.xlsx"

# 2. openpyxl 経由で FHIR CodeSystem (content=complete) に変換
pip install openpyxl
./scripts/build-mhlw-icd10-full.py

# 3. FHIR NPM package (.tgz) に pack
./scripts/build-mhlw-icd10-package.sh

# 4. terminology dir に extract、package.ini に登録
PKG_DIR='tx-server-build/terminology/fhir-server/fhir-jp-validator.mhlw-icd10-2013-full#1.1.2'
mkdir -p "$PKG_DIR"
tar -xzf tx-server-build/mhlw-icd10-src/fhir-jp-validator.mhlw-icd10-2013-full-1.1.2.tgz -C "$PKG_DIR/"
cp tx-server-build/mhlw-icd10-src/pkg-stage/package/.index.json "$PKG_DIR/package/"

# 5. jpfhir-terminology の fragment CS を disable (version 衝突回避)
mv 'tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package/CodeSystem-mhlw-codesystem-icd10-2013-jp.json' \
   'tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package/CodeSystem-mhlw-codesystem-icd10-2013-jp.json.disabled'
python3 -c "
import json
p='tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package/.index.json'
d=json.load(open(p)); d['files']=[f for f in d['files'] if f.get('filename')!='CodeSystem-mhlw-codesystem-icd10-2013-jp.json']
json.dump(d,open(p,'w'),ensure_ascii=False,indent=2)"

# 6. fhirserver-config/config.json の packages 一覧に追加、restart
python3 -c "
import json
p='tx-server-build/fhirserver-config/config.json'
c=json.load(open(p))
pkgs=c['content']['uv']['packages']['r4']
if 'fhir-jp-validator.mhlw-icd10-2013-full' not in pkgs:
    pkgs.append('fhir-jp-validator.mhlw-icd10-2013-full')
json.dump(c,open(p,'w'),indent=2)"

docker restart fhir-jp-validator-fhirserver
sleep 45   # load 完了待ち

# 動作確認
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full&code=Z00.0" \
  -H "Accept: application/fhir+json" | jq '.parameter[] | select(.name=="display" or .name=="result")'
# → "result": true, "display": "一般医学的検査"
```

出典明記例 (再配布時、`copyright` field に記載済み):
> 『疾病、傷害及び死因の統計分類』(厚生労働省) を加工して作成

## 3.6 MHLW レセプト電算 傷病名/修飾語マスター 完全版 (optional、推奨)

jpfhir-terminology の `masterB-disease` (傷病名、27,684 concept) と `masterZ-disease-modifier`
(修飾語、2,390 concept) は fragment (先頭 2,000 concept のみ) 版で publish されている。
社会保険診療報酬支払基金 (SSK) から完全版 CSV を DL して override:

```bash
# 1. SSK から DL (公共データ利用規約 PDL 1.0)
mkdir -p tx-server-build/mhlw-receipt-src && cd tx-server-build/mhlw-receipt-src
curl -sSL -o b_20260601.zip -A "Mozilla/5.0" \
  "https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_07.files/b_20260601.zip"
curl -sSL -o z_20260601.zip -A "Mozilla/5.0" \
  "https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_08.files/z_20260601.zip"
unzip -o b_20260601.zip && unzip -o z_20260601.zip
cd ../..

# 2. FHIR CodeSystem 変換 (SHIFT_JIS → UTF-8、CSV → JSON)
./scripts/build-mhlw-receipt-masters.py
# → CodeSystem-mhlw-masterB-disease.json (2.1 MB), -masterZ-modifier.json (0.2 MB)

# 3. FHIR NPM package (.tgz) 化
./scripts/build-mhlw-receipt-package.sh

# 4. terminology dir に extract、jpfhir-terminology 内の fragment CS を disable
PKG_DIR='tx-server-build/terminology/fhir-server/fhir-jp-validator.mhlw-receipt-masters#5.18.1'
mkdir -p "$PKG_DIR"
tar -xzf tx-server-build/mhlw-receipt-src/fhir-jp-validator.mhlw-receipt-masters-5.18.1.tgz -C "$PKG_DIR/"
cp tx-server-build/mhlw-receipt-src/pkg-stage/package/.index.json "$PKG_DIR/package/"

for f in CodeSystem-jp-conditiondieasecodereceipt-cs.json CodeSystem-jp-conditiondieasemodifierreceipt-cs.json; do
  mv "tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package/$f" \
     "tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package/${f}.disabled"
done
python3 -c "
import json
p='tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package/.index.json'
d=json.load(open(p))
excl={'CodeSystem-jp-conditiondieasecodereceipt-cs.json','CodeSystem-jp-conditiondieasemodifierreceipt-cs.json'}
d['files']=[f for f in d['files'] if f.get('filename') not in excl]
json.dump(d,open(p,'w'),ensure_ascii=False,indent=2)"

# 5. config に追加、restart
python3 -c "
import json
p='tx-server-build/fhirserver-config/config.json'
c=json.load(open(p))
pkgs=c['content']['uv']['packages']['r4']
if 'fhir-jp-validator.mhlw-receipt-masters' not in pkgs: pkgs.append('fhir-jp-validator.mhlw-receipt-masters')
json.dump(c,open(p,'w'),indent=2)"
docker restart fhir-jp-validator-fhirserver && sleep 45

# 動作確認
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterB-disease&code=8848176" \
  -H "Accept: application/fhir+json" | jq '.parameter[] | select(.name=="display" or .name=="result")'
# → "result": true, "display": "１１β−水酸化酵素欠損症"
```

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

# MHLW ICD-10 (3.5 節導入時) — fragment 外 code の complete 化を検証
curl -sS "http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full&code=C34" \
  -H "Accept: application/fhir+json" | jq '.parameter[] | select(.name=="display" or .name=="result")'
# → "result": true, "display": "気管支及び肺の悪性新生物＜腫瘍＞"
```

全て成功したら準備完了。次は `scripts/hapi-cluster.sh start` で HAPI cluster を起動して検証実行。

## 6. 追加の terminology 完全版 (実装済 + 計画)

- ✅ Phase 1: MHLW ICD-10 2013 完全版 (§3.5 参照、実装済)
- ✅ Phase 3: MHLW masterB (傷病名) + masterZ (修飾語) 完全版 (§3.6 参照、実装済)
- ❌ **Phase 2: LOINC Japan Translation** — **Not Applicable と判定**
  ([terminology-completion-plan.md](terminology-completion-plan.md) 参照)
- ⏳ Phase 4: JLAC11 / YJ / HOT13/9/7 / MEDIS 完全版 (licensing 交渉中、
  [terminology-licensing-actions.md](terminology-licensing-actions.md) 参照)

## 7. LOINC display の運用パターン (JP FHIR data)

**Phase 2 (LOINC 日本語 translation) は現状 authoritative source が存在しないため見送り**
判定。fhir-jp-validator では以下の運用を推奨:

### 検査コードの一次選択

- **JLAC10 / JLAC11 を primary** に使う (日本の臨床検査標準、jpfhir-terminology 内で
  提供)
  - JLAC10 CoreLabo/InfectionLabo は既 complete (jpfhir-terminology 2.2606.0 内)
  - JLAC11 は fragment 状態、Phase 4-B で完全化予定
- LOINC は cross-reference 用途で **英語 canonical のまま** 使う (`system: http://loinc.org`、
  `display` は LOINC LONG_COMMON_NAME を emit)

### 日本語表示の扱い

- `Coding.display` に **日本語を無理に入れない** (canonical と mismatch で validator error 化)
- 日本語 UI 表示が必要な場合は `CodeableConcept.text` field で local 日本語表現を保持
  - text field は canonical validate されない
  - JLAC10/11 使用時は JLAC 側の日本語 display が canonical として使える (translation 不要)
- 部分的に必要な LOINC 日本語 display があれば個別に supplement 追加
  (jpfhir-terminology の `Loinc-jpdisplay` 5 concept と同 pattern で個別追加)

### 例

```json
{
  "code": {
    "coding": [
      {
        "system": "http://jpfhir.jp/fhir/clins/CodeSystem/JLAC11/JP_CLINS_ObsLabResult_CoreLabo_CS",
        "code": "3B015000002327101",
        "display": "クレアチニン [血清]"
      },
      {
        "system": "http://loinc.org",
        "code": "2160-0",
        "display": "Creatinine [Mass/volume] in Serum or Plasma"
      }
    ],
    "text": "血清クレアチニン"
  }
}
```

- JLAC11 が primary (日本の実運用 code + 日本語 display で canonical)
- LOINC は cross-reference (英語 canonical で validator conformance を保つ)
- text で UI 用日本語を保持
