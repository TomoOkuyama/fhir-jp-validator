# Terminology 完全 load: Licensing 確認/交渉アクション

fhir-jp-validator の完全な JP FHIR validation を実現するために必要な、外部機関との
licensing 確認/交渉の action list。

## 現状: 導入 phase 別 licensing 状態

| Phase | 対象 | Licensing 状態 | Action 要否 |
|---|---|---|---|
| Phase 1 (実装済) | MHLW ICD-10 2013 完全版 | ✅ PDL 1.0 明快、出典明記条件で再配布可 | 対応不要 |
| Phase 3 (実装済) | MHLW masterB (傷病名) / masterZ (修飾語) | ✅ PDL 1.0 明快、SSK 経由 DL、出典明記済 | 対応不要 |
| **Phase 2** | LOINC Japan Translation | 🟡 LOINC License 準拠、Regenstrief 事前通知要 | **通知メール送信** |
| **Phase 4-A** | JLAC10 CoreLabo/InfectionLabo | ✅ jpfhir-terminology 内で既 complete、追加作業なし | 対応不要 |
| **Phase 4-B** | **JLAC11 CoreLabo/InfectionLabo** | 🔴 licensing 未明示 (JCCLS/JAMI) | **問合せ要** (優先度高、55×+38× 参照) |
| **Phase 4-C** | YJ 医薬品コード (17,456) | 🔴 iyaku.info/capstandard 経由、licensing 未確定 | 問合せ要 |
| **Phase 4-D** | HOT13 (62,210)、HOT9 (33,533)、HOT7 (10,069) | 🔴 MEDIS-DC 会員契約要、再配布制限 | **賛助会員登録要** |
| **Phase 4-E** | MEDIS master-disease シリーズ 4 CS | 🔴 MEDIS-DC 会員契約要 | 同上 (Phase 4-D と一括) |
| Phase 5 (将来) | Dental procedure / Jfagy allergen | 未調査 | 後回し |

## Action 1: LOINC Japan Translation — Regenstrief 通知 (Phase 2)

**目的**: LOINC License の "translation" 条項に基づき、既存の日本語 translation を fhirserver
に load する前の事前通知義務を履行。

**送信先**: `translations@loinc.org`
**CC 候補**: `office@hl7fhir.jp` (日本 FHIR 実装研究会、JP LOINC 情報保持元)

**送信内容**:
- 事前 draft 済: `/private/tmp/.../scratchpad/regenstrief-loinc-jp-notification.md`
- ポイント: 我々は **既存 translation を consume するだけ、新規翻訳はしない**、
  data 自体は repo に含めず build script のみ提供

**確認事項**:
1. 既存 LOINC Japan translation を supplement 形式で load する行為に追加 license 手続き不要か
2. LOINC 帰属表記を fhirserver の CS.copyright field に記載する形式で充足するか
3. 実際の translation data source (LOINC Japan Committee 直か、JAMI FHIR 経由か) の推奨

**期待応答**: 3-5 営業日、通常 acknowledge のみ (translation consumption は明示的制限なし)

**沈黙の場合**: 通常「通知した」事実で LOINC License 上の義務履行、2 週間経過後は着手可

## Action 2: JP LOINC translation data source — JAMI/JCCLS 問合せ

**目的**: LOINC Japan translation の **実 data 入手ルート** 特定。

**送信先**: `office@hl7fhir.jp` (日本 FHIR 実装研究会、JCCLS 内 LOINC 委員会にリーチ可能)

**確認事項**:
1. JCCLS / JAMI が保持する LOINC Japan 訳データの配布状況
2. FHIR CodeSystem supplement 形式で入手可能か、それとも CSV/Excel からの独自変換要か
3. jpfhir-terminology 内 `CodeSystemJPDisplay/Loinc-jpdisplay` (5 concept のみ) との関係
4. 使用条件 (無料か、会員限定か)

**期待応答**: 1-2 週間 (研究会内部確認 + LOINC Japan 委員会照会が必要な可能性)

**Action 1 と並行実施可**

## Action 3: JLAC11 — JCCLS 直接問合せ

**目的**: JLAC11 (55×+38× = 影響最大の binding target) の完全版 data 入手 + license 確認。

**送信先**: JCCLS (公益社団法人 日本臨床検査標準協議会) contact page
  - https://www.jccls.org/ の問合せフォーム

**確認事項**:
1. JLAC11 full code list の入手方法 (CSV / Excel / API)
2. 再配布条件 — FHIR CodeSystem 変換版を open source repo に build script として同梱可能か
3. 商用利用条件 (fhir-jp-validator 自体は MIT、terminology data は独立 license 可)
4. AWS 等クラウド展開の可否
5. 個人利用 vs 法人利用の別料金の有無
6. 定期更新の配布方式

**期待応答**: 2-4 週間 (公益社団法人、慎重回答)、有償の可能性あり

**代替候補**: JAMI 経由 (JCCLS メンバーシップと関係あるため office@hl7fhir.jp から先に照会が
効率的な可能性)

