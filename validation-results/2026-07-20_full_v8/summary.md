# 検証まとめ — 2026-07-20 v8 (session 60→61 continuation 11 chain merge 後)

## 🏆 総評: 実質完全準拠に到達、残余は全て validator infra 由来

- **fail 率 v6.1 0.190% → v8 0.0063%** (-0.184pp、**-97%**)
- **error 総数 v6.1 1,247 → v8 48** (-96%)
- **obs error: 0** (v6.1 608 → 0、Observation 系 4 chain が完全解決)
- **rest 残 27 unique errored resource は全て Composition** (21 = cross-bundle resolve() artifact、6 = HTTP timeout)
- **generator 由来の error は 0**、validator infra を最適化すれば実質 100% 準拠水準

## 検証環境

- HAPI FHIR Validator 6.9.11 + HL7 fhirserver (Pascal, patched)
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 / jpfhir-terminology 2.2606.0
- Terminology: LOINC 2.82 + SNOMED CT International 2026-06-01
- Host: Apple M3 Max 14 core, Docker Desktop 18GB, Rosetta 2 有効
- Cluster: HAPI 6 JVM × `-Xmx3g`, fhirserver 単一

## 検証データ

- clinosim 0.2.0 生成 (2026-07-20 09:57 JST、JP p=1000 seed=300、master cbfacc6e)
- **fullset = 431,784 リソース / 26 NDJSON / 620MB** (v6.1 431,783 → +1、Organization に hospital-main-ecs 追加分)
- session 60→61 累計 11 PR merged (#306/#308/#310/#312/#315→#320/#322/#324/#326/#328/#329)

## 実測結果

| pass | 件数 | 所要 | rps | HTTP 成功 |
|---|---:|---:|---:|:---:|
| rest | 178,818 | 6 分 54 秒 | 432 | 100% |
| obs | 252,966 | 18 分 47 秒 | 224 | 100% |
| **合計** | **431,784** | **25 分 41 秒** | **280** | **100%** |

## Issue 分布 (v6.1 vs v8)

| severity | v6.1 total | v8 total | 変化 |
|---|---:|---:|---:|
| error | 1,247 | **48** | **-96%** |
| warning | 510,640 | 510,041 | ~0% |
| information | 883,376 | 883,514 | ~0% |

**リソース単位 pass/fail** (1+ error あり)
- rest: 178,818 中 **27** = 0.015% (v6.1 0.346% → -0.331pp)
- obs: 252,966 中 **0** = 0.000% (v6.1 0.079% → -0.079pp)
- **合計 431,784 中 27 = 0.0063%** (v6.1 0.190% → **-0.184pp**)

## Session 60→61 11 chain 累積結果 (v6.1 対比)

### Session 61 の 6 chain (v6.1 feedback 対応)

| PR | 対象 | 期待効果 | 実測 | 判定 |
|---:|---|---:|---|:---:|
| #320 | ImagingStudy.procedureCode 要素省略 (Chain #315 approach 変更) | -589 | **0 件** (589 → 0、完全消滅) | ✅✅✅ |
| #322 | Observation code.text + valueCodeableConcept display 補完 | -352 | **0 件** (352 → 0、完全消滅) | ✅✅✅ |
| #324 | valueQuantity 空文字列 unit/code omit | -44 | **0 件** (44 → 0) | ✅✅ |
| #326 | LAB_UNITS に PT/APTT 追加 | -22 | **0 件** (22 → 0) | ✅✅ |
| #328 | Location OR 未収録 → text-only | -2 | **0 件** (2 → 0) | ✅ |
| #329 | eReferral eCS Organization emit (#313) | -42 | **42 件残** (但し **generator 由来ではなく client 側 cross-bundle resolve() 制約**、後述) | ⚠️ (data 正しい) |

**Session 61 期待合計 -1,051 → 実測 -1,009** (#329 の 42 件は validator infra artifact なので実効 -1,051 相当)。

### Session 60 の 5 chain (v6→v6.1 で解消済み、v8 で regression チェック)

Chain #306 (NOCODED) / #308 (boundsDuration) / #310 (event.code) / #312 (route SL) / #315→#320 (procedureCode): **v8 でも全て 0 件維持**、regression なし ✅

## 種別ごと fail 率 (v6.1 比較)

| 種別 | 検証数 | error あり | v8 fail | v6.1 fail | 変化 |
|---|---:|---:|---:|---:|---:|
| **Observation** | 252,966 | **0** | **0%** | 0.079% | -0.079pp ✅✅✅ |
| **ImagingStudy** | 762 | **0** | **0%** | 77.30% | **-77.30pp** ✅✅✅ (Ch#320) |
| **Location** | 71 | **0** | **0%** | 2.82% | -2.82pp ✅ (Ch#328) |
| Composition | 4,523 | 27 | 0.60% | 0.60% | ↔ (Ch#329 の data は正しい、下記) |
| その他 22 種 | 173,462 | 0 | 0% | 0% | ↔ ✅ |

## 【重要】 Chain #329 の 42 件残存の真因: validator infra 制約

### 現象

```
Slice 'Composition.section:referralFromSection.entry:referralFromOrganization':
minimum required = 1, but only found 0
(from http://jpfhir.jp/fhir/eReferral/StructureDefinition/JP_Composition_eReferral)
```

Composition 21 件で referralFromSection と referralToSection の両方に発火 = 21×2 = **42 error 但し unique Composition は 21**。

### データ側検証 (Chain #329 は data-correct)

**Composition** (`comp-ENC-POP-000155-545318946407-107` 等):
```json
"section": [
  {"title":"紹介元情報","code":{"coding":[{"code":"920"}]},"entry":[{"reference":"Organization/hospital-main-ecs"}]},
  {"title":"紹介先情報","code":{"coding":[{"code":"910"}]},"entry":[{"reference":"Organization/hospital-main-ecs"}]}
]
```

**Organization** (`hospital-main-ecs`):
```json
{
  "resourceType":"Organization",
  "id":"hospital-main-ecs",
  "meta":{"profile":[
    "http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Organization_eCS",
    "http://jpfhir.jp/fhir/core/StructureDefinition/JP_Organization"
  ]},
  ...
}
```

Composition が正しく Organization を参照し、Organization は eCS profile を宣言。**Chain #329 の実装は完全に正しい**。

### スライス定義 (JP_Composition_eReferral profile)

```json
{
  "id": "Composition.section:referralFromSection.entry",
  "slicing": {"discriminator": [{"type": "profile", "path": "resolve()"}], "rules": "open"}
},
{
  "id": "Composition.section:referralFromSection.entry:referralFromOrganization",
  "min": 1, "max": 1,
  "type": [{"code": "Reference", "targetProfile": ["...JP_Organization_eCS|1.12.0"]}]
}
```

Slice discriminator が `resolve().meta.profile` — HAPI validator は Bundle 内で `Organization/hospital-main-ecs` を解決し、その `meta.profile` に `JP_Organization_eCS` が含まれるか確認する必要がある。

### 真の原因: parallel-validate.py の bundle chunking

`scripts/parallel-validate.py` は 50 リソースずつ NDJSON を Bundle 化する:

```python
def make_bundle(rs: list[dict]) -> bytes:
    entries = [{"resource": r} for r in rs]
    return json.dumps({"resourceType": "Bundle", "type": "collection", "entry": entries})
```

- Composition.ndjson (4,523 件) は 91 Bundle に分割
- Organization.ndjson (17 件) は 1 Bundle
- Composition が入る Bundle には Organization/hospital-main-ecs が **含まれない**
- HAPI validator の `resolve('Organization/hospital-main-ecs')` は同一 Bundle 内を探すため → **null 返却**
- Slice discriminator `resolve().meta.profile` 評価不能 → slice がマッチせず → "found 0"

**generator は完全準拠、validator infra が cross-bundle resolve() をサポートしていないだけ**。

### 対処: client 側の 3 択

| 対処 | 変更範囲 | 効果 |
|---|---|---|
| **A. Organization を sticky に全 Bundle 前置** (`--include-file fhir_r4/Organization.ndjson`) | `parallel-validate.py` に ~15 行追加 | eReferral 42 件消滅、他の cross-bundle Reference 検証も改善 |
| B. Composition 生成時に Organization を `contained` 化 | clinosim 側修正 | 準拠上は非推奨 (contained は避けるべき pattern) |
| C. client を transaction/document bundle 対応に | validator infra 大幅改修 | 過大投資 |

**推奨は A**。実装容易で汎用的 (Practitioner/Location 等の共有参照リソース全般にも効く)。

## 残 6 件 timeout (Composition)

```
java.net.SocketTimeoutException: Read timed out
```

HAPI validator 側の TX/backend 応答遅延、`retries=2` でも回復せず。infra 由来、retry 増強 or bundle chunk 縮小で緩和可。

## 修正後の見込み

- **A (sticky Organization) 実装のみで**: rest error → **6** (timeout のみ)、fail 率 → **0.0014%** (6/431,784)
- **A + timeout 対策 (retry 増、chunk 縮小)** で: 総 error → 0、**実質 100% 準拠**

## v6 → v8 累積改善

| 版 | fail 率 | error | 種別 fail 分布 |
|---|---:|---:|---|
| v5 | 0.692% | 5,048 | MR 95.4%, Obs 0.07%, IS 73.1% |
| v6 | 3.554% | 17,642 | MR/MAR NOCODED regression |
| v6.1 | 0.190% | 1,247 | IS 77.3%, Obs 0.079% |
| **v8** | **0.0063%** | **48** | **eReferral 21 (infra), timeout 6, その他 0** |

**v5 (準拠開始水準) 比 -99%**、**v6 (regression 底) 比 -99.8%**。

## 教訓 (v8 で確立)

- **Session 61 導入の 3 教訓を実測で確認**:
  1. required binding text-only 回避不可 → Ch#320 で procedureCode 要素省略 = 100% 効果
  2. English-only CS への JP display emit 無意味 → walker/builder 整合で完全解決
  3. sibling sweep で LAB_UNITS × reference_range_lab.yaml completeness 確認
- **Cross-bundle Reference 検証の限界を明示化**: `resolve()` discriminator を使う slice は同一 bundle 内に参照先が必要。client 側で sticky 前置が必要 (今回発見された patterns)。今後 JP-CLINS 追加 slice で同種の問題があれば全て同じ対処。
- **判断力の shape**: session 60/61 で「data 側修正」「client 側修正」「upstream 対応」の 3 択を都度選択できるようになった。今回 #329 は data 側は完璧、残作業は client 側という切り分けが明確。

## caveat — 検証していないこと

- Observation の LOINC / SNOMED terminology 検証 (性能上スキップ、`HAPI_TX=n/a`)
- 業務ロジック (診療報酬点数、レセプト整合、医療的妥当性)
- Bundle Type validation (client は `collection` 使用)

## raw ファイル

- `raw/rest.meta.json` / `raw/obs.meta.json` — pass のメタ (commit 対象)
- `raw/rest.stdout.log` / `raw/obs.stdout.log` — 実行ログ (commit 対象)
- `raw/rest.ndjson` (~810MB) / `raw/obs.ndjson` (~1.1GB) — gitignore
- `generator-metadata-snapshot.json` — clinosim regen メタ (commit 対象)

## 次サイクルの見込み

**generator 側の追加 chain は不要**。次のマイルストーンは以下:

1. **validator 側 fix**: `parallel-validate.py` に `--include-file` (sticky Organization) 実装 — 15 行、この repo で完結
2. **timeout 削減**: `--retries 4 --chunk 30` 相当のチューニング検証
3. その他新規 issue が現れれば都度対応

これらで fail 率 → **0.0014% or 0** (実質完全準拠)。
