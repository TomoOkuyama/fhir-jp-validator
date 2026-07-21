# 2026-07-22 v18 — clinosim enumerate mode + PR #348/#352/#353 適用

## 位置付け

v17 (enumerate 初回) で発掘された 3 pattern に対する 3 PR fix の直接検証。同 config
(enumerate L3、seed=42、802 patients) を保ち generator master のみ差替 → v17 との A/B 比較。

| run | master | fix 差分 (v17 比) |
|---|---|---|
| v17 | `cae630be` | (baseline、431 error) |
| **v18** | **`a9813247`** | **PR #348 (MR id length)** + **PR #352 (Patient.name populate)** + **PR #353 (JP ICD-10 URI switch)** |

## Setup

- `validator_cli.jar` 6.9.12
- `-tx http://localhost:8181/r4` (fhirserver、warm cache)
- rest pass は `--include-file fhir_r4/Organization.ndjson`
- Data: 345,497 rest + 511,003 obs = **856,500 res** (enumerate、`clinosim` v0.2.0, `seed=42`,
  master `a9813247`, patients 802)

## Result

| pass | 件数 | 所要 | rps | error | warning | fail resources | fail 率 | timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rest (tx=8181, +sticky) | 345,495 (−17 sticky) | 11.6 min | 497 | **0** | 786,054 | 0 | **0.000%** | **0** |
| obs (tx=n/a) | 511,003 | 40.8 min | 208 | **0** | 275,329 | 0 | **0.000%** | **0** |
| **合計** | **856,498** | **52.4 min** | 272 | **0** | 1,061,383 | **0** | **0.000%** | **0** |

## v17 → v18 diff (完全 A/B)

| 指標 | v17 (baseline) | v18 (3 PR 適用) | 変化 |
|---|---:|---:|---|
| **error** | **431** | **0** | **-100% (完全消滅)** |
| Patient.name empty | 416 | 0 | -100% (PR #352 効果) |
| ICD-10 unknown code (S67.2 等) | 14 | 0 (error) | -100% (PR #353 効果、warning に降格) |
| MR id > 64 chars | 1 | 0 | -100% (PR #348 効果) |
| timeouts | 0 | 0 | ↔ |
| rest 所要 | 11.5 min | 11.6 min | ↔ (regression 無し) |
| obs 所要 | 38.2 min | 40.8 min | +2.6 min (誤差範囲、fresh cluster 個体差) |
| warning 総数 | 633,544 | 786,054 | +152,510 (MHLW fragment CS 由来、後述) |

**3 PR 全効果確認、regression 皆無、fail 率 0.000% 達成**。

## warning 増分 152,510 件の内訳 (MHLW ICD-10 fragment CS)

PR #353 で generator が ICD-10 の system URI を切替:
- 旧: `http://hl7.org/fhir/sid/icd-10` (WHO)
- 新: `http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full` (MHLW 厚労省 2013 版)

JP Core `jp-condition-diagnosis` の `Condition.code.coding:icd10` slice の required binding
(`http://jpfhir.jp/fhir/core/mhlw/ValueSet/ICD10-2013-full`) に conformant となり、v17 の
14 件 error は解消。

一方 **fhirserver に load されている MHLW CS は `content: fragment` (14,877 concept 中 2,000
のみ収録)** のため、fragment 外の code (12,877 の可能性) は:

```
system 'http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full' で未知のコード 'W19'
- CodeSystem は断片としてラベル付けされているため、
  そのコードは他の断片では有効である可能性があります
```

を **warning で通過** (`$validate-code` は `result: true`、severity `warning`)。事前実測で
確認した挙動通り。v18 rest では 152,614 件のこの warning を検出:

| category (実測 code prefix 別、上位) | 件数 |
|---|---:|
| J系 (呼吸器) | 32,847 |
| K系 (消化器) | 26,309 |
| I系 (循環器) | 23,136 |
| S系 (損傷) | 9,397 |
| M系 (筋骨格) | 6,078 |
| R系 (症状) | 5,441 |
| E系 (内分泌) | 4,803 |
| その他 W/T/L/N/O/G 等 | ~44k |

**すべて `result: true` 判定なので required binding 違反にはならず、error 化しない**。

## 中期対応の検討事項 (fhir-jp-validator 側)

fragment CS のため validation coverage は文字通り 2,000/14,877 = 13.5%。残 86.5% は
「validator が code の存在を確認できない状態」。実運用 quality を上げるには:

1. **厚労省 統計情報** https://www.mhlw.go.jp/toukei/sippei/ から疾病分類 CSV DL
2. CSV → FHIR CodeSystem (`content: complete`, 14,877 concept) 変換 script
   (`scripts/build-mhlw-icd10-full.py`)
3. fhirserver に `-cmd icd10-import` 追加 patch or IG 追加 load
4. `docs/terminology-setup.md` に完全版 setup 節追加
5. `docs/fhirserver-setup-for-beginners.md` にライセンス注意 (厚労省 CSV 再配布条件) 追記

現状は data 品質としては perfect (error 0)、warning 152k は「監査的な穴」ではあるが実運用の
妨げにはならないため、優先度は中。data 側の他改善が一巡してから着手が費用対効果高い。

## v14 - v18 fail 率推移

| run | mode | data | error | fail 率 |
|---|---|---|---:|---:|
| v14 (cache wipe) | population | p=1000 s=300 | 26,238 | 3.04% |
| v15 (+ PR #344, sticky) | population | p=1000 s=300 | 0 | **0.000%** |
| v16 (seed 変更) | population | p=1000 s=700 | 1 | 0.000265% |
| v17 (enumerate 初回) | enumerate | seed=42 802pt | 431 | 0.014% |
| **v18 (+ 3 PR fix)** | **enumerate** | **seed=42 802pt** | **0** | **0.000%** |

**enumerate mode の rare pattern 3 種を 24 時間以内に検出 → PR 化 → 消滅までを回せた**。
regression suite として generator CI に組み込む価値が改めて実証された。

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log`
- `raw/rest.ndjson` / `raw/obs.ndjson` (git-ignored)
- `raw/generator-metadata-snapshot.json` — clinosim 生成メタ
- `raw/enumeration_manifest.json` — patient_id → kind/scenario/severity/archetype 逆引き