**優先度**: 🔴 **最高** (JP-CLINS 系の 93 required binding が JLAC11 依存)

## Action 4: YJ 医薬品コード — iyaku.info / 厚労省照会

**目的**: 個別医薬品コード (17,456 concept) の完全版 data と licensing 明確化。

**入手候補**:
1. **iyaku.info** (`http://capstandard.jp/iyaku.info/CodeSystem/YJ-code-active`) — jpfhir-terminology
   が canonical URL としているホスト、実 data 提供状況要確認
2. **厚労省 薬価基準収載品目リスト** — YJ code 定義元、PDL 1.0 の可能性、要確認
3. **PMDA** (医薬品医療機器総合機構) — 医療用医薬品情報検索

**問合せ順序**:
1. iyaku.info (`capstandard.jp`) の運営元に data source と license 問合せ
2. 並行して厚労省 医政局 経済課 薬価基準収載品目関連の公開データ確認
3. 厚労省側で公開されていれば PDL 1.0 で Phase 1/3 と同構造で対応可

**期待応答**: 各機関 2-4 週間

## Action 5: MEDIS-DC 賛助会員登録 (Phase 4-D, 4-E)

**目的**: HOT13/9/7 医薬品マスタ + MEDIS master-disease シリーズを合法的に入手 + fhirserver
load。

**送信先**: MEDIS-DC (医療情報システム開発センター)
- https://www.medis.or.jp/
- 賛助会員案内: https://www.medis.or.jp/7_kikaku/sanjyo/sanjyo_01.html
- Contact form: 同 site 内

**確認事項**:
1. **賛助会員種別と年会費**
   - 個人 vs 法人 vs 学術団体
   - fhir-jp-validator は個人が MIT で公開する OSS、どの category が適用か
2. **利用範囲**:
   - 会員が入手したマスタを FHIR CodeSystem 化して public GitHub repo に build script + data
     の形で載せることは可能か
   - AWS 等クラウド展開は可能か
   - 商用製品への組込み可能条件
3. **配布形式**: CSV / Excel / FHIR CodeSystem か
4. **更新頻度**: 年次 vs 半期 vs 随時

**リスク**: 会員契約は年額有償 (数万円〜) + 契約書上の再配布制限で **build script 同梱すら不可**
の可能性あり。その場合 fhir-jp-validator は「会員が個別 DL + local 変換」する **build 手順のみ
提供** に留まる (data 自体は repo に含まない、Phase 3 の SSK 同様の運用)。

**期待応答**: 1-3 週間 (会員案内 + 具体条件確認は複数往復要)

**代替候補**: 
- HOT シリーズ自体は厚労省の副次配布データ (医薬品副作用データベース等) との重複領域が
  あり、部分的に PDL 準拠で入手可能かも要調査

## Action 順序 (推奨実行順)

**Week 1 (即着手)**:
1. Action 1: Regenstrief 通知メール送信 (低コスト、応答 3-5 営業日、承諾 or 沈黙で先へ)
2. Action 2: JAMI/JCCLS へ JP LOINC data source 問合せ (LOINC Japan committee リーチ)

**Week 1-2 (並行)**:
3. Action 3: JLAC11 問合せ (優先度最高、応答時間長め)
4. Action 5: MEDIS-DC 賛助会員登録案内請求 (会員種別・費用把握)

**Week 3-4**:
5. Action 4: YJ code — 厚労省 薬価基準リスト経由の可能性を先に検証、確定次第 iyaku.info へ照会

**Week 4+**:
6. 各 Action の応答受領 → licensing 明確化した順に Phase 2/4 の実装 phase に移行

## 応答待ちの間にできること (fhir-jp-validator 側)

- ✅ **Phase 1 + Phase 3 のブラッシュアップ** (実装済、v30b/v31 で効果測定)
- ✅ **build script の generic 化** (Phase 4 で流用できる pattern を先に洗練)
- **docs/terminology-completion-plan.md の update** (licensing 交渉状況を反映)
- **JLAC10 の validator 実測** (既 complete、v32 相当 run で validation infrastructure 確認)
- Phase 4-B/C/D/E の実装だけは licensing 待ち (data 入手不可のため)

## 責任範囲の整理

- Actions 1, 2, 4, 5: **email 送信 + 応答対応** (user 主導、私は draft と応答分析)
- Actions 3: 同上、JCCLS は公益法人ゆえ formal communication 推奨
- 全 Action で **licensing 条項の細部確認と repository への反映** は私が支援可

## 送信 template 一覧

- Action 1 (Regenstrief): `scratchpad/regenstrief-loinc-jp-notification.md` に draft 済
- Action 2 (JAMI): 要 draft
- Action 3 (JCCLS): 要 draft
- Action 4 (iyaku.info / 厚労省): 要 draft
- Action 5 (MEDIS-DC): 要 draft (会員案内請求 → 具体条件確認の 2 段階)

次段階として、user が実際に送信する email drafts (Action 2-5) を順次作成可能。
