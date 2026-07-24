# 2026-07-23 JP-CLINS 検体検査コーディング移行 Gate 検証

clinosim (workspace:1) 側で検体検査 Observation を LOINC → JLAC10/JP-CLINS に移行する
実装着手前の gate 検証。docs / data の変更を伴わない調査のみ。

## Gate 1: fhirserver が `descendent-of` VS expansion を実行できるか — **PASS**

### 事前確認

- `JP_CLINS_ObsLabResult_CoreLabo_CS` load 済 (version 2026.03.31, content=complete, count=833, hierarchyMeaning=is-a)
- `JP_CLINS_ObsLabResult_Uncoded_CS` load 済 (content=complete, count=1, version 1.4.0)

### VS expansion 実測

| VS | v1.6.0 render 期待 | 実測 |
|---|---:|---:|
| `CoreLaboJLAC10_k_VS` | 10 | **14** (期待 10 全含む + 4) |
| `CoreLaboJLAC10_wbc_VS` | 2 | **3** (期待 2 全含む + 1) |

版差 (2026.03.31 版) による定義追加分。descendent-of フィルタ正常動作。

> **訂正 (2026-07-24)**: 上記「suffix 版差追加分」の解釈は不正確。実際は以下。
> baseline の期待値 10 / 2 は **v1.6.0 IG の render (依頼側が提示)** に由来する古い list。
> 実測に含まれる **追加 4 件 (k_VS)** / **追加 1 件 (wbc_VS)** は全て
> **測定法コード `998` (測定法問わず)** の子で、fhirserver に load している
> 2026.03.31 版 CS に含まれる `<検体材料>_998_<識別>` 系 17 桁 code が
> descendent-of で拾われた結果である。
>
> 結論の差分:
> - 「CS が版差で不安定」ではなく「古い IG render を baseline としたこと」が真因
> - **測定法 998 (測定法問わず)** の存在は generator 側の code 選択規則に直結する
>   情報 (WBC/K 等の分類軸で 998 を選ぶかどうかの判断に必要)
> - 教訓: 外部から渡された期待値は、実測との突き合わせで真因を確認してから
>   結論を書く。「版差」で片付けると 998 の意味が失われる

### `$validate-code` 実測

| test | code | 期待 | 実測 |
|---|---|---|---|
| K の 17 桁子 | `3H015000002327201` | true | ✅ true (display: K) |
| K 親 | `K` | false (自己除外) | ✅ false (Not found) |
| 不在 | `9999` | false | ✅ false (Unknown code) |

**必ず 17 桁 code を emit する必要**が実測で確定。

備考: `CodeSystem/$lookup?code=<17桁>` は fhirserver Access violation を返すが、
`$validate-code` と `$expand` は完全動作、運用影響なし。

## Gate 2: Open slicing display 不一致 silent-pass — **SILENT-PASS 確認**

### Setup

- meta.profile: `http://jpfhir.jp/fhir/eCS/StructureDefinition/JP_Observation_LabResult_eCS`
- 5 obs を Bundle 化、HAPI Validator 6.9.12 (tx=8181) に POST
- 変数を code.coding[0] の code + display に絞った最小構成

### 結果 (test bundle setup 上のノイズ = Patient_eCS 未適合、meta.lastUpdated、
category slice、refRange、dom-6、performer 系 は本 gate 外なので除外)

| # | code | display | slice matching | 結論 |
|---|---|---|---|---|
| 1 | WBC 17 桁 | `WBC` (fixed) | ✅ WBC slice matched | **clean pass** |
| 2 | WBC 17 桁 | `白血球数` | ❌ **どの既知スライスにも一致しない** (information severity のみ) | 🚨 **SILENT-PASS** |
| 3 | K の code | `WBC` | matched via display | ✅ error 2 種 (K code not in wbc VS、K の display は K/カリウム(K)) |
| 4 | 不在 code | `WBC` | matched via display | ✅ error 3 種 (未知 code + not in VS + URI unknown) |
| 5 | K 親 | `WBC` | matched via display | ✅ error 2 種 (Wrong Display + not in VS) |

