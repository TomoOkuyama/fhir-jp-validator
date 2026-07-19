# 検証まとめ — 2026-07-20 v6.1 (session 60 5 chain merge 後)

## 🎉 総評: judgment recovery 完全成功、v5 を超える実質完全準拠水準に到達

- **fail 率 v6 3.554% → v6.1 0.190% (-3.36pp)** — v6 regression から完全回復
- **v5 比: 0.692% → 0.190% (-0.502pp)** — v5 の目標水準を超過達成
- **error 総数 v6 17,642 → v6.1 1,247 (-93%)** — 過去最少
- **5 chain のうち 4 chain が期待通り完全解決**、残る 1 chain (#315) は方針変更が必要

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-20 04:59 JST、JP p=1000 seed=300、master e2835d02)
- **fullset = 431,783 リソース / 26 NDJSON / 620MB** (v6 426,301 → +5,482)
- session 60 merged 5 PR (#306/#308/#310/#312/#315) 反映済み

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 178,817 | 8 分 22 秒 | 356 | 100% |
| obs | 252,966 | 21 分 22 秒 | 197 | 100% |
| **合計** | **431,783** | **29 分 44 秒** | **242** | **100%** |

## Issue 分布 (v6 vs v6.1)

| severity | v6 total | v6.1 total | 変化 |
|---|---:|---:|---:|
| error | 17,642 | **1,247** | **-93%** ✅✅ |
| warning | 502,139 | 510,640 | +2% |
| information | 882,199 | 883,376 | ~0% |

**リソース単位 pass/fail** (1+ error あり)
- rest: 178,817 中 618 = **0.346%** (v6 8.499% → **-8.15pp**)
- obs: 252,966 中 201 = **0.079%** (v6 と同水準、Chain 対象外)
- **合計 431,783 中 819 = 0.190%** (v6 3.554% → **-3.36pp**、v5 0.692% → **-0.502pp**)

## Session 60 5 chain 実測結果サマリ

| PR | 対象 | 期待効果 | 実測 | 判定 |
|---:|---|---:|---|:---:|
| #306 | NOCODED slice display `'標準コードなし'` 固定 + text へ薬剤名 | -12,891 | **0 件** (完全消滅) | ✅✅✅ |
| #308 | JP timing.repeat periodUnit/period 削除、boundsDuration only | -3,532 | **0 件** (tim-2 も 0、UnitsOfTime も 0) | ✅✅✅ |
| #310 | eReferral Composition.event.code Array wrap + text 正規化 | -37 | **0 件** (event.code 構造誤り 15 と `他医療機関紹介` display 22 の両方消滅) | ✅✅ |
| #312 | MAR route SL entry authoritative Sublingual code 37839007 | -13 | **0 件** | ✅✅ |
| #315 | JP ImagingStudy.procedureCode text-only | -571 | **589 件残** (approach では required binding 制約を回避できず) | ❌ |

**期待合計 -17,044 → 実測 -16,395** (期待から -649 差、#315 分)。

## 種別ごと fail 率 (v6 比較)

| 種別 | 検証数 | error あり | v6.1 fail | v6 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| **MedicationAdministration** | 64,304 | **0** | **0%** | 19.4% | **-19.4pp** ✅✅✅ (Ch306 完全解決) |
| **MedicationRequest** | 2,034 | **0** | **0%** | 95.4% | **-95.4pp** ✅✅✅ (Ch306/308 完全解決) |
| Observation | 252,966 | 201 | 0.079% | 0.070% | ↔ (Chain 対象外) |
| Composition | 4,523 | 27 | 0.60% | 0.6% | ↔ (Ch310 で eReferral event.code 22+15 消滅、残 42 は #313 backlog) |
| ImagingStudy | 762 | 589 | 77.30% | 74.5% | ↔ (Ch315 効果なし、required binding 未解決) |
| Location | 71 | 2 | 2.82% | 2.8% | ↔ |
| Condition | 6,236 | 0 | 0% | 0% | ↔ ✅ |
| AllergyIntolerance | 76 | 0 | 0% | 0% | ↔ ✅ |
| Encounter | 3,899 | 0 | 0% | 0% | ↔ ✅ |
| Practitioner | 101 | 0 | 0% | 0% | ↔ ✅ |
| その他 (17 種) | ~100,000 | 0 | 0% | 0% | ↔ |

**Chain 対象 5 種のうち MR/MAR は完全解決**。Composition は eReferral event.code が消え内部残 42 のみ (backlog)、ImagingStudy のみが方針変更を要する。

## 【要対処】Chain #315 ImagingStudy.procedureCode text-only の失敗詳細

### 現象

```
Bundle.entry[N].resource/*ImagingStudy/imgst-.../.procedureCode[0]
コードが提供されていません。ValueSet 'JP ImagingStudy RadLexPlaybook CodeDev VS'
(http://playbook.radlex.org/playbook/SearchRadlexAction|1.0.0) のコードが必須です
```

### v6.1 の実データ (Chain #315 適用後)

```json
{
  "resourceType": "ImagingStudy",
  "meta": {"profile": ["http://jpfhir.jp/fhir/core/StructureDefinition/JP_ImagingStudy_Radiology"]},
  "procedureCode": [{"text": "胸部単純X線撮影 正面"}]
}
```

`coding` を空にして `text` だけを設定した (Chain #315 の狙い)。

### なぜ失敗するか

**required binding は「テキストのみ」では満たされない**。HAPI validator の解釈:
- `procedureCode[0]` element が存在するなら、その CodeableConcept は required binding VS の code を **少なくとも 1 個 coding に持つ** 必要がある
- `text` は補助情報であり、required binding の充足には寄与しない
- 結果: `procedureCode[0]` は存在するのに valid code なし → "コードが提供されていません" error 発火

つまり Chain #315 の text-only approach では required binding を回避できず、以下 3 択のいずれかが必要:

1. **procedureCode 要素そのものを出力しない** (cardinality 0..* なので省略可) — 最もシンプル、rate 77% → 0%
2. **RadLexPlaybook VS 内の実際の code を選定して coding に入れる** — 検査種別 (胸部X線等) と RadLex code の mapping table 整備が必要
3. **JP Core 側で binding strength を required → extensible/example に緩和** — upstream JP Core への PR 提案 (時間軸長い)

**推奨: 1 (procedureCode 省略)**。text だけ残したいなら要素ごと落とす。診療情報は `ImagingStudy.description` に入れる代替案あり。

## v6.1 で残る主要 issue (優先度順)

| # | 対象 | 対処 |
|---:|---|---|
| **589** | ImagingStudy.procedureCode required binding (Chain #315 失敗) | procedureCode 要素を出力しない (省略) 、あるいは description に移す |
| **42** | Composition eReferral referralFrom/toSection Organization slice (#313 backlog) | eCS profile Organization 新設 + 8 required fields (中〜大工数、continuing backlog) |
| 190 × 2 | Observation.code.text 欠落 (LabResult / eCS 両方) | code.text にコード名称を必ず入れる |
| 162 | Observation valueCodeableConcept.coding.display 欠落 (qualitative) | qualitative code に display を必ず設定 |
| 22 × 2 | Observation.value.ofType(Quantity) unit/code 空 ele-1 | 空 Quantity を出さない (null / 要素そのものを省略) |
| 11 × 2 | Observation referenceRange units invariant (Low/High units-isSameAs-resultValueUnits) | referenceRange の unit を value と一致させる |
| 6 | Composition timeout (Read timed out) | インフラ (retry で流動) |
| 2 | Location v3-RoleCode 'OR' unknown | `OR` は v3-RoleCode 未収録、正しい code に置換 |

### rest 残 618 の対処見込み

- Chain #315 修正 (procedureCode 省略) → -589 (rate 77.30% → 0%)
- #313 完全解決 → -42
- v3-RoleCode `OR` fix → -2
- 残 timeout → 0 (infra)

**追加対処後見込み: rest error 0-6 (timeout のみ)** → 実質完全準拠

### obs 残 201 の対処見込み

- code.text 追加 → -190 unique
- valueCC display 追加 → -162 error instances
- 空 Quantity ele-1 修正 → -22 instances
- referenceRange units invariant → -22 instances

**追加対処後見込み: obs error < 10** → 実質完全準拠

## v6 → v6.1 で得られた知見

- **NOCODED fallback の display 制約は fixed value binding パターン**: 該当 code が定義された CS で `display` が 1 通りしか無い場合、CodeSystem 定義が実質的に required-fixed binding として作用する。「fallback code に情報を詰める」のではなく「fallback code は固定表現、情報は text に」の設計原則。
- **UnitsOfTime binding の HAPI 挙動を pragmatic に迂回できた**: `boundsDuration` のみに切替 (period + periodUnit 廃止) で tim-2 と UnitsOfTime binding の両方を回避、これは session 58 Chain #2 の元の狙いに戻す形。
- **required binding は "text only" では充足されない**: これは FHIR spec の設計上の原則で、CodeableConcept.text は補助情報。required binding VS が空でよいのは要素自体を省略した時のみ。

## caveat — 検証していないこと

- Observation の LOINC / SNOMED terminology 検証 (性能上スキップ、`HAPI_TX=n/a`)
- 業務ロジック (診療報酬点数、レセプト整合、医療的妥当性)
- Bundle Type validation (client が `collection` 化)

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~810MB) / `raw/obs.ndjson` (~1.1GB) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 次サイクルの見込み

**v6.1 → v6.2 で fail 率 0.190% → ~0.01% (実質 0)** が視野:

- Chain #315 修正 (procedureCode 省略) — -0.14pp
- #313 完全解決 (eReferral Organization) — -0.01pp
- Observation 系 4 種 fix — -0.05pp

これらは全て単純な生成側修正で対応可能。到達水準は「validator が検出する残余 error は infra timeout のみ」で実質完全準拠。
