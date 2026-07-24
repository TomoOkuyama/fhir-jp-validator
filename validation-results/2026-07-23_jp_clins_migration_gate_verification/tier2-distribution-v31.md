# Tier 2 (slice unmatched) 分布 — v31 データ実測 (2026-07-24)

Gate 2 で発掘した silent-pass パターン (`code.coding` の Open slicing) が、
検体検査 Observation の code.coding 固有ではなく **JP-CLINS profile 全体に
広範に分布する Tier 2 の一般的性質**であることを、v31 (2026-07-23、
Phase 3 receipt-master complete、tx=8181、full-set) の `result.ndjson` で実測。

集計方法は [`docs/output-guide.md` §4.5](../../docs/output-guide.md) の
汎用 recipe を使用。message pattern は日本語版
`この要素はどの既知のスライスとも一致しません` + 英語版
`This element does not match any known slice` の両方をカバー。

## 実測サマリ

- **scanned**: 1,161 Bundle、127,663 issue
- **slice unmatched (severity=information)**: **28,334 件 = 全 issue の 22.19%**
- 該当リソース種別: 7 種 (Observation / Condition / DiagnosticReport /
  MedicationRequest / MedicationAdministration / Procedure / AllergyIntolerance)

silent-pass は **`Observation.code.coding` だけの現象ではない**。JP-CLINS
profile を宣言している任意の CodeableConcept 系 slice で発生している。

## resourceType 別

| resourceType | 発生件数 | unique リソース |
|---|---:|---:|
| Observation | 26,954 | 13,431 |
| Condition | 779 | 736 |
| DiagnosticReport | 387 | 210 |
| MedicationRequest | 118 | 118 |
| MedicationAdministration | 47 | 47 |
| Procedure | 44 | 11 |
| AllergyIntolerance | 5 | 5 |

## profile 別

| profile | 発生件数 |
|---|---:|
| `JP_Observation_Common` | 10,908 |
| `JP_Observation_LabResult_eCS\|1.12.0` | 7,555 |
| `heartrate\|4.0.1` (HL7 vital-signs 自動 profile) | 2,819 |
| `oxygensat\|4.0.1` | 2,500 |
| `bp\|4.0.1` | 1,252 |
| `bodytemp\|4.0.1` | 987 |
| `resprate\|4.0.1` | 933 |
| `JP_Condition_eCS\|1.12.0` | 779 |
| `JP_DiagnosticReport_LabResult` | 354 |
| `JP_MedicationRequest_eCS\|1.12.0` | 118 |
| `JP_MedicationAdministration` | 47 |
| `JP_DiagnosticReport_Radiology` | 26 |
| `JP_Procedure` / `JP_Procedure_eCS\|1.12.0` | 各 22 |
| `JP_DiagnosticReport_Microbiology` | 7 |
| `JP_AllergyIntolerance_eCS\|1.12.0` | 5 |

**HL7 vital-signs 系 5 profile (heartrate/oxygensat/bp/bodytemp/resprate) の
合計 8,491 件**は、Observation に LOINC vital-sign code が含まれると HAPI が
自動的に vital-signs profile を追加適用する挙動由来。JP-CLINS 側の profile と
同時評価されるため、双方で unmatched が計上される。

## 要素 path 別 (top、正規化済)

| resourceType | element path | 発生件数 | unique リソース |
|---|---|---:|---:|
| Observation | `.category` | **19,399** | 10,908 |
| Observation | `.code.coding` | 5,032 | 2,523 |
| Observation | `.identifier` | 2,523 | 2,523 |
| Condition | `.identifier` | 736 | 736 |
| DiagnosticReport | `.code.coding` | 203 | 203 |
| DiagnosticReport | `.category` | 184 | 184 |
| MedicationRequest | `.medication.ofType(CodeableConcept).coding` | 118 | 118 |
| MedicationAdministration | `.dosage.rate.ofType(Quantity)` | 47 | 47 |
| Procedure | `.code.coding` | 44 | 11 |
| Condition | `.bodySite.coding` | 43 | 43 |
| AllergyIntolerance | `.identifier` | 5 | 5 |

path は `[N]` (array index) と `:sliceName` を除去して正規化。

## 観察

1. **最多は Observation.category** (19,399 件 / 10,908 obs)。code.coding より
   3.8 倍多い。Gate 2 では code.coding のみ検証したが、実データでは category が
   より広範に silent-pass している
2. **identifier 系** (Observation / Condition / AllergyIntolerance) も silent-pass
   pattern。Open slicing + `S 0..*` の identifier slice (system 別 slice 等) が
   discriminator 不一致で unmatched になっている
3. **MedicationRequest.medication.ofType(CodeableConcept).coding** で 118 件。
   薬剤の CodeableConcept 系 slice が unmatched
4. **HL7 base vital-signs profile 8,491 件**は HAPI 自動適用由来。data 側 fix
   ではなく validator 側の profile 適用方針の検討対象
5. **MedicationAdministration.dosage.rate.ofType(Quantity) 47 件**は Quantity 型
   の Open slicing (rate\[x\] の型別 slice) の unmatched

## 移行効果測定における意味

JLAC 移行の効果測定では、これまで「エラー数の増減」を追ってきたが、Tier 2
分布はエラーには全く現れない。この 28,334 件の分布を移行前後で比較することで:

- **matched / (matched + unmatched)** の比率 = **slice 適合率**という新しい指標が
  取れる
- 移行前は unmatched がベースラインとして数えられていなかったため、この計測は
  「エラーが減った」とは全く別軸の成果になる
- code.coding だけでなく category / identifier 系にも同じ計測を広げれば、
  JP-CLINS 全体の準拠実態が可視化される

## 再現手順

```bash
# 分布再計測
python3 <<'PY'
import json, re, collections
path = 'validation-results/2026-07-23_full_v31_p100_phase3_receipt_complete/raw/all.ndjson'
# ... (recipe は docs/output-guide.md §4.5)
PY
```

recipe 本体は [`docs/output-guide.md`](../../docs/output-guide.md) の
「4.5 Tier 2 (slice unmatched) の集計」節に、汎用形 (message pattern と
resourceType 両方でフィルタ可能) で維持。