### 🚨 case 2 で silent-pass 確定

case 2 (`code=2A990000001930952, display=白血球数`) の実測:

```
[information] code.coding[0]: この要素はどの既知のスライスとも一致しません
              defined in JP_Observation_LabResult_eCS|1.12.0
```

- severity: **information** (error/warning でなく silent)
- WBC slice の required binding も fixed display check も **両方 skip**
- Open slicing (rules=open) の設計上、unmatched extra coding は正常扱い

### 準拠性担保の観点

**移行後、generator が display を fixed 値 (英語 abbreviation) 以外で emit すると
validator は silent 承諾** = spec 上の準拠性を validator で担保できない。

generator 側で必須:
1. fixed display (英語 abbrev) を strict に emit — WBC slice なら `display = "WBC"` 必須
2. 別言語 UI 表示は `CodeableConcept.text` field で保持 (validator 対象外)
3. **generator CI で "各項目 slice の display が fixed 値と一致するか" invariant 追加**
   (validator に頼れないため)

備考: case 3 が正しく error になった = **binding は slice match 成立時に確実に発火**。
問題は「slice match の hurdle が display strict 比較」であること。

## 補助: Uncoded slice 疎通

- `$validate-code?system=<Uncoded_CS>&code=99999999999999999&display=未標準化コード項目(JLAC)`
- → **result: true** (1 concept CS で軽量)
- **Phase 1 fallback として即使用可**、MEDIS マスター入手も 17 桁 マッピングも不要で成立

## 性能実測 (Phase 1 移行後の bottleneck 見通し)

fhirserver 直 curl、warm、`Accept: application/fhir+json`:

| operation | latency (4 runs) |
|---|---:|
| `$validate-code` on 17 桁 CoreLabo code | 112 / 114 / 116 / 117 ms |
| `$expand` on wbc_VS (3 concept) | 113 / 116 / 120 ms |

- LOINC Observation の ~700 ms/code (`Display()` SQL + FLock 直列化 + 大規模 CS) と比較して
  **6-7 倍高速**
- CoreLabo CS は 833 concept と小規模、hierarchy is-a 解決も軽量
- **Observation を `HAPI_TX=n/a` で分離している現行運用を見直せる可能性**
- ただし移行過渡期 (LOINC + JLAC 混在) は LOINC 側 bottleneck が残る

> **訂正 (2026-07-24)**: 「6-7 倍高速」および「obs 分離運用を見直せる」の主張は取り下げ。
> - CoreLabo 113 ms は **fhirserver 直・単発・warm** の測定
> - LOINC ~700 ms は **HAPI cluster 経由・並列実行下** (P=24 相当)。
>   真因は tx-cache miss + VS expansion + **`FLock` mutex による直列化** の合算で、
>   `FLock` の影響は並列度が上がって初めて顕在化する
> - 測定条件 (単発 vs 並列) が揃っていないため両者の比較は成立しない
> - **移行運用 (`HAPI_TX=n/a` 分離見直し) の性能根拠にできるかは、P=24 相当の
>   並列下で JLAC を測り直してから判断する**。それまでは未確定として扱い、
>   移行の動機に性能改善を含めない
> - 現時点で確度あるのは「fhirserver 直・単発・warm で JLAC = 113 ms、
>   小規模 CS の descendent-of 展開が軽い」のみ

## 総合判定

- **Gate 1: ✅ PASS** — 実装着手可
- **Gate 2: ⚠️ SILENT-PASS 確認** — 移行可、ただし display strict 一致は generator 側 invariant で担保する義務
- **Uncoded slice**: ✅ 利用可、Phase 1 fallback 成立
- **性能**: JLAC 系は LOINC 比 6-7 倍高速、obs 分割戦略見直しの余地

## 未検証項目 (明示、2026-07-24 追記)

本 gate 検証で扱っていない領域。移行実装や第三者利用で踏む可能性があるため明示する。

