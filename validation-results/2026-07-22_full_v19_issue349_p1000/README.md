# 2026-07-22 v19 — clinosim Issue #349 Phase 1a/1b/3-Z wave

## 位置付け

Issue #349 (architectural refactor) の第 1 wave 3 PR merge 後の population 検証。
v15 (2026-07-21) と同 seed=300 のため直接 A/B 可能。

| PR | Phase | 効果 |
|---:|---|---|
| #354 | 1a foundation | opaque_ids helper module 追加 (byte-diff なし) |
| #356 | 3-Z invariant test | 全 Resource.id を FHIR R4 spec `[A-Za-z0-9\-\.]{1,64}` に対して assert (regression guard) |
| #357 | 1b antibiotic MR | 抗菌薬 MR.id を compound → opaque `mr-{sha256[:12]}` (15 chars 固定) に切替、structural key は `identifier[]` に round-trip 保存 |

**注意**: PR #357 の効果は population run (p=1000 seed=300) では観測不能 (HAI 抗菌薬 MR は
enumerate mode の `ENC-FORCED-*` 系でのみ発火。この run の MR は全て `ORD-*` 系で opaque
`mr-*` 0 件、`medication-request-key` identifier 0 件)。#354/#356 の regression 有無を主目的に測定。

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- rest pass は `--include-file fhir_r4/Organization.ndjson`
- Data: 177,113 rest + 251,413 obs = **428,509 res** (合成、`clinosim` v0.2.0, `seed=300`,
  master `39ae1b7f`, patients 3,795)

## Result

| pass | 件数 | 所要 | rps | error | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 177,096 (−17 sticky) | 7.2 min | 413 | **378** | 182 | 0.103% | **0** |
| obs (tx=n/a) | 251,413 | 16.1 min | 260 | **0** | 0 | 0.000% | **0** |
| **合計** | **428,509** | **23.3 min** | 306 | **378** | **182** | **0.042%** | **0** |

## v15 → v19 diff (同 seed=300 A/B)

| 指標 | v15 (baseline) | v19 (3 PR 適用) | 変化 |
|---|---:|---:|---|
| rest error | 0 | 378 | **+378 (regression)** |
| obs error | 0 | 0 | ↔ |
| timeouts | 0 | 0 | ↔ |
| rest 所要 | 7.3 min | 7.2 min | ↔ |

## 発掘された regression: FamilyMemberHistory display mismatch (378 errors, all rest)

**現象**: `FamilyMemberHistory.condition.code.coding[]` の MHLW ICD-10 display が canonical と
不一致。全 error が FMH に集中 (**182 / 1620 FMH = 11.2% fail rate**)。

**data 実態**: FMH.condition.code に **2 coding emit** されている:

```json
{
  "coding": [
    {"system": "http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full",
     "code": "C34", "display": "気管支および肺の悪性新生物"},
    {"system": "http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full",
     "code": "C34", "display": "Malignant neoplasm of bronchus and lung"}
  ]
}
```

**8 unique mismatches × 各 ~47 患者** で 378 error。全て C-series (がん) code:

| code | emit (JA / EN) | MHLW canonical | 差 |
|---|---|---|---|
| C34 | 気管支**および**肺の悪性新生物 | 気管支**及び**肺の悪性新生物**＜腫瘍＞** | 「および」→「及び」、`＜腫瘍＞` suffix 欠落 |
| C34 | Malignant neoplasm of bronchus and lung | (同上、Japanese only) | 英語 display 自体無効 |
| C61 | 前立腺の悪性新生物 | 前立腺の悪性新生物**＜腫瘍＞** | `＜腫瘍＞` suffix 欠落 |
| C61 | Malignant neoplasm of prostate | (同上) | 英語 display 無効 |
| C18 | 結腸の悪性新生物 | 結腸の悪性新生物**＜腫瘍＞** | 同 |
| C18 | Malignant neoplasm of colon | (同上) | 同 |
| C50 | 乳房の悪性新生物 | 乳房の悪性新生物**＜腫瘍＞** | 同 |
| C50 | Malignant neoplasm of breast | (同上) | 同 |

**なぜ v15 で発生しなかったか**: v15 は system URI が WHO ICD-10 (`http://hl7.org/fhir/sid/icd-10`)
だった。WHO CS は fragment 内 code に緩やかな display tolerance を持つ、または display 不一致が
warning 止まり。PR #353 (v18) で URI を MHLW に切替後、MHLW canonical display との strict 比較が
発火。**PR #353 の後続 fix が FMH data に必要**。

**generator-side fix 案** (2 段):

1. **英語 display の削除**: MHLW ICD-10 は Japanese-only CS。coding[1] (英語) を emit しない
   (もしくは system を別 URI に、例: patient-facing 用途なら `Coding.text` に入れる)
2. **日本語 display を canonical に整合**:
   - `＜腫瘍＞` suffix を C-series (悪性新生物 系) code で必ず付与
   - 表記統一: `および` → `及び` (MHLW 表記に合わせる)
   - 安全策として `display` field を省略 (display 検証はスキップされる)

**影響範囲**: この run では 8 unique code のみ。実際の MHLW ICD-10 で `＜...＞` suffix が付く
code は他にも多数 (悪性新生物、良性新生物、上皮内新生物 等の C/D 系)。generator が使う ICD-10
code table の display source を MHLW canonical に統一する対処が本質。

## Issue #349 wave の regression 有無

- **#354 (opaque_ids helper)**: byte-diff なし、regression 無し (期待通り)
- **#356 (invariant test)**: 全 MR id ≤ 50 chars、上限 64 制約に余裕。generator 側 assert が
  validator 到達前に catch する運用が回れば validator の id-length error は今後恒久的に 0
- **#357 (antibiotic MR opaque id)**: 本 run では発火せず (population で HAI 抗菌薬 MR が
  生成されない)。enumerate mode 系 (v20 想定) で効果測定要

## v14 - v19 fail 率推移 (population run のみ抜粋)

| run | data | error | fail 率 |
|---|---|---:|---:|
| v14 (cache wipe) | p=1000 s=300 | 26,238 | 3.04% |
| v15 (+ PR #344 sticky) | p=1000 s=300 | 0 | **0.000%** |
| v16 (seed 変更) | p=1000 s=700 | 1 | 0.000265% |
| **v19 (Issue #349 wave1)** | p=1000 s=300 | **378** | **0.042%** |

v15 → v19 の regression は Issue #349 wave 起因ではなく、間に merge された **PR #353
(WHO → MHLW ICD-10 URI 切替) の後続 display 整合作業が未着手** だったため。

## 参考: fhir-jp-validator 側の中期対応 (docs/hapi-txcache-poisoning.md 系)

現在 fhirserver が load する MHLW ICD-10 CS は `content: fragment` (2,000/14,877 concept)。
generator 側 display fix と併せて、fhirserver 側で MHLW 完全 CS を load すれば残 warning
152k 弱も減らせる (未着手、中期候補)。

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
