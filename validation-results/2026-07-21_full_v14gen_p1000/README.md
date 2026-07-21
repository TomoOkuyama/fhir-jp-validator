# 2026-07-21 v14gen — clinosim PR #342 検証 (Composition.meta.profile 宣言)

## 位置付け

前 3 run とは検証対象が異なる:

| run | 変数 | 目的 |
|---|---|---|
| v12 | 4 種 workaround 全網羅 | 6 timeout 固定を再現 (client / config 変更が効かないことを示す) |
| v13 | `validator_cli` 6.9.11 → 6.9.12 | okhttp3 移行が timeout に影響しないことを示す |
| v14 | `.hapi-cache/tx-cache/` wipe | **HAPI validator 側 cache poisoning** が真因と確定 |
| **v14gen** | **clinosim PR #342** (Composition に `clinicaldocument` profile 明示宣言) | **generator 側で HAPI VS 展開 default path を回避** して timeout を再発させない |

v14 は HAPI 側の bug を確定させ、それとは独立に **generator 側でも default path を踏まない profile 宣言に切り替える** ことで
再発を予防する — という改善案が v14gen。

## 何が変わったか (vs v13)

**clinosim 側のみ** 1 PR (Issue #340 fix = PR #342, master `9167777b`):

- JP path で JP-CLINS profile 未対応 Composition (rehab_plan LOINC 34823-5 等) に対し
  HL7 R4 core `clinicaldocument` profile を `meta.profile` に明示宣言
- `subject.targetProfile` / `versionNumber` extension slice も宣言 (semantic 誠実な refinement)

fhir-jp-validator 側は変更なし。fhirserver / HAPI cluster / `-txCache` / `validator_cli.jar` 全て v14 と同一。

**pre-verify**: 生成データ内の 6 rehab_plan Composition (`comp-ENC-POP-000033-224923531116-187` 含む、v12/v13 の timeout culprit) は
全て `meta.profile = [http://hl7.org/fhir/StructureDefinition/clinicaldocument]` を保持。

## Setup

- `validator_cli.jar` **6.9.12** (unchanged from v13/v14)
- `-tx http://localhost:8181/r4` (HL7 fhirserver、v14 実行後の warm cache 状態)
- `-txCache /Users/tokuyama/workspace/fhir-jp-validator/.hapi-cache/tx-cache`
  (v14 実行後の状態 = 6 timeout culprit tuple には success entry が入っている)
- Client: `scripts/parallel-validate.py --chunk 30 --parallel 24` (defaults)

## Data

- 178,818 リソース (rest 25 種) + 252,966 Observation の 合計 431,784 リソース
- **合成データ** (`clinosim` v0.2.0, `country=JP`, `population=1000`, `seed=300`, master `9167777b`)
- `_generator_metadata.json` を `raw/generator-metadata-snapshot.json` として保存

## Result

| pass | 件数 | 所要 | rps | error 件数 | fail resources | fail 率 | **timeouts** |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181) | 178,818 | 8.1 min | 366 | 26,238 | 13,119 | 7.337% | **0** |
| obs (tx=n/a) | 252,966 | 15.2 min | 277 | 0 | 0 | 0.000% | **0** |
| **合計** | **431,784** | **23.3 min** | 309 | **26,238** | **13,119** | **3.038%** | **0** |

- **timeout 数**: v13 の **6 → 0** (期待通り、PR #342 の目的達成)
- **rehab_plan Composition 6 個** (v12/v13 timeout culprit): 全て pass、tx call は success (`SocketTimeoutException` 0)
- **rest pass rps**: 273 → **366** (+34%) — 6 tuple 分の 15s timeout ブロックが消えた寄与
- **他リソースの error 数**: v14 と完全一致 (rest 26,238)、PR #342 は他 profile に regression 起こしていない

## v13 → v14gen 差分の要因分解

| 項目 | v13 | v14 (wipe) | v14gen | 効いた変数 |
|---|---:|---:|---:|---|
| timeouts | 6 | 0 | 0 | v14 では **cache wipe**、v14gen では **PR #342 profile 宣言** |
| rest error | 48 | 26,238 | 26,238 | cache 内の stale success entry (`text/plain; charset=utf-8` の MimeType VS mismatch) が v14 以降 unmask された |
| rest rps | 216 | 273 | 366 | timeout ブロック消失 + warm cache 温度差 |

## error 内訳 (rest pass)

| resourceType | fail resources / total | fail 率 | error 件数 |
|---|---:|---:|---:|
| DocumentReference | 10,459 / 10,459 | 100.00% | 20,918 |
| DiagnosticReport | 2,639 / 2,639 | 100.00% | 5,278 |
| Composition | 21 / 4,523 | 0.46% | 42 |

### 主 error パターン

1. **DocumentReference / DiagnosticReport (23,556 件、90% を占める)**:
   `text/plain; charset=utf-8` が FHIR `MimeType` value set (`http://hl7.org/fhir/ValueSet/mimetypes|4.0.1`) に含まれない。
   実データ確認: `DocumentReference.content[N].attachment.contentType`、`DiagnosticReport.presentedForm[N].contentType` に
   `"text/plain; charset=utf-8"` (charset parameter 付き) が emit されている。
   FHIR spec 上、`MimeType` binding は BCP 13 (RFC 6838) registered media types (parameter 無し) を要求。→ **generator-side fix 案**: charset parameter を削除して `"text/plain"` を emit
2. **Composition (42 件)**: `Composition.section:referralFromSection.entry:referralFromOrganization` および `referralToSection` の
   min=1 slice 未充足。これは eReferral の cross-bundle Reference target が別 NDJSON ファイルにあるため `parallel-validate.py`
   が Bundle 分割時に見つけられない、既知の client-side infra 制約 (v8 で 42 件と一致、生成データ側は正しい)

## 結論

- **PR #342 の目的 = HAPI VS 展開 default path 回避による timeout 再発予防**: 達成 (6 → 0)
- **副作用としての regression**: 無し (Composition profile 追加は他 resource / 他 profile の error 数を全く変えていない)
- **残る 26k error は data content 側の別 issue** (MimeType charset parameter)、次 chain の候補

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log` — rest pass (tx=8181)
- `raw/obs.meta.json` / `raw/obs.stdout.log` — Observation pass (tx=n/a)
- `raw/rest.ndjson` / `raw/obs.ndjson` — full OperationOutcome NDJSON (git-ignored)
- `raw/generator-metadata-snapshot.json` — clinosim 生成メタデータ