- **InfectionLabo (指定感染症 5 項目)**: 現行 data で emit 0 件のため実害なし。
  ただし Fixed display が **日本語** (`HBs抗原(定性)` / `梅毒STS(定性)` /
  `HCV核酸増幅検査(定量)` 等) であり、英語 abbrev の CoreLabo と挙動が同じとは
  限らない。移行実装で InfectionLabo を emit する前に別途 gate 検証が必要
- **cold / cache-miss 時 latency**: 実測は全て warm cache 前提。cold state の
  `$validate-code` / `$expand` latency は未測定
- **`JP_CLINS_ObsLabResult_LocalUncoded_CS`**: fhirserver に未 load。
  `JP_CLINS_ObsLabResult_Uncoded_CS` (§ 補助 で疎通確認済) とは **別 CodeSystem**。
  LocalCode fallback で必要になった際に別途 load が要る

## Tier 2 の計測可能性 (2026-07-24 追記)

Gate 2 の silent-pass は OperationOutcome に severity=information として残る:

```
[information] code.coding[N]: この要素はどの既知のスライスとも一致しません
              defined in JP_Observation_LabResult_eCS|1.12.0
```

`result.ndjson` から `expression` で集計すれば **JP-CLINS Open slicing 下の
unmatched を件数で計測可能**。汎用形の集計 recipe は
[`docs/output-guide.md` §4.5](../../docs/output-guide.md) に追加済
(2026-07-24)。

**v31 データでの実測分布** (2026-07-24 実施):
[`tier2-distribution-v31.md`](tier2-distribution-v31.md)

要点 (切り分け後):
- 生 count 28,334 件 = 全 issue の 22.19% (clinosim v31 合成データ、tx=8181、
  MHLW Phase 1/3 load 済、HAPI 6.9.12 の特定条件下、外部引用時は条件セット必須)
- 内訳を切り分けた結果:
  - **Tier 2-noise 19,583 件 (69%)**: `Observation.category` 19,399 +
    `DiagnosticReport.category` 184。data が「JP profile 用 coding + HL7 base
    用 coding」を意図的に並置しており、各 profile 視点から相手側 coding が
    余剰 unmatched と評価される。**data 設計としては正しく、非準拠ではない**
  - **Tier 2-real 8,751 件 (31%) = 全 issue の 6.86%**: `Observation.code.coding`
    5,032 + `Observation.identifier` 2,523 + `Condition.identifier` 736 +
    `DiagnosticReport.code.coding` 203 + `MedicationRequest.medication.coding`
    118 + `MedicationAdministration.dosage.rate` 47 + `Procedure.code.coding` 44
    + `Condition.bodySite.coding` 43 + `AllergyIntolerance.identifier` 5。
    これらは真の silent-pass = **data が profile の期待に合致していないが
    error/warning が出ていない状態**

Gate 2 で発掘した検体検査 `code.coding` pattern (Tier 2-real) は 5,032 件で
Tier 2-real の 57.5% を占め、Tier 2-real の中では最大寄与。ただし生 count に
対しては 17.8% で、残り Tier 2-real は他 resourceType の identifier 系や
CodeableConcept 系に広く分布している。

切り分け根拠 (JP_Observation_Common の category:first slice 定義、data 実物、
Tier 2-noise / Tier 2-real の判定基準) は tier2-distribution-v31.md 内。

**意味**: JLAC 移行の真の成果は「エラーが減る」ではなく、Tier 2-real の
`matched / (matched + unmatched)` = **slice 適合率**という新指標が手に入る
ことにある。Tier 2-noise (category 系) は data の多重 coding 設計に依存する
constant で、移行効果測定からは除外する。

## clinosim 側 (workspace:1) 移行実装要件まとめ

1. 各項目 slice の **fixed display (英語 abbrev)** を 100% 正確に emit
   - WBC/K/TP/ALB 等、間違えると silent-pass
2. **必ず 17 桁 code** (親コード K/WBC 等は不可、descendent-of 自己除外)
3. generator CI に **"emit 対象 display が profile の fixed 値と一致するか" invariant** 追加
4. CoreLabo 非該当項目は Uncoded slice fallback で問題なし
5. `Coding.text` に日本語 (`カリウム(K)`, `白血球数` 等) を配置して UI レイヤ日本語表示を確保
