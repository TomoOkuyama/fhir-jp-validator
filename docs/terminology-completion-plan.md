# JP terminology 完全 load 計画

FHIR R4 JP Core / JP-CLINS validation の **conformance check 完全性** を担保するための
terminology data 完全版導入計画。

## 前提: fragment CS の設計

`jpfhir-terminology` package は主要 JP CodeSystem を **意図的に fragment mode** (先頭 2,000
concept のみ) で publish しており、full data は「tx server に別途 load される想定」の
stub。fhir-jp-validator の validator infrastructure として complete conformance を実現するには
**full 版データを外部入手 → fhirserver に override load** が必要。

## 現状 gap 一覧 (jpfhir-terminology 2.2606.0 実測)

| CS URL | 参照数 | jpfhir 内 | full 予想 | Coverage | 状態 |
|---|---:|---:|---:|---:|---|
| **`http://jpfhir.jp/fhir/clins/CodeSystem/JLAC11/JP_CLINS_ObsLabResult_CoreLabo_CS`** | 55× | 13 | 数千 | <1% | ⚠️ 最優先 |
| **`http://jpfhir.jp/fhir/clins/CodeSystem/JLAC11/JP_CLINS_ObsLabResult_InfectionLabo_CS`** | 38× | 1 | 数百 | <1% | ⚠️ 最優先 |
| **`http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full`** | 数十k件 (transitively) | 2,000 | 14,877 | 13% | ⚠️ 最優先 |
| `http://medis.or.jp/CodeSystem/master-HOT13` | 数千 | 2,000 | 62,210 | 3.2% | 医薬品 core |
| `http://capstandard.jp/iyaku.info/CodeSystem/YJ-code-active` | 数千 | 2,000 | 17,456 | 11.5% | 医薬品 core |
| `http://medis.or.jp/CodeSystem/master-HOT9` | — | 2,000 | 33,533 | 6% | 医薬品 |
| `http://medis.or.jp/CodeSystem/master-HOT7` | — | 2,000 | 10,069 | 20% | 医薬品 |
| `http://medis.or.jp/CodeSystem/master-disease-*` (4 種) | 数千 | 2,000 | 数千-数万 | 部分 | 病名 modifier |
| `http://jpfhir.jp/fhir/clins/CodeSystem/JLAC10/*` | 55×+38× | 55/1 | 55/1 | **100%** | 既 complete ✅ |
| `http://jpfhir.jp/core/terminology/CodeSystemJPDisplay/Loinc-jpdisplay` | (LOINC 参照時) | 5 (supplement) | 数万 (LOINC JP subset) | <0.1% | JP display 追加 |

## Data source と licensing 分析

### ✅ 1. MHLW ICD-10 2013 完全版 (14,877 concept)

**Source**:
- 厚労省 統計情報 https://www.mhlw.go.jp/toukei/sippei/
- ファイル: `kihon2013.xlsx` (Excel、1.3 MB)
- 内容: 基本分類表 (2013 年版)

**License**: **公共データ利用規約 (PDL 1.0) 準拠**
- ✅ 再配布可 (出典明記条件)
- ✅ 商用利用可
- ✅ 編集/加工可 (加工した旨明記条件)
- ✅ **AWS 等クラウド展開可**
- 制限: 「国が作成したかのような態様」で公表不可 (加工版を厚労省公式と誤解させない)

**出典記載例**: `『疾病、傷害及び死因の統計分類』(厚生労働省) を加工して作成`

**変換手順** (実装予定):
1. `kihon2013.xlsx` を DL、`scripts/build-mhlw-icd10-full.py` で FHIR CodeSystem に変換
2. `url = "http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full"` (jpfhir-terminology と同 URI)
3. `content = "complete"` で 14,877 concept 全 emit
4. fhirserver `-cmd import-fhir-codesystem` (patch 追加要) で load
5. `docs/terminology-setup.md` に導入手順追記

**優先度**: 🔴 **最優先** — v14-v29 で 152k+ warning 出続けている根本、licensing 明快

---

### ⚠️ 2. JLAC10 / JLAC11 (日本臨床検査医学会 標準検査コード)

**Source**:
- **JLAC10**: JCCLS (日本臨床検査標準協議会) 公式配布、Excel/CSV 形式
- **JLAC11**: JAMI (日本医療情報学会) FHIR domestic 研究会公式、JP-CLINS 準拠 subset
- 主要 URL:
  - https://www.jccls.org/ (JCCLS)
  - https://jpfhir.jp/ (JP FHIR 実装研究会)

**License**: **要問い合わせ**
- 現時点で明示的な公開ライセンス表記無し
- JCCLS は「公益社団法人」、標準化目的で公開されているが再配布/クラウド展開条件は要個別確認
- **推奨**: `office@hl7fhir.jp` に問い合わせ、または JCCLS 直接問い合わせ
- Fallback: JP-CLINS 準拠の subset を jpfhir-terminology 内部で公開している範囲 (fragment) を活用、
  full 版導入は licensing 明確化後

