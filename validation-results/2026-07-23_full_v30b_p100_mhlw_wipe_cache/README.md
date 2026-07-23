# 2026-07-23 v30b — Phase 1 (MHLW ICD-10 complete) 効果測定 (fresh cache)

## 位置付け

Phase 1 実装 (MHLW ICD-10 2013 完全版 15,586 concept 導入) の真の効果測定。
v29 と同 dataset (clinosim master `0ef6edcf`) に対し、新 fhirserver + **HAPI on-disk txCache
wipe 後** で再検証。fragment CS 由来 warning が real 検証結果 (OK / display mismatch / Unknown)
にどう分岐したかを実測。

前 run (v30) は tx-cache warm 状態で古い fragment 判定を cache hit で継続、真の効果が
見えなかったための reset run。

## Setup

- fhirserver: v29 baseline + Phase 1 (fhir-jp-validator.mhlw-icd10-2013-full#1.1.2 追加 load)
- **`.hapi-cache/tx-cache/*` を完全 wipe**
- HAPI cluster 6 JVM tx=8181 fresh start
- Data: 35,062 res (v29 と同一)

## Result

| 指標 | 値 | v29 比 | v30 (warm) 比 |
|---|---:|---:|---:|
| 所要 | 16.1 min | -3.2 min | -2.5 min |
| 平均 rps | **36.0** | +20% | +15% |
| error 総数 | 5,115 | +420 | +414 |
| warning 総数 | 51,757 | -434 | -428 |
| information 総数 | 70,791 | ±0 | ±0 |
| HTTP failed | 0 | ↔ | ↔ |

## Phase 1 の真の効果 (v29 → v30b 詳細)

### MHLW ICD-10 code 状態変化

| 状態 | v29 (fragment CS) | v30b (complete CS) |
|---|---:|---:|
| Fragment warning | **6,700** | **0** ✅ (完全消滅) |
| Display mismatch error | 0 | **420** (新可視化) |
| **真の validation success (silent OK)** | ~0 (fragment ゆえ確認不能) | ~6,280 |

**Phase 1 の意義**:

1. **fragment 隠しが取れて validation coverage が真に complete 化**
2. 隠れていた **data 側 display 誤り 420 件** を表面化 (silent → error)
3. 6,700 warnings → 6,280 の code 実在確認 (真の OK) + 420 の display mismatch
4. validator infrastructure として「JP ICD-10 の code 実在確認と display 検証が両方できる」
   状態に到達

## 発掘: MHLW ICD-10 display mismatch 420 errors (Pattern C 新規)

### Top 15 unique mismatch

| code | 件数 | emit (generator 側) | canonical (MHLW 2013) |
|---|---:|---|---|
| I10 | 210 | 本態性高血圧症 | 本態性（原発性＜一次性＞）高血圧（症） |
| Z00.0 | 51 | 一般的医学的検査 | 一般医学的検査 (「的」1 文字余分) |
| E78 | 28 | 脂質異常症 | リポタンパク＜蛋白＞代謝障害及びその他の脂血症 |
| Z23 | 27 | 予防接種 | 単独の細菌性疾患に対する予防接種の必要性 |
| E11.9 | 24 | 2型糖尿病（合併症なし） | ２型＜インスリン非依存性＞糖尿病＜NIDDM＞，合併症を伴わないもの |
| Z09 | 11 | 治療後フォローアップ | 悪性新生物＜腫瘍＞以外の病態の治療後の経過観察＜フォローアップ＞検査 |
| Z12.3 | 10 | 乳房の新生物に対する特殊スクリーニング検査 | 乳房の新生物＜腫瘍＞の特殊スクリーニング検査 |
| Z13.5 | 8 | 眼及び耳の障害に対する特殊スクリーニング検査 | 眼及び耳の障害の特殊スクリーニング検査 |
| M81 | 6 | 骨粗鬆症（病的骨折なし） | 骨粗しょう＜鬆＞症＜オステオポローシス＞，病的骨折を伴わないもの |
| I48 | 6 | 心房細動・心房粗動 | 心房細動及び粗動 |
| Z12.1 | 5 | 腸管の新生物に対する特殊スクリーニング検査 | 腸管の新生物＜腫瘍＞の特殊スクリーニング検査 |
| A08.4 | 4 | ウイルス性腸炎、詳細不明 | ウイルス性腸管感染症，詳細不明 |
| N39.0 | 4 | 尿路感染症、部位不明 | 尿路感染症，部位不明 |
| J06.9 | 3 | 急性上気道感染症、詳細不明 | 急性上気道感染症，詳細不明 |
| A05.9 | 3 | 細菌性食中毒、詳細不明 | 細菌性食中毒，詳細不明 |

**共通 pattern**:

1. **`＜XXX＞` 併記表記の欠落**: 悪性新生物＜腫瘍＞、リポタンパク＜蛋白＞、２型＜インスリン非依存性＞
   等の疾患 name の詳細表記
2. **句読点差**: 全角カンマ `，` vs 読点 `、`
3. **簡略名 vs 正式名**: `脂質異常症` vs `リポタンパク＜蛋白＞代謝障害及びその他の脂血症`
4. **半角/全角数字**: `2型` vs `２型`

## 残 5,115 error の分類

| category | 件数 | 状態 |
|---|---:|---|
| Pattern B (JP_Patient_eCS 未 match) | 3,426 | 継続 (Issue #378 次 chain) |
| Pattern A: LOINC 80288-4 residual | 1,252 | 継続 (canonical 'Level of consciousness' 修正待ち) |
| **Pattern C: MHLW ICD-10 display mismatch (Phase 1 で新可視化)** | **420** | **新規、data 側 display 修正で 0 化可能** |
| Pattern A: 新規 6 code | 6 | 継続 |
| Composition eReferral | 11 | client-side infra |
| **計** | **5,115** | |

## Phase 1 実装物と licensing 遵守確認

- CS URL: `http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full` version `1.1.2`
- Concept 数: 15,586 (fragment 2,000 の 7.8x)
- License: 公共データ利用規約 (PDL 1.0)、`copyright` field に「『疾病、傷害及び死因の統計分類』
  (厚生労働省) を加工して作成」記載済
- Source data (`kihon2013.xlsx`) は gitignore、user が個別 DL する運用

## 追加発見: fragment 隠しは他 CS でも継続

v30b の warning 内訳:
- MHLW ICD-10 fragment: **0** (Phase 1 で解消)
- 他 CS の fragment warning:
  - `medis-codesystem-hot13` 系: ~5,100
  - `capstandard.jp/YJ-code`: ~4,100
  - その他 (MEDIS master-disease 等): 数千
  - **合計 ~10,378** — Phase 3/4 で全解消可能

**Phase 3/4 完了で warning は数万件レベルの削減**、validation infrastructure がさらに complete
に近づく見込み。

## 次アクション

1. **Pattern C を workspace:1 (clinosim) に通知** — display 修正で 420 → 0 到達
2. **Phase 3 着手**: MHLW masterB/Z-disease (同 PDL、実装コスト小、warning さらに削減)
3. Phase 4 licensing 交渉 (JLAC11 は 55x+38x で影響最大)

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
