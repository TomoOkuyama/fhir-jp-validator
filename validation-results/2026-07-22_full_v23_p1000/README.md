# 2026-07-22 v23 — clinosim PR #370/#371/#372 + #368

## 位置付け

v22 で発掘した display mismatch 2 種 (FMH RoleCode / DocRef LOINC) への直接 fix + Phase 2
refactor (antibiotic MR opaque id) の検証。v15 / v19 / v22 と同 seed=300 で 4 世代 A/B 可能。

| PR | 内容 | 期待効果 |
|---:|---|---|
| #370 | FMH.relationship NSIB canonical = `natural sibling` | v22 の 456 errors 解消 |
| #371 | DocRef LOINC 11506-3 canonical = `Provider-unspecified Progress note` | v22 の 2,513 errors 解消 |
| #372 | FMH.relationship MTH/FTH = `natural mother` / `natural father` | v22 は 0 error だったが future-proof + sibling-sweep alignment |
| #368 | Phase 2: antibiotic MR opaque id + `meta.tag[]` | spec-conformance 維持 (population run では発火なし) |

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- rest pass は `--include-file fhir_r4/Organization.ndjson`
- Data: 177,113 rest + 251,413 obs = **428,509 res** (合成、`clinosim` v0.2.0, `seed=300`,
  master `fea22929`, patients 3,795)

## Result

| pass | 件数 | 所要 | rps | error | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 177,096 (−17 sticky) | 12.0 min | 246 | **1,164** | 1,164 | 0.657% | **0** |
| obs (tx=n/a) | 251,413 | 17.6 min | 238 | **0** | 0 | 0.000% | **0** |
| **合計** | **428,509** | **29.6 min** | 241 | **1,164** | **1,164** | **0.272%** | **0** |

## v22 → v23 diff (期待は 2969 → 0、実測は 2969 → 1164)

| error pattern | v22 | v23 | 判定 |
|---|---:|---:|---|
| FMH NSIB display (`Sibling`) | 456 | **0** | ✅ #370 完全効果 |
| DocRef LOINC 11506-3 (`Progress note`) | 2,513 | **0** | ✅ #371 完全効果 |
| FMH MTH display (`natural mother`) | 0 | **582** | ⚠️ **#372 新 regression** |
| FMH FTH display (`natural father`) | 0 | **582** | ⚠️ **#372 新 regression** |

## 発掘 regression: PR #372 の MTH/FTH canonical 誤認

**現象**:
```
Wrong Display Name 'natural mother' for http://terminology.hl7.org/CodeSystem/v3-RoleCode#MTH.
Default display is 'mother'
```

同じく FTH: emit `natural father` vs canonical `mother`, canonical `father`.

**根本原因**: v3-RoleCode の naming convention は **code ごとに異なる**、`natural` prefix は
NSIB (sibling) にだけ付き、MTH/FTH には付かない。PR #372 は「NSIB を修正したから MTH/FTH も
同じ pattern だろう」と誤って類推した regression。

| v3-RoleCode code | canonical display |
|---|---|
| **MTH** (mother) | `mother` |
| **FTH** (father) | `father` |
| **NSIB** (natural sibling) | `natural sibling` |

**v22 での挙動 (参考)**: v22 は emit `Mother` / `Father` (case-insensitive)、これは canonical
`mother` / `father` と case-tolerant で match、0 error だった。**PR #372 で `natural`
prefix を追加した結果、strict comparison で不一致化**。

**fix 案** (generator-side):
- `natural mother` → `mother` (canonical そのまま)、`Mother` (v22 の case-tolerant 挙動を維持)、または display 省略
- 同じく FTH
- NSIB は v23 のまま (`natural sibling` が canonical で正しい)

## PR #370 / #371 は完全効果

- FMH NSIB: 456 → 0 (canonical `natural sibling` に整合)
- DocRef LOINC 11506-3: 2,513 → 0 (canonical `Provider-unspecified Progress note` に整合)

pre-verify で FMH.relationship の全 3 code (`natural mother` / `natural father` /
`natural sibling`) の distribution を確認。DocRef.type.coding の 11506-3 は 2,513 件全て
`Provider-unspecified Progress note` に更新済。

## #368 Phase 2 refactor は population run で発火せず

- MR max id length: 50 (opaque `mr-*` prefix 0 件)、`meta.tag[]` を持つ MR 0 件
- 全 MR は `ORD-*` 系 (通常の medication order)
- HAI 抗菌薬 MR は enumerate mode 系 (`ENC-FORCED-*`) でのみ発火するため、次 enumerate 検証時に
  効果測定要

## fail 率推移 (seed=300 系 全 5 世代)

| run | 主変更 | error | fail 率 | 状態 |
|---|---|---:|---:|---|
| v14 | cache poisoning | 26,238 | 3.04% | HAPI txCache 汚染中 |
| v14gen | + PR #342 profile 宣言 | 26,238 | 3.04% | timeouts 6→0、cache wipe 前 |
| v15 | + PR #344 sticky | 0 | 0.000% | 品質 perfect 到達 |
| v19 | + Issue #349 wave1 (#354/#356/#357) | 378 | 0.042% | FMH ICD-10 display 発掘 |
| v22 | + #358 + #360 wave (10 PR) | 2,969 | 0.693% | #358 効果 + 2 新 regression |
| **v23** | **+ #370/#371/#372/#368** | **1,164** | **0.272%** | 2 新 regression 解消 + 1 新 regression |

## 教訓

v3-RoleCode の canonical display は code ごとに独立、`natural` prefix pattern は普遍でない。
**Code-by-code の canonical 確認が必要**、類推による一括更新は regression リスクが高い。
walker-safe な UI 表示改善は `text` field 側で行い、`coding.display` は CodeSystem canonical に
**個別に整合** させるのが安全。

## 次 fix 見込み

PR #372 (MTH/FTH) を revert して canonical `mother` / `father` (or 省略) に戻せば
v24 で **1,164 → 0** 到達見込み。同 seed=300 系で fail 率 0.000% 再達成予想。

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