**変換手順** (licensing 明快後):
1. JCCLS / JAMI から CSV/Excel DL
2. `scripts/build-jlac11-full.py` で FHIR CodeSystem 変換
3. `url = "http://jpfhir.jp/fhir/clins/CodeSystem/JLAC11/JP_CLINS_ObsLabResult_CoreLabo_CS"` (既存 URI 上書き)
4. `content = "complete"`
5. fhirserver load

**優先度**: 🔴 **最優先** (参照数 55×+38×、影響度最大) だが licensing 未確認で **保留** (問い合わせ中の間は fragment のまま運用)

---

### ⚠️ 3. YJ 医薬品コード (17,456 concept) + HOT13/9/7 (62k/33k/10k)

**Source**:
- **YJ コード**: iyaku.info / capstandard.jp 経由 (厚労省 薬事関連公開データ)
- **HOT シリーズ**: MEDIS-DC (医療情報システム開発センター) 公式配布
  - https://www.medis.or.jp/ の標準マスタセクション

**License**:
- **MEDIS-DC 標準マスター**: **賛助会員登録要** (会員契約の下で提供)
  - 商用利用は会員契約条件次第
  - 再配布は原則不可 (会員向け配布物)
  - **クラウド展開の可否は個別契約条件要確認**
- **YJ コード**: 公表薬価基準収載品目リスト (厚労省公開) が起源、二次加工版の再配布条件は
  発信元 (iyaku.info) に確認要

**問い合わせ先**:
- MEDIS-DC: https://www.medis.or.jp/ の contact page
- iyaku.info / capstandard.jp: 別途調査

**優先度**: 🟡 **中期** (licensing 明快後着手)、fhir-jp-validator を legal に商用配布するなら MEDIS-DC 会員登録が必須

---

### ⚠️ 4. MEDIS 病名 master (master-disease-* 系 4 種)

**Source**: 同上 MEDIS-DC

**License**: 同上 (会員登録要)

**優先度**: 🟡 **中期** (YJ/HOT と同 licensing scope、まとめて対応)

---

### ⚠️ 5. LOINC Japan Translation (supplement mode)

**Source**:
- LOINC International Translations: https://loinc.org/international/
- Japanese translation の公式提供状況: **現状 LOINC 公式 translations リストに日本語版なし**
- 代替 source:
  - **LOINC 日本語版翻訳作業部会** (日本臨床検査医学会 内)、部分翻訳が既存
  - jpfhir-terminology 内 `CodeSystemJPDisplay/Loinc-jpdisplay` (5 concept のみ、supplement 形式で
    mechanism 準備済)

**License**: **LOINC License** (無料、再配布可、Regenstrief 帰属)
- ✅ 商用利用可
- ✅ 再配布可 (copyright/license notice 付与要)
- ✅ **AWS 等クラウド展開可**
- 翻訳条件: 翻訳前に Regenstrief に email 通知要、翻訳所有権は Regenstrief に帰属
- **既存翻訳 (LOINC Japan 委員会作成分) の再配布**: LOINC License 準拠なら OK、実物データの
  licensing 状態は個別に確認要

**変換手順** (data source 決定後):
1. LOINC Japan 委員会 (JCCLS or JAMI) 経由で日本語 translation DL
2. FHIR CodeSystem supplement 形式 (`content: supplement`, `system: http://loinc.org`) に変換
3. `url` は `http://jpfhir.jp/core/terminology/CodeSystemJPDisplay/Loinc-jpdisplay` を上書き
   (jpfhir-terminology で mechanism 準備済のため path 継承)
4. fhirserver に load、Display() 経由で JP display 検証可能に

**優先度**: 🟡 **中期** (data source 特定と Regenstrief 通知が必要)

---

### ✅ 6. JLAC10 CoreLabo/InfectionLabo (既 complete、追加作業不要)

jpfhir-terminology 内で `content: complete` 既に load 済 (55 + 1 concept、実データ規模と一致)。
追加作業なし。

---

## 実装 phase (licensing 明快度順)

### Phase 1: MHLW ICD-10 2013 完全版 (即着手可)

- Licensing: ✅ PDL 1.0 で明快
- 期間: **2-3 日**
- 成果物:
  - `scripts/build-mhlw-icd10-full.py`
  - `tx-server-build/terminology/mhlw-icd10-2013-full.json` (~2-3 MB、gitignore 対象)
  - fhirserver `-cmd import-fhir-codesystem` patch (kernel.pas.patch 拡張)
  - `docs/terminology-setup.md` に手順追記
  - `docs/fhirserver-setup-for-beginners.md` の terminology 節に追記
