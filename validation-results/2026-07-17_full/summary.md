# 検証まとめ — 2026-07-17 (session 55 fix 適用後 fullset)

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 2026-07-17 生成 (JP p=1000 seed=300、PR-J branch `fix/fhir-id-spec-compliance` から regen)
- **fullset = 437,669 リソース / 26 種 / 589MB**
- Session 55 merged 7 PR + open 3 PR (#192/#197/#199) の fix 全て反映

## 分布

| 種別 | 件数 | 占有 |
|---|---:|---:|
| Observation | 262,835 | 60% |
| MedicationAdministration | 64,366 | 15% |
| ServiceRequest | 35,786 | 8% |
| Specimen | 31,047 | 7% |
| DocumentReference | 10,223 | 2% |
| Condition | 6,235 | 1% |
| 他 (Composition/Encounter/CareTeam 等 20 種) | 27,177 | 6% |

## 検証戦略

前回同様の分割:

| pass | 対象 | tx 設定 | HAPI_EXTRA_ARGS |
|---|---|---|---|
| rest | 25 種 (非 Observation) 174,834 | `-tx=http://localhost:8181/r4` | `-best-practice ignore -check-display Ignore` |
| obs | Observation 262,835 | `-tx=n/a` (構造/slice のみ) | `-best-practice ignore` |

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 174,834 | 7 分 25 秒 | 393 | 100% |
| obs | 262,835 | 17 分 57 秒 | 244 | 100% |
| **合計** | **437,669** | **25 分 22 秒** | **288** | **100%** |

- quarantined port: 両 pass ともゼロ
- rest 側 rps 393 は前回 307 の +28% (JIT warm state で fhirserver / HAPI 双方の cache 効果)
- Bundle 単位 timeout ゼロ、client リトライ発生ゼロ

**caveat**: 初回 run で **fhirserver が謎の 1500% CPU idle-spin 状態に陥り validation が 7 rps しか出なかった**。fhirserver container を restart することで解消 (原因未特定、Docker Desktop update + 数時間放置後の状態が疑わしい)。restart 後は上記の正常値。

## Issue 分布

| severity | rest | obs | 合計 |
|---|---:|---:|---:|
| error | 100,666 | 484,240 | **584,906** |
| warning | 296,392 | 194,032 | **490,424** |
| information | 182,527 | 404,526 | **587,053** |

**リソース単位 pass/fail**:
- rest: 174,834 中 ~35,110 (20.1%) に 1+ error
- obs: 262,835 中 183,305 (69.7%) に 1+ error
- **合計 437,669 中 218,415 (49.9%) に 1+ error**

## 種別ごと fail 率 (error あり率)

| 種別 | 検証数 | error あり | fail 率 | 前回比 |
|---|---:|---:|---:|---:|
| Observation | 262,835 | 183,305 | **69.7%** | 69.8% → 69.7% (↔) |
| Condition | 6,235 | 6,235 | **100%** | 100% (↔、#192 未 merge) |
| CareTeam | 3,781 | 3,781 | **100%** | 100% (↔、#179 fix 効果なし) |
| MedicationRequest | 1,870 | 1,870 | **100%** | 100% (↔、#197 未 merge) |
| Patient | 577 | 577 | **100%** | 100% (↔、example CS 別 issue) |
| AllergyIntolerance | 75 | 75 | **100%** | 100% (↔) |
| DiagnosticReport | 2,675 | 2,277 | 85.1% | ~86% (↔) |
| ImagingStudy | 753 | 562 | 74.6% | ~79% (↓) |
| MedicationAdministration | 64,366 | 19,131 | **29.7%** | ~100% → **-70pp** (#183 UCUM 大幅改善) |
| Practitioner | 100 | 10 | 10.0% | ~17% (↓) |
| Composition | 4,466 | 421 | 9.4% | ~9% (↔) |
| ServiceRequest | 35,786 | 131 | **0.4%** | ~8% → **-8pp** (#181 効いた) |
| Encounter | 3,892 | 36 | 0.9% | ~1% (↔) |
| Specimen | 31,047 | 0 | **0%** | new (#195 emit) |
| DocumentReference | 10,223 | 0 | 0% | – |
| Immunization | 2,959 | 0 | 0% | – |
| ClinicalImpression | 2,479 | 0 | 0% | – |
| FamilyMemberHistory | 1,605 | 0 | 0% | – |
| Endpoint / Coverage / Procedure / Location / Device / DeviceUseStatement / PractitionerRole / Organization | ~1,300 | ~4 | ほぼ 0% | – |

## 検出された主要 issue パターン (上位、実測 error 数)

詳細と対処は `generator-feedback.md` を参照。

### Observation (obs pass)

- Observation.category dual coding が profile と矛盾 (mismatch 双方向 + max=1 違反): 316,504
- Observation.identifier `resourceIdentifier` slice 欠落: 31,172
- Observation.referenceRange.extension URL 未知 + max=0 違反: 62,012 (旧 fix URL が反映後も未定義)
- Vital-signs BP profile 違反 (component 欠落): 43,422
- BP slice mismatch (bp profile の closed slice): ~4,200

### rest 側 (25 種)

- Condition eCS 必須要素の完全欠落 6 種 × 6,235: 37,410 (PR #192 で対処予定)
- MedicationRequest eCS 必須要素 5 種 × 1,870: 9,350 (PR #197 で対処予定)
- MedicationAdministration UCUM 特殊単位 (IU/mcg): 6,179
- CareTeam SNOMED 735320007 unknown: 3,781 (fhirserver に code 未収録)
- ICD-10-CM code S72.00 / E11.65 (WHO 版に無い): 7,652
- DiagnosticReport.category:first slice 欠落: 2,265

### validator noise (data 側の問題ではない)

- dom-6 Best Practice narrative missing: 349k warning (`-best-practice ignore` で抑止済)
- SNOMED/LOINC 日本語 display なし: info、対処不要
- `urn:oid:...1005` 未知 CodeSystem: 31k warning、対処不要
- `warn-localCode-observation-laboresult`: 31k warning、情報のみ

## caveat — 検証していないこと

- **Observation の LOINC / SNOMED terminology 検証**: 前回同様、性能上スキップ (fhirserver 日本語 display per-code ~700ms、26 万件を通せない)。構造/slice/invariant のみ
- **業務ロジック**: 診療報酬点数、レセプト整合、医療的妥当性は対象外
- **Bundle Type validation**: client が `collection` 化するため `transaction`/`document` の制約は非対象

## raw ファイル

- `raw/rest.meta.json` — rest pass のメタ (commit 対象)
- `raw/obs.meta.json` — obs pass のメタ (commit 対象)
- `raw/rest.stdout.log` — rest pass の実行ログ (commit 対象、~10KB)
- `raw/obs.stdout.log` — obs pass の実行ログ (commit 対象、~10KB)
- `raw/rest.ndjson` — 全 OperationOutcome (~803 MB、gitignore)
- `raw/obs.ndjson` — 同上 (~2.6 GB 推定、gitignore)

## 次サイクルの見込み

`generator-feedback.md` の最優先 1-7 対処で予想 fail 率:

- 現状: 49.9%
- #190 dual category 修正 + #185 extension URL 修正 + #179 SNOMED 差替 + #192/#197 merge + UCUM マッピング → **~25%**
- + ICD-10 版統一 + BP profile 準拠 + 例 URL 除去 + DR slice → **~15%**

`generator-feedback.md` を clinosim チームに送付済み想定。
