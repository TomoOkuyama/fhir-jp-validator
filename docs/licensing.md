# ライセンスと入手方法 (要確認)

本プロジェクト自体は MIT ライセンスですが、**terminology 系のデータには個別のライセンスが適用**されます。以下、各データセットの入手経路とライセンス上の注意点をまとめます。

## 1. 本 repo のコード (scripts、docs、Dockerfile、patches)

- ライセンス: [MIT](../LICENSE)
- 使用制限: なし (自由に use / copy / modify / publish / distribute / sublicense / sell)
- `patches/*.patch` は fhirserver (BSD-3-Clause) 派生。patch を適用した状態のバイナリを再配布する場合は BSD-3-Clause の帰属表記が必要

## 2. HL7 fhirserver (Pascal)

- 上流: https://github.com/HealthIntersections/fhirserver
- ライセンス: **BSD-3-Clause** (`fhirserver/LICENSE` を参照)
- 商用利用: 可 (帰属表記要)
- 本 repo は clone + patch 適用スクリプトのみ提供、source code 自体は含みません

## 3. HAPI Validator CLI

- 上流: https://github.com/hapifhir/org.hl7.fhir.core
- ライセンス: **Apache-2.0**
- 商用利用: 可
- `scripts/hapi-cluster.sh` の初回起動時に GitHub Releases から自動 DL (~177 MB)

## 4. JP Core (Japan FHIR Implementation Guide)

- 公式サイト: https://jpfhir.jp/fhir/core/
- ライセンス: **CC0-1.0** (Public Domain 相当)
- 商用利用: 可、帰属不要 (推奨)
- 現バージョン: 1.2.0 (2025-11-28 release)

## 5. JP-CLINS (電子カルテ情報共有サービス実装ガイド)

- 公式サイト: https://jpfhir.jp/fhir/clins/igv1/
- パッケージ名: `clinical-information-sharing` (NPM 内)、canonical `http://jpfhir.jp/fhir/clins`
- ライセンス: **CC0-1.0**
- 商用利用: 可、帰属不要 (推奨)
- 現バージョン: 1.12.0 (2026-02-15 build)

## 6. jpfhir-terminology (JP FHIR Terminology)

- 公式サイト: https://jpfhir.jp/fhir/core/terminology/igv-2.2606.0/
- パッケージ名: `jpfhir-terminology` (NPM 内)、canonical `http://jpfhir.jp/fhir/jpfhir-terminology`
- ライセンス: **CC0-1.0**
- 現バージョン: 2.2606.0 (2026-06-21 build、対応: CLINS + JP-Core 1.2.x)
- 内容: UCUM、JP Core Common ValueSet (JP_MedicationCode_VS、JP_SimpleObservationCategory_VS 等)、日本 CodeSystem (JP_ConditionSeverity_CS 等)

## 7. LOINC (Logical Observation Identifiers Names and Codes)

- 公式サイト: https://loinc.org/
- **入手前にアカウント作成 + LOINC License 受諾が必要**
- ライセンス: LOINC License (無料、非商用/商用問わず利用可、再配布 OK)
- 商用利用: 可 (LOINC 帰属表記要)
- ライセンス全文: https://loinc.org/license/
- 本 repo での使用: LOINC 2.82 (2026-02-24 release) を推奨
- **本 repo に LOINC ソースは含みません**、ユーザが自分で DL してください

## 8. SNOMED CT (Systematized Nomenclature of Medicine - Clinical Terms) ⚠️ 要注意

- 公式サイト: https://www.snomed.org/、UMLS 経由 https://uts.nlm.nih.gov/uts/
- **UMLS Metathesaurus License が必要** (無料だが申請要、承認まで数営業日)
- ライセンス: **UMLS Metathesaurus License** (SNOMED CT 部分は SNOMED International 帰属)
- 個人ライセンス (Individual UMLS Account) の使用制約:
  - **用途 A**: 個人研究 / 個人開発マシンでのみ使用可
  - **NG**: 共有クラウド (AWS EC2、GCP 等)、他人との共有、社内 shared server への配置
  - **NG**: 商用製品への組込み (別途 Affiliate 契約=法人契約要)
- 日本での利用:
  - 日本は SNOMED International Member ではない (2026-07 現在)
  - **SNOMED CT Japan Edition は存在しません**、International Edition (英語版) を使用
  - JP Core / JP-CLINS の terminology は SNOMED CT International を参照
- **本 repo に SNOMED cache/binary は絶対に含めません**、ユーザが自分で UMLS ライセンス取得 → DL してください
- SNOMED CT Affiliate 契約 (法人向け):
  - https://www.snomed.org/get-snomed で見積依頼
  - 商用製品組込み時に必要

## 9. UCUM (Unified Code for Units of Measure)

- 公式サイト: https://ucum.org/
- ライセンス: 独自ライセンス (再配布可、条件付き、詳細は https://ucum.org/license.html)
- 商用利用: 可
- 本 repo では `jpfhir-terminology` package 内に含まれる形で使用 (別途 DL 不要)

## 10. HL7 Terminology / FHIR Core

- 公式サイト: https://hl7.org/fhir/
- ライセンス: **HL7 Terms of Use** (相互運用性のためのライセンス、無料、明示的な帰属推奨)
- 商用利用: 可 (HL7 帰属表記要)
- `packages.fhir.org` から fhirserver 起動時に auto fetch

## サマリ表

| コンポーネント | ライセンス | 再配布 | 商用 | 本 repo に含む |
|---|---|:---:|:---:|:---:|
| このプロジェクトのコード | MIT | ✅ | ✅ | ✅ |
| fhirserver source | BSD-3-Clause | ✅ | ✅ | ❌ (patches のみ) |
| HAPI Validator | Apache-2.0 | ✅ | ✅ | ❌ (auto DL) |
| JP Core | CC0-1.0 | ✅ | ✅ | ❌ (setup script で DL) |
| JP-CLINS | CC0-1.0 | ✅ | ✅ | ❌ (setup script で DL) |
| jpfhir-terminology | CC0-1.0 | ✅ | ✅ | ❌ (setup script で DL) |
| LOINC | LOINC License | ✅ | ✅ | ❌ (要 user 登録) |
| SNOMED CT International | UMLS License | ❌ (個人) | ❌ (個人) | ❌ (**絶対に含めない**) |
| UCUM | UCUM License | ✅ | ✅ | ❌ (jpfhir-terminology 内) |
| HL7 Terminology | HL7 Terms of Use | ✅ | ✅ | ❌ (auto DL) |

## トラブル対応

### UMLS ライセンス申請が承認されない

- 個人の場合、申請理由に「FHIR JP Core / JP-CLINS 準拠性検証」等の学術/技術的な用途を明記
- 商用検討の場合、Affiliate 契約に切り替え (SNOMED International 経由)

### AWS 等クラウドでの利用

- **個人 UMLS ライセンスでは SNOMED を含む image を AWS EC2 に置いてはいけません** (用途 A 違反)
- 対応:
  - SNOMED 抜きの構成で運用 (LOINC + JP terminology だけでも大半の validation は可能)
  - Affiliate 契約に切り替え (法人)
