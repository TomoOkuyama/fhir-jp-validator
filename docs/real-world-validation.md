# 実データバリデーション ガイド (JP Core / JP-CLINS)

日本の患者 FHIR データを本 validator で通した際の**実測特性・落とし穴・推奨構成**をまとめる。ベンチ数値は M3 Max 14 core + Docker Desktop 18GB での測定 (docs/benchmarks.md 参照)。

## 1. データ特性と `Observation` bottleneck

日本の EHR 由来 FHIR データは、リソース種別分布が極端に偏る傾向にあります (実測サンプル 3.58M res):

| 種別 | 占有率 | 備考 |
|---|---:|---|
| Observation | **65%** | 検査値中心、LOINC + 日本語 display |
| ServiceRequest / Procedure / MedicationAdmin | 15-20% | 中規模 |
| Composition / Condition / Encounter 等 | 5-10% | 小規模 |
| 他 (Patient/Organization 等) | <5% | ごく少数 |

**中核 bottleneck**: `Observation` に含まれる LOINC code の **日本語 display 検証**が fhirserver 側で 1 code あたり ~700ms かかる。

- 例: `Observation.code = {system: http://loinc.org, code: 1751-7, display: "アスパラギン酸アミノトランスフェラーゼ(AST)"}` を検証するとき、fhirserver は LOINC と JP terminology の間の日本語 mapping を照合し、その処理コストが極めて高い
- HAPI validator の `-check-display Ignore` は **HAPI 側の判定にしか影響せず、tx server (fhirserver) には引き続き display 込みで `$validate-code` を投げる**。結果、fhirserver 側で照合コストが発生し続ける
- Observation 1 件あたり平均 15+ code の tx call が必要 → 200k res 級では現実的な時間で完了しない

**対処 (分割検証戦略)**:

1. **`Observation` を分離** — 独立ディレクトリに移す
2. **他 25 種類**を `-tx=http://localhost:8181/r4` (通常の tx enabled) で検証
3. **`Observation`** を `HAPI_TX=n/a` (tx 検証スキップ、構造・slice・invariant のみ) で検証
4. 必要なら Observation の terminology は別途 1/100 サンプリング等で追加検証

## 2. 分割検証の実測結果 (1/20 sample, 179k res)

`/scripts/parallel-validate.py` を分割で回した実測:

| 対象 | resource 数 | 所要 | rps | 成功率 | 構成 |
|---|---:|---:|---:|:---:|---|
| 25 種 (非 Observation) | 63,477 | 3 分 27 秒 | 307 | 100% | `HAPI_EXTRA_ARGS="-best-practice ignore -check-display Ignore"`, tx 有効 |
| Observation | 115,718 | 7 分 21 秒 | 262 | 100% | `HAPI_TX=n/a`, 構造/slice のみ |
| **合計** | **179,195** | **10 分 48 秒** | **276** | **100%** | |

分割なしで tx 有効のまま Observation を検証すると、~64k 付近 (Observation ファイル序盤) で **1 code 700ms × 20-30 concurrent tx call** の詰まりで client timeout が連発し完走しません。

## 3. 実データで頻出する issue パターン

上位 issue を「原因」「対処要否」で分類。数字は 1/20 sample での出現数。

### tx 有効側 (25 resource type)

| # | severity | 内容 | 対処要否 |
|---:|---|---|---|
| 63,301 | warning | `dom-6` Best Practice: narrative missing | 不要 (Best Practice 推奨) — `-best-practice ignore` で抑止可 |
| 29,608 | info | `default display; no Display Names for language ja` | 不要 (SNOMED/LOINC に日本語 translation なし) |
| 27,092 | warning | `system 'X' で未知のコード` (CodeSystem fragment) | 該当 CodeSystem の完全版 load を検討 |
| **25,532** | **error** | **`Quantity.code: 最小必要値 = 1、見つかった値 = 0`** | **要修正** (UCUM 単位 code の欠落) |
| 14,998 | warning | `CodeSystem urn:oid:...1005 は未知` | 日本の医療機関コード OID、`jpfhir-terminology` 側の登録待ち |
| **8,526** | **error** | **`Slice X: minimum required = 1, but only found 0`** | **要修正** (eCS プロファイル必須 slice の欠落) |
| **6,354** | **error** | **`Unknown code 'X' in CodeSystem 'Y'`** | **要修正** (typo / deprecated code) |
| 各種 | error | `Condition.identifier / meta.lastUpdated / clinicalStatus.coding.display: 最小必要値 = 1` | 要修正 (JP_Condition_eCS 必須要素) |

