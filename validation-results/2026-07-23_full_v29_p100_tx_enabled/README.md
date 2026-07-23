# 2026-07-23 v29 — clinosim PR #388 (LOINC 80288-4 emit 修正試み) tx=8181 full-set

## 位置付け

v28 の Pattern A residual 1,258 のうち LOINC 80288-4 (1,252 errors) の hardcoded emit を canonical と
思われる `Level of consciousness AVPU score` に修正 (`_fhir_observations.py:626`) した検証。
v25/v27/v28/v29 の 4 世代 A/B (seed=300 固定)。

| PR | 内容 | 期待効果 |
|---:|---|---|
| #388 (Issue #384 hotfix follow-up) | LOINC 80288-4 hardcoded emit を `Level of consciousness AVPU` → `Level of consciousness AVPU score` に実修正 (v28 では #385 が override_allowlist 更新のみで無効判明への follow-up) | -1,252 (期待) |

## Setup

- `validator_cli.jar` 6.9.12、`-tx http://localhost:8181/r4`
- 単一 pass、sticky × 4、`--chunk 30 --parallel 24 --timeout 300`
- Data: **35,062 res** (合成、seed=300, patients 434, master `0ef6edcf`)

## Result

| 指標 | 値 |
|---|---:|
| 総 res | 35,062 (processed 34,810) |
| 所要 | **19.3 min** (v28 21.0 → -1.7 min、fhirserver 効率向上) |
| 平均 rps | **30.0** |
| **error 総数** | **4,695** (v28 と完全同数、期待 -1,252 に届かず) |
| warning | 52,191 |
| information | 70,791 |
| HTTP failed | 0 |

## v28 → v29 diff (期待 -1,252、実測 ±0)

| 指標 | v28 | v29 | 差分 |
|---|---:|---:|---|
| error 総数 | 4,695 | 4,695 | **±0 (⚠️ PR #388 効果なし)** |
| Pattern A total | 1,258 | 1,258 | ±0 |
| LOINC 80288-4 | 1,252 | 1,252 | **±0 (emit 変更したのに error 同数)** |
| Pattern B (JP_Patient_eCS) | 3,426 | 3,437 | +11 (誤差) |
| 所要時間 | 21.0 min | 19.3 min | -1.7 min (rps +8%) |

## 真因判明: fhirserver の LOINC 80288-4 canonical 実測

fhirserver に直接 curl で問い合わせ + LOINC SQLite の Codes テーブル直接照会で判明:

```bash
$ curl "http://localhost:8181/r4/CodeSystem/$validate-code?url=http://loinc.org&code=80288-4&display=Level%20of%20consciousness%20AVPU%20score"
→ result: false
→ message: "Wrong Display Name 'Level of consciousness AVPU score' for http://loinc.org#80288-4.
   Default display is 'Level of consciousness'"

$ sqlite3 loinc-2.82.cache "SELECT Code, Description FROM Codes WHERE Code = '80288-4'"
→ 80288-4 | Level of consciousness
```

**fhirserver 側 canonical (LOINC 2.82 official)**:
- LOINC 80288-4 = `Level of consciousness` (シンプル、"AVPU" や "score" は付かない)

Session 65 の user 事前予想 `Level of consciousness AVPU score` (fhirserver-side canonical と
してのつもり) は **推定誤り**。実際の LOINC 2.82 canonical は `Level of consciousness` のみ。

**PR #388 は誤った canonical で emit を修正したため無効**。同様に PR #385 (override_allowlist) も
無効 (前 run で確認済)。

## 主要 LOINC code の実 canonical (fhirserver LOINC 2.82 実測)

参考 (PR #386 で修正済 code の canonical と、まだ問題ある code):

| code | fhirserver canonical | v29 emit | 判定 |
|---|---|---|---|
| 80288-4 | `Level of consciousness` | `Level of consciousness AVPU score` | ❌ mismatch |
| 8478-0 | `Mean blood pressure` | (v22-v25 で誤って 8478-0 に "Inhaled oxygen delivery system" emit、#377 で 107117-4 に code 変更済) | ✅ |
| 107117-4 | `Method of oxygen delivery` | `Method of oxygen delivery` (#377 で切替) | ✅ |
| 2160-0 | `Creatinine [Mass/volume] in Serum or Plasma` | `Creatinine [Mass/volume] in Serum or Plasma` (#386) | ✅ |
| 2951-2 | `Sodium [Moles/volume] in Serum or Plasma` | `Sodium [Moles/volume] in Serum or Plasma` (#386) | ✅ |

## 教訓 (v28-v29 で確立)

**canonical 修正の前に必ず fhirserver に実測で確認する**:

1. `curl "http://localhost:8181/r4/CodeSystem/$validate-code?url=http://loinc.org&code=<CODE>"` で
   fhirserver の返す `Default display` を直接確認
2. または SQLite 直接: `sqlite3 loinc-2.82.cache "SELECT Description FROM Codes WHERE Code='<CODE>'"`
3. 想像や推測での canonical 修正は無効化リスク

Session 65 で `Level of consciousness AVPU score` を canonical と想定したのは、user (clinosim
側) からの推測伝聞に基づく (fhirserver 独自 canonical と期待)。**実測で確認していれば PR #388
は無駄実装だった**。

## 残 4,695 error の内訳 (v28 と同構造)

| category | 件数 | 状態 |
|---|---:|---|
| LOINC 80288-4 mismatch | 1,252 | 未解消 (emit を `Level of consciousness` に再修正要) |
| Pattern A 新規 6 code | 6 | SHORTNAME 系、#386 拡張候補 |
| Pattern B (JP_Patient_eCS) | 3,437 | Issue #378 次 chain |
| Composition eReferral | 11 | client-side infra |
| その他 | ~0 | — |
| **計** | **4,695** | |

## seed=300 系 全 8 世代 (v14 → v29) 総括

| run | error | 変化要因 |
|---|---:|---|
| v14 | 26,238 | cache poisoning + 未 fix |
| v15 | 0 | (rest only tx=n/a、当時) |
| v19 | 378 | FMH ICD-10 display 発掘 |
| v22 | 2,969 | display regression 2 種発掘 |
| v23 | 1,164 | MTH/FTH regression |
| v24 | 0 | (rest only tx=n/a) |
| v25 | 7,764 | tx=8181 full-set 初 baseline |
| v26 | 37,762 | #379 cascade regression |
| v27 | 4,984 | #383 revert、v25 を下回る |
| v28 | 4,695 | #386 14 LOINC 修正 |
| **v29** | **4,695** | **#388 誤 canonical で無効** |

**v28-v29 の停滞** を打破するには:
1. LOINC 80288-4 emit を **正しい canonical `Level of consciousness` に再修正** (-1,252 見込み)
2. Issue #378 完全対応 (Patient data の eCS 準拠実装) (-3,437 見込み)
3. → v30 or v31 で **error 数 <20** (Composition eReferral 11 + Pattern A 新規 6 + 少数残)
   到達見込み

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
- `raw/all.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json`
