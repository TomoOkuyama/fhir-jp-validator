# 2026-07-21 v14 — cleared `-txCache` run (after)

This is the "after" side of the pair v12 / v14 that isolates the HAPI validator
on-disk txCache poisoning documented in
[../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md).

## What changed vs. v12

**Only one thing.** The on-disk `-txCache` directory was backed up and wiped:

```bash
mv .hapi-cache/tx-cache .hapi-cache/tx-cache.v13.bak
mkdir -p .hapi-cache/tx-cache
./scripts/hapi-cluster.sh stop
HAPI_TX="http://localhost:8181/r4" ./scripts/hapi-cluster.sh start
```

Everything else was identical to
[../2026-07-21_full_v12_p1000/](../2026-07-21_full_v12_p1000/):

- Same `validator_cli.jar` **6.9.12**
- Same fhirserver image (same `-tx` URL)
- Same 178,818-resource dataset (byte-for-byte identical NDJSON files)
- Same `scripts/parallel-validate.py --chunk 30 --parallel 24` invocation
- Same JVM and same package versions

## Result

| pass | file | elapsed | rps | error | timeouts |
|---|---|---:|---:|---:|---:|
| rest | `raw/rest.meta.json` + `raw/rest.stdout.log` | 10.9 min | 273 | 26,238 | **0** |

**Timeouts went from 6 to 0.** The six specific `Composition` resources that
timed out in every v12 configuration now validate cleanly against the same
fhirserver:

| Composition id | live response time |
|---|---:|
| `comp-ENC-POP-000033-224923531116-187` | 1.51 s |
| `comp-ENC-POP-000270-188036175455-107` | 0.20 s |
| `comp-ENC-POP-000380-231140288681-119` | 1.28 s |
| `comp-ENC-POP-000411-281839974939-149` | 1.27 s |
| `comp-ENC-POP-000546-245245476108-135` | 0.04 s |
| `comp-ENC-POP-000631-093553807940-85`  | 0.04 s |

## About the 26k other errors

Those are a genuine data-side issue (`text/plain; charset=utf-8` not in the
`MimeType` value set) that had been **hidden** by the same `-txCache` in prior
runs — the previous cache held stale `success` entries for that tuple. They are
not related to the HAPI validator bug this v12/v14 pair is about; they are
mentioned only to explain why v14's rest error count is higher than v12's
even though the timeouts disappeared.

## Root cause

Established in [../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md):
`org.hl7.fhir.r5.terminologies.utilities.TerminologyCache#store` persists any
`ValidationResult` whose `errorClass` is anything other than
`CODESYSTEM_UNSUPPORTED`, including `SERVER_ERROR` (any HTTP failure at the tx
client, e.g. `java.net.SocketTimeoutException`) and `NOSERVICE`. Once written,
those entries are served back for every subsequent identical request forever.
`TerminologyServiceErrorClass#isInfrastructure()` already flags exactly the
classes that should be excluded from the store; nothing in `TerminologyCache`
consults it.

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log` — the single rest pass
- `raw/rest.ndjson` — full OperationOutcome NDJSON (git-ignored due to size)