**リソース単位 fail 率 (1+ error)**: 35,674 / 63,477 = **56%**

### tx=n/a 側 (Observation、構造/slice のみ)

| # | severity | 内容 | 対処要否 |
|---:|---|---|---|
| **111,623** | **error** | **`値は 'X' ですが、'Y' でなければなりません`** | **要修正** (status/カテゴリの enum 誤り) |
| 70,416 | warning | `dom-6` narrative missing | 不要 |
| 45,302 | info | `拡張可能な ValueSet に該当` | 通常は不要 |
| **40,600** | **error** | **`Slice X: minimum required = 1, but only found 0`** | **要修正** (JP_Observation_LabResult_eCS slice 欠落) |
| **28,128** | **error** | **`Observation.specimen: 最小必要値 = 1, but only found 0`** | **要修正** (検体 reference 欠落) |
| 各種 | info | `Validate Observation against the Heart rate profile ... required because LOINC code N was found` | 情報のみ (LOINC vital-signs 自動プロファイル) |
| **14,128** | **error** | `Observation.meta.lastUpdated 最小必要値` / `identifier 必須` / `status 必須` | **要修正** (eCS 必須要素の欠落) |
| **14,064** | **error** | `extension URL はこの時点では使用できません` / `extension タイプ ... が見つかりました` | **要修正** (拡張の型/位置違反) |

**リソース単位 fail 率**: 80,778 / 115,718 = **70%**

### 全体像

- **全体 fail 率**: (35,674 + 80,778) / 179,195 = **65%** リソースに 1+ error
- **主な error 原因**: JP-CLINS eCS プロファイル (JP_Observation_LabResult_eCS 等) の必須 slice/要素の欠落、および Observation の一部フィールドの値域違反 (`値は X ですが Y でなければ`)
- **無視して良い noise の割合**: 全 warning の ~30% (dom-6 だけで 133k) は Best Practice で対処不要

## 4. 推奨検証構成 (実データ用)

### 4.1 少量検証 (< 30k res / 半日以内で結果が欲しい)

```bash
docker compose up -d fhirserver
HAPI_EXTRA_ARGS="-best-practice ignore" \
  ./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py <input> --output result.json --chunk 50 --parallel 24
./scripts/hapi-cluster.sh stop
```

Best Practice の noise を消すだけで、rps が上がる (default warning 生成コストが減る) + 出力量が減る。

### 4.2 大量検証 (100k+ res、Observation を含む)

`Observation` を必ず分離。以下パターンで:

```bash
# 分離
mkdir -p input_rest input_obs
mv input/Observation.ndjson input_obs/
mv input/* input_rest/

# rest: tx 有効
docker compose up -d fhirserver
HAPI_EXTRA_ARGS="-best-practice ignore" \
  ./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py input_rest --output rest.json --chunk 50 --parallel 24 --timeout 120 \
  --include-file input_rest/Organization.ndjson    # cross-bundle Reference resolve、詳細は 4.3
./scripts/hapi-cluster.sh stop

# Observation: tx=n/a (構造/slice/invariant のみ)
HAPI_TX=n/a HAPI_EXTRA_ARGS="-best-practice ignore" \
  ./scripts/hapi-cluster.sh start
./scripts/parallel-validate.py input_obs --output obs.json --chunk 50 --parallel 24
./scripts/hapi-cluster.sh stop
```

**Observation の terminology 検証は別途、無作為抽出で行うのが実務的** (例: 5k 件だけを sample し fhirserver で `$validate-code` 直接呼び)。

### 4.3 cross-bundle Reference の解決 (`--include-file`)

**症状**: `Composition` や `MedicationRequest` 等の profile が `.section:xxx.entry:organization`
のような slice を `min=1` で要求している場合、下記のような error が持続する:

```
Slice 'Composition.section:referralFromSection.entry:referralFromOrganization':
  minimum required = 1, but only found 0
```

data 側では `Organization/hospital-main-ecs` を正しく参照しているのに、この error が出る。

**原因**: `parallel-validate.py` は resource を `--chunk N` (default 30) 個ずつ 1 Bundle に
まとめて `/validateResource` に投げる。参照先の Organization が別 Bundle に落ちると、
HAPI validator は Bundle 内で `resolve()` に失敗し slice discriminator が発火しない。
これは data の問題ではなく **client 側の分割戦略に由来する artifact**。

**対処**: `--include-file` で **参照候補になる resource を全 Bundle に前置** する。

