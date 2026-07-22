# 2026-07-23 v24 — clinosim PR #375 hotfix (MTH/FTH canonical revert)

## 位置付け

v23 で発掘した MTH/FTH regression (1,164 errors) への直接 hotfix。v15/v19/v22/v23 と同
seed=300 で 5 世代 A/B、**v15 水準 (fail 率 0.000%) 復帰** を検証。

| PR | 内容 |
|---:|---|
| #375 | v3-RoleCode MTH/FTH の `coding.display` を `natural mother` / `natural father` → **`mother` / `father`** (canonical、strict-legal) |

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- rest pass は `--include-file fhir_r4/Organization.ndjson`
- Data: 177,499 rest + 252,061 obs = **429,543 res** (合成、`clinosim` v0.2.0, `seed=300`,
  master `3d173857`, patients 3,797)

## Result

| pass | 件数 | 所要 | rps | error | warning | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 177,482 (−17 sticky) | 8.4 min | 350 | **0** | 365,755 | **0.000%** | **0** |
| obs (tx=n/a) | 252,061 | 15.1 min | 279 | **0** | 217,692 | **0.000%** | **0** |
| **合計** | **429,543** | **23.5 min** | 305 | **0** | 583,447 | **0.000%** | **0** |

## v23 → v24 A/B (完全解消)

| 指標 | v23 | v24 | 効果 |
|---|---:|---:|---|
| rest error | 1,164 | **0** | **-100% ✅** |
| FMH MTH `natural mother` | 582 | 0 | PR #375 で `mother` に revert |
| FMH FTH `natural father` | 582 | 0 | PR #375 で `father` に revert |
| FMH NSIB `natural sibling` | 0 | 0 | 維持 (canonical で正しい) |
| DocRef LOINC 11506-3 | 0 | 0 | 維持 (canonical) |
| fail 率 | 0.272% | **0.000%** | 完全 clean |
| timeouts | 0 | 0 | ↔ |

## seed=300 系 7 世代総括 (v14 → v24)

| run | 主変更 | error | fail 率 | 状態 |
|---|---|---:|---:|---|
| v14 | cache poisoning 状態 | 26,238 | 3.04% | HAPI txCache 汚染 |
| v14gen | + PR #342 profile 宣言 | 26,238 | 3.04% | timeouts 6→0、cache wipe 前 |
| v15 | + PR #344 sticky | 0 | **0.000%** | 品質 perfect 到達 |
| v19 | + Issue #349 wave1 | 378 | 0.042% | FMH ICD-10 display 発掘 |
| v22 | + #358 + #360 wave | 2,969 | 0.693% | #358 効果 + 2 display regression |
| v23 | + #370/#371/#372 | 1,164 | 0.272% | 2 regression 解消 + #372 で MTH/FTH 新 regression |
| **v24** | **+ #375 hotfix** | **0** | **0.000%** | **v15 水準完全復帰** |

## 教訓 (2 セッションで確立)

1. **canonical display は code ごと独立**、pattern の類推による一括更新は regression リスク。
   v3-RoleCode で `natural` prefix があるのは NSIB のみ、MTH/FTH には無い。
2. **walker-safe な UI 表示改善は `text` field で完結**、`coding.display` は CodeSystem
   canonical に **code-by-code で個別整合** させるのが安全。
3. **hotfix cycle は短い** — v23 発掘 → PR #375 → v24 で 1,164 → 0 到達を 1 日以内で回した実例。

## 残 warning の内訳 (総計 583k、いずれも設計通り)

- rest 365k: MHLW ICD-10 fragment CS 未収録 code (~152k)、`dom-6` 推奨 narrative 欠落、
  HOT7 medication master fragment、`urn:oid:` 系日本の医療機関 OID 未収録等
- obs 217k: `dom-6` narrative 主体、Observation 拡張の情報 issue

いずれも **error 化しない** (`result: true` + warning の設計)。運用上の意思決定次第で
中期対応 (MHLW ICD-10 完全 CS の fhirserver load 等) が可能。

## #368 Phase 2 (opaque MR id + meta.tag) は本 run で発火せず

population run では HAI 抗菌薬 MR が生成されないため、enumerate mode 系 (次回) で効果測定要。

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