- 効果:
  - v14-v29 の 152k+ ICD-10 fragment warning 大幅減
  - JP Condition.code の code 実在確認完全化
  - 実 EHR data validation で ICD-10 未収録 code 警告解消

### Phase 2: LOINC Japan Translation — **Not Applicable として close (2026-07-23 判定)**

**判定**: 完全な LOINC 日本語翻訳は authoritative source として現状**存在しない**。

**根拠**:
- LOINC 公式 (Regenstrief) の international languages に日本語 variant なし
- jpfhir-terminology `jp-loinc-display` supplement は 5 concept のみ (拡張版なし)、
  publisher = JAMI が必要な所だけ手動追加している pattern
- JCCLS / JSLM / JAMI / MEDIS-DC いずれも公開資産無し
- 学術・community driven の完全翻訳も未発見 (複数 AI 独立リサーチで一致)

**構造的理由**: 日本の臨床検査は **JLAC10/JLAC11** で標準化されており、LOINC 完全翻訳を作る
インセンティブが業界内に無い。JLAC 系が primary、LOINC は cross-reference 用途で英語 canonical
のまま使う運用が定着。

**推奨運用パターン** (docs/terminology-setup.md §7 参照):
1. LOINC の validate は英語 canonical で回す (現状構成)
2. 日本の実運用検査コードは **JLAC10 (既 complete、Phase 4-A 完了) + JLAC11 (Phase 4-B、
   licensing 交渉要)** で検証 — こちらが JP FHIR の primary lab code
3. UI で日本語表示が必要な場合は `Coding.display` に無理に日本語を入れず、
   `Coding.text` 側 or client-side dictionary で対応
4. 必要な特定 concept だけ jpfhir-terminology の 5 concept stub のように supplement 追加

**将来的な再検討トリガー**:
- JAMI or JSLM が正式 LOINC 日本語 mapping を公開したら再開
- Regenstrief が Japanese Linguistic Variant を認可したら再開

### Phase 3: MHLW masterB/Z + MEDIS master-disease (licensing 明快)

- MHLW masterB/Z-disease は PDL 準拠、Phase 1 と同構造
- MEDIS master-disease は Phase 4 と scope 重複、まとめて対応
- 期間: **3-5 日**

### Phase 4: JLAC11 + YJ + HOT13/9/7 + MEDIS master-disease (licensing 未確定)

- Licensing 明快化まで **保留**
- 問い合わせ先:
  - JCCLS: https://www.jccls.org/ contact
  - JAMI FHIR 研究会: `office@hl7fhir.jp`
  - MEDIS-DC: https://www.medis.or.jp/ 賛助会員登録案内
- 期間: licensing 交渉 (未定) + 実装 **1-2 週間** (全 CS 対応)

---

## fhirserver 側 patch 要件

現行 fhirserver v4.0.7 (patch 済) には CLI import-fhir-codesystem 相当が無い。以下いずれか実装要:

### Option A: 新規 CLI subcommand 追加 (patches/kernel.pas.patch 拡張)

```pascal
-cmd import-fhir-codesystem -source <path.json> -dest <name.cache>
```

- FHIR CodeSystem JSON を fhirserver 内蔵 storage 形式に変換して load
- 起動時 auto-load

### Option B: FHIR IG package として提供

- FHIR IG package (`.tgz`) 形式で bundle
- `packages.ini` に追加登録
- fhirserver 起動時に auto load
- **より簡便、上流互換性高い、推奨**

Phase 1 実装時は Option B を採用予定 (package.tgz 生成 → `packages.ini` 登録)。

---

## 全体スケジュール (概算)

| Phase | 内容 | Licensing | 実装 | Wall-clock |
|---|---|---|---|---|
| 1 | MHLW ICD-10 完全版 | 明快 (PDL) | 2-3 日 | 3 日 |
| 2 | LOINC JP translation | 通知要 | 2-3 日 | 通知後 2-3 週 |
| 3 | MHLW masterB/Z + MEDIS 病名 (公開範囲) | PDL / 一部要問合せ | 3-5 日 | 1-2 週 |
| 4 | JLAC11 + YJ + HOT + MEDIS 完全 | 要問合せ (JCCLS, JAMI, MEDIS-DC) | 1-2 週 | 1-2 ヶ月 |

**全 Phase 完了で fhir-jp-validator は「FHIR R4 JP full-conformance validator」として complete
に到達**、public value が大きく上がる。

## 次アクション

1. **Phase 1 即着手**: MHLW ICD-10 完全版の `kihon2013.xlsx` DL → 変換 script 実装
2. **Phase 2 事前**: Regenstrief に LOINC Japan translation 使用通知 (email 送信)
3. **Phase 4 事前**: JCCLS / JAMI / MEDIS-DC への licensing 問合せ

Phase 1 は v29 完了 + 集計 の後に着手推奨 (fhirserver は Phase 1 実装中に再起動 + 検証で
一時停止 必要のため、running run と並行しない)。