```bash
./scripts/parallel-validate.py input_rest --output rest.json \
  --chunk 30 --parallel 24 \
  --include-file input_rest/Organization.ndjson \
  --include-file input_rest/Location.ndjson \
  --include-file input_rest/PractitionerRole.ndjson
```

- 前置された resource 自体は入力側から自動的に除外され二重投入されない (`load_sticky` +
  `bundle_generator`)
- 前置 resource に付いた OperationOutcome issue は `filter_sticky_from_outcome` により結果
  から除去され、fixture 由来の noise が入らない
- `--include-file` は複数指定可 (`Organization.ndjson`, `Location.ndjson`, ...)。file でも
  dir でも受け付ける

**実測** (2026-07-21, v15 データ 178,818 res、Composition 4,523 件を対象):

| pass | error | 42 error 由来 (referralFrom/ToSection Organization slice) |
|---|---:|---:|
| 通常 (`--include-file` 無し) | 42 | **21 件 × 2 slice = 42** (Composition 21/4523 fail) |
| `--include-file Organization.ndjson` | **0** | **0** |

**トレードオフ**:

- **Bundle サイズが膨張**: 前置 fixture 分 × Bundle 数 だけ処理量が増える
  (17 Organizations × 5,961 Bundle ≒ 101k 追加 resource 相当、実測で rest 8.1 min → 影響
  軽微。fixture が数千件を超える場合は要注意)
- **前置候補の選定**: `Reference.type` を明示していない参照は候補が広く、`Patient`/`Practitioner`
  等 大量 resource を include すると Bundle が爆発する。まずは errors から失敗している slice
  を特定し、最小の fixture set (Organization / Location / PractitionerRole 等の小規模 master
  データ) から入れる

**再集計 recipe**:

```bash
# resourceType 別 fail 数を再集計 (OperationOutcome から)
python3 -c "
import json, re, collections
c = collections.defaultdict(set)
pat = re.compile(r'resource/\*([A-Za-z]+)/([^*]+)\*/')
for line in open('result.ndjson'):
    oo = json.loads(line)
    for i in oo.get('issue', []):
        if i.get('severity') != 'error': continue
        for e in i.get('expression', []) or []:
            m = pat.search(e)
            if m: c[m.group(1)].add(m.group(2))
for rt, ids in sorted(c.items(), key=lambda x: -len(x[1])):
    print(f'{rt}: {len(ids)} fail')
"
```

### 4.4 全構成での期待値 (M3 Max Rosetta)

| データ規模 | 分割 | 予想時間 |
|---|---|---|
| 1/20 (179k res) | あり | **~11 分** |
| 1/1 (3.58M res) | あり | 3-4 時間 (Observation の tx=n/a で線形) |
| 1/1 (3.58M res) | なし (tx 全部) | **完走しない** (Observation 序盤で timeout) |

## 5. 既知の validator 限界

- **HAPI validator `-check-display Ignore` は表示された振る舞いにしか影響しない**。tx server への `$validate-code` request には display が含まれ続けるため、fhirserver 側で日本語 display 照合コスト (~700ms/call) は削減不能。この振る舞いは HAPI 6.9.11 で確認。
- **fhirserver (HL7 fhirserver Pascal 実装) の日本語 display 照合速度は 1 code ~700ms**。SNOMED CT には日本語 translation なし、LOINC は部分的、JP terminology 側の日本語 code は照合ロジック上効率が悪い。改善には fhirserver 側の tuning もしくは Pascal 側 patch が必要。
- **HAPI cluster の 6 JVM 並列は M3 Max で最適** (4 JVM = CPU 余剰、8 JVM = coordination overhead)。docs/benchmarks.md 参照。
- **fhirserver LB (2 台化) は今回の設計 (nginx + separate terminology volume) では改善なし**。理由: fhirserver は idle 時 in-memory cache hit で速く、CPU-bound 時は per-call latency (~700ms) が支配的で並列化ゲインが乏しい。

## 6. 次に検討する余地

品質を保ちながらさらに速度が欲しい場合の未検証施策:
- `fhirserver` 側の日本語 index 事前 build (要 Pascal 側 patch)
- HAPI validator を patch して `$validate-code` から display を落とす (`-check-display Ignore` の semantics を tx call まで伝播)
- Observation 内の重複 code をリソース間で dedup してから tx call (client 側 layer 追加)
- native amd64 Linux server 上で fhirserver 実行 (Rosetta emulation overhead 除去、想定 +30-50%)
