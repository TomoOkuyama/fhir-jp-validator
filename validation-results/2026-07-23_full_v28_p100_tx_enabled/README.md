# 2026-07-23 v28 — clinosim wave2 (#385/#386/#387) tx=8181 full-set

## 位置付け

v27 の Pattern A residual 1,547 error に対する 2 PR fix (#385 80288-4 override + #386 追加
14 LOINC display) の検証。同 config で generator master のみ差替。

| PR | 内容 | 期待効果 |
|---:|---|---|
| #385 (Issue #384) | LOINC 80288-4 canonical を fhirserver-side に更新 + override_allowlist 追加 | -1,252 |
| #386 (Issue #380 follow-up) | 追加 14 LOINC display を LONG_COMMON_NAME に統一 (血液ガス 4 + 循環器 5 + 脂質糖感染 5) | -295 |
| #387 | `.test_durations` refresh (CI shard balance) | 検証には無影響 |

## Setup

- `validator_cli.jar` 6.9.12、`-tx http://localhost:8181/r4`
- 単一 pass、sticky × 4、`--chunk 30 --parallel 24 --timeout 300`
- Data: **35,062 res** (合成、seed=300, patients 434, master `007e255b`)

## Result

| 指標 | 値 |
|---|---:|
| 総 res | 35,062 (processed 34,810) |
| 所要 | 21.0 min |
| 平均 rps | 27.7 |
| **error 総数** | **4,695** |
| warning | 52,191 |
| information | 70,791 |
| HTTP failed | 0 |

## v27 → v28 diff (期待 -1,547 に対し実測 -289)

| 指標 | v27 | v28 | 差分 | 判定 |
|---|---:|---:|---:|---|
| error 総数 | 4,984 | 4,695 | **-289** | 期待 -1,547 の 19% のみ |
| Pattern A (LOINC display) | 1,547 | 1,258 | -289 | 部分効果 |
| Pattern B (JP_Patient_eCS) | 3,426 | 3,426 | ↔ | 期待通り (Issue #378 次 chain) |

## PR 別評価

### 🟡 PR #386 完全効果

v27 で残っていた 14 LOINC (2744-1/2019-8/2703-7/1963-8/10839-9/13969-1/17861-6/777-3/2524-7/
4548-4/1751-7/2571-8/2085-9/75241-0) の SHORTNAME 由来 error **295 → 0** (完全消滅)。

pre-verify で全 14 code が LONG_COMMON_NAME に更新済みを確認 (例: `2744-1: pH` →
`2744-1: pH of Arterial blood`)。

### ❌ PR #385 効果なし (実測)

**LOINC 80288-4 の error は 1,252 のまま v27/v28 で不変**。

原因分析:
- v28 data pre-verify で 80288-4 の emit は依然 `Level of consciousness AVPU` (short 形)
- clinosim 内部の "override_allowlist" は clinosim 側 sanity check の tolerance で、
  fhirserver validator の判定には影響しない
- fhirserver は canonical `Level of consciousness AVPU score` を strict 比較、依然 mismatch

**fix には data emit 側を実際に "Level of consciousness AVPU score" に変更する必要あり**
(override_allowlist だけでは validator 経由の error は消えない)。または LOINC display 省略。

### 新規発掘 pattern (小)

Pattern A に新規 6 code が 1 error ずつ出現 (v27 では 0 だった code):

| # | code | emit |
|---:|---|---|
| 1 | LOINC 14979-9 | `aPTT` |
| 1 | LOINC 48642-3 | `Estimated GFR` |
| 1 | LOINC 48065-7 | `D-dimer` |
| 1 | LOINC 3016-3 | `Thyroid-stimulating hormone` |
| 1 | LOINC 3255-7 | `Fibrinogen` |
| 1 | LOINC 2093-3 | `Total cholesterol` |

いずれも SHORTNAME emit、canonical は LONG_COMMON_NAME と推定。v28 で PR #386 が top 14 を
拡張したので、次点 code が visible になった (前は 14 top に埋もれて見えず、量が少ないため
今回発掘)。cumulative 6 error のみで優先度低いが、PR #386 の list 追加拡張時に併合可能。

## 残 4,695 error の分類

| category | 件数 | 状態 |
|---|---:|---|
| Pattern A residual: LOINC 80288-4 | 1,252 | PR #385 効果無し、data emit 側 fix 要 |
| Pattern A 新規: 6 code × 1 = 6 | 6 | 次点 SHORTNAME emit、PR #386 拡張候補 |
| Pattern B: JP_Patient_eCS 未 match | 3,426 | Issue #378 reopen (Patient data eCS 準拠実装) |
| Composition eReferral cross-bundle | 11 | 既知 client-side infra 制約 |
| その他 | ~0 | — |
| **計** | **4,695** | |

## fail res by rt (sticky 除外)

| rt | fail res | 総数 | fail 率 |
|---|---:|---:|---:|
| Observation | 3,775 | 20,035 | 18.8% |
| Condition | 736 | 736 | 100% (全て Pattern B) |
| MedicationRequest | 151 | ? | — |
| Composition | 11 | 490 | 2.2% |
| AllergyIntolerance | 5 | ? | — |

## 3 世代 A/B 総括

| run | error | 変化要因 |
|---|---:|---|
| v25 | 7,764 | tx=8181 full-set 初 baseline |
| v26 | 37,762 | #379 で cascade regression |
| v27 | 4,984 | #383 hotfix で cascade 解消 |
| **v28** | **4,695** | **#386 で 14 LOINC 解消 (-295)、#385 は効果なし** |

## 次 chain 推奨

1. **80288-4 の data emit 実修正** (short → full canonical or display 省略) → **-1,252** で
   Pattern A の 80% 消滅。次点は各 code 6 error 未満で優先度低い
2. **Issue #378 完全対応**: Patient data の eCS 準拠実装 (identifier slice / 拡張等の追加
   emit) → **-3,426** で Pattern B 完全解消
3. 両方適用で **v29 or v30 で error 数 <30** (Composition eReferral 11 + AllergyIntolerance 5 +
   新規 pattern 6 = 22) の Pattern A/B 完全解消到達見込み

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
