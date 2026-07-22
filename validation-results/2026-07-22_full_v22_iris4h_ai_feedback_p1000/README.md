# 2026-07-22 v22 — clinosim Issue #349 wave1 + Issue #358 + Issue #360 全 10 PR

## 位置付け

v19 (Issue #349 wave1 単独) の FMH regression 修正 (#358) と、iris4h-ai 2026-07-22 feedback
7 items (#360) を反映した population 検証。v15 / v19 と同 seed=300 で 3 世代 A/B 可能。

| Issue | PR | 内容 |
|---|---:|---|
| #349 (wave1) | #354/#356/#357 | opaque_ids helper / MR id 上限 assert / antibiotic MR opaque id |
| #358 | #359 | FMH の MHLW ICD-10 display を canonical 整合 (v19 の 378 error 対処) |
| #360 G2 | #361 | FMH.relationship = EN coding + JP text (walker-safe) |
| #360 G4 | #362 | ClinicalImpression.description = JP template |
| #360 G6 | #363 | Procedure.code.text supportive-care = JP category prefix |
| #360 G5 | #364 | DocumentReference.type = EN LOINC display + JP text + LOINC 34133-9 追加 |
| #360 G3 | #365 | Composition.section.title = 46 slug JP localization |
| #360 G1 | #366 | Encounter.reasonCode.text = `chief_complaint_ja` fallback |
| #360 G7 | #367 | 未成年 occupation = 発達段階別ラベル |

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- rest pass は `--include-file fhir_r4/Organization.ndjson`
- Data: 177,113 rest + 251,413 obs = **428,509 res** (合成、`clinosim` v0.2.0, `seed=300`,
  master `ceb8a9e7`, patients 3,795)

## Result

| pass | 件数 | 所要 | rps | error | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 177,096 (−17 sticky) | 9.4 min | 314 | **2,969** | 2,969 | 1.677% | **0** |
| obs (tx=n/a) | 251,413 | 16.8 min | 249 | **0** | 0 | 0.000% | **0** |
| **合計** | **428,509** | **26.2 min** | 273 | **2,969** | **2,969** | **0.693%** | **0** |

## 3 世代比較 (同 seed=300)

| 指標 | v15 | v19 (+ Issue#349 wave1) | v22 (+ #358 + #360) |
|---|---:|---:|---:|
| rest error 総数 | 0 | 378 | **2,969** |
| FMH ICD-10 display | 0 | 378 | **0** ✅ (#358 効果) |
| FMH RoleCode display | 0 | 0 | **456** ⚠️ (#361 新 regression) |
| DocRef LOINC display | 0 | 0 | **2,513** ⚠️ (#364 新 regression) |
| fail 率 | 0.000% | 0.042% | **0.693%** |

## #358 効果確認 (期待通り)

v19 の 378 FMH ICD-10 mismatch (`＜腫瘍＞` 欠落、`および` vs `及び` 表記差、英語 display) が
**完全消滅**。pre-verify で MHLW canonical (`＜腫瘍＞` 付き C-series) 189 件、non-tumor 2568 件
の正しい display emit を確認済。

## 新規発掘 regression 2 種 (#361 G2 と #364 G5)

両者とも共通パターン: **canonical display 名の短縮 label emit → validator が strict 比較で mismatch 判定**。
`-check-display Ignore` は display そのものの言語 check には効くが、CodeSystem の canonical
display との alignment mismatch は別 rule でエラー化される (fhirserver 側判定を HAPI が受領)。

### #361 (G2) FamilyMemberHistory.relationship: 456 errors (456/1620 = 28.1% fail)

**現象**:
```
Wrong Display Name 'Sibling' for http://terminology.hl7.org/CodeSystem/v3-RoleCode#NSIB.
Default display is 'natural sibling'
```

**data 実態**: PR #361 は walker-safe な EN coding + JP text の pair を作った。
`coding.display = "Sibling"` (短縮形) だが、v3-RoleCode の canonical display は
`natural sibling` (LOINC/HL7 spec 準拠)。同様に `Mother` / `Father` も canonical は
`natural mother` / `natural father`。

**fix 案**:
- `coding.display` を canonical (`natural mother` / `natural father` / `natural sibling`) に
  切替
- または `coding.display` を省略 (省略された display は canonical でカバーされる)
- JP text は `text` field のみで維持 (walker-safe な UI 表示は既に確保)

### #364 (G5) DocumentReference.type LOINC 34133-9: 2,513 errors (2513/10370 = 24.2% fail)

**現象**:
```
Wrong Display Name 'Progress note' for http://loinc.org#34133-9.
Valid display is 'Provider-unspecified Progress note' (for the language(s) 'ja')
```

**data 実態**: PR #364 は LOINC 34133-9 (progress note) を追加、display を短縮形
`Progress note` で emit。LOINC canonical display は `Provider-unspecified Progress note`
(fhirserver に load されている LOINC 2.82 版で確認)。

**fix 案**:
- `Progress note` → `Provider-unspecified Progress note` (LOINC canonical)
- LOINC 短縮名 (SHORTNAME) column を使うなら `Provider unspec Progress note` 等の別 canonical
- 安全策として display 省略

## #360 の残 5 items は regression なし (population run では)

- #362 G4 (ClinicalImpression.description JP): 検証時 warning/info のみで error 化せず
- #363 G6 (Procedure.code.text supportive-care JP prefix): text 側なので validator 判定対象外
- #365 G3 (Composition.section.title JP): pre-verify で全 section 日本語化を確認、error 増なし
- #366 G1 (Encounter.reasonCode.text JP): text 側なので validator 判定対象外
- #367 G7 (未成年 occupation): validator 判定対象外 (data quality 改善)

## Issue #349 wave1 の再確認 (population run では発火なし、regression なし)

- #354 opaque_ids helper: byte-diff なし
- #356 invariant test: 全 MR id ≤ 50 chars で余裕、regression なし
- #357 antibiotic MR opaque id: population run で HAI 抗菌薬 MR 未生成、発火せず

## fail 率推移 (population run seed=300 系)

| run | 主変更 | fail 率 | 教訓 |
|---|---|---:|---|
| v14 | cache poisoning 状態 | 3.04% | HAPI txCache 汚染 |
| v14gen | + PR #342 profile 宣言 | 3.04% | timeouts 6→0、data error は data 側 |
| v15 | + PR #344 sticky | 0.000% | data 品質 perfect 到達 |
| v16 | seed=700 | 0.000265% | cross-seed で 1 rare pattern |
| v19 | + Issue #349 wave1 | 0.042% | PR #353 未着手の FMH ICD-10 display 発掘 |
| **v22** | **+ #358 + #360** | **0.693%** | #358 は完全効果、#360 で 2 新 regression |

**教訓**: display 短縮 label は CodeSystem の canonical と strict 比較されるため regression
リスクが高い。walker-safe 改善は `text` field で行い、`coding.display` は canonical 準拠を
保つのが安全。

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
