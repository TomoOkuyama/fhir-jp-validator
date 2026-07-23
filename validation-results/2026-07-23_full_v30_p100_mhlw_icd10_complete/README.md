# 2026-07-23 v30 — Phase 1 導入直後 (tx-cache warm) run

## 位置付け

Phase 1 (MHLW ICD-10 2013 完全版 15,586 concept) を fhirserver に load した直後、
**HAPI on-disk txCache は v29 warm 状態** で v29 と同 dataset を再検証。

**結論**: cache warm で古い fragment 判定を hit し続けたため Phase 1 効果ほぼ見えず (v29 との
差 -6 warning のみ)。**真の効果測定は cache wipe 後の v30b** を参照。

## Result

| 指標 | 値 |
|---|---:|
| error 総数 | 4,701 (v29 4,695 → +6 誤差) |
| warning 総数 | 52,185 (v29 52,191 → -6 誤差) |
| 所要 | 18.6 min |

## 参考

- 真の Phase 1 効果測定: [`../2026-07-23_full_v30b_p100_mhlw_wipe_cache/`](../2026-07-23_full_v30b_p100_mhlw_wipe_cache/)
- v29 baseline: [`../2026-07-23_full_v29_p100_tx_enabled/`](../2026-07-23_full_v29_p100_tx_enabled/)

## Raw logs

- `raw/all.meta.json` / `raw/all.stdout.log`
