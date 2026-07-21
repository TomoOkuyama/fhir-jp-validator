# 2026-07-21 v12 — poisoned `-txCache` run (before)

This is the "before" side of the pair v12 / v14 that isolates the HAPI validator
on-disk txCache poisoning documented in
[../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md).

## Setup

- `validator_cli.jar` **6.9.11** and **6.9.12** (both reproduced identically)
- FHIR R4 (`-version 4.0.1`)
- `-tx http://localhost:8181/r4` pointing at HL7 fhirserver (Pascal, healthy)
- `-txCache` reused from earlier v6-era runs, on-disk state carried forward
- IG: JP Core 1.2.0 / JP-CLINS 1.12.0 (Japanese LOINC display translations installed)
- Client: `scripts/parallel-validate.py`

## Data

- Same 178,818-resource **synthetic** JP Core / JP-CLINS dataset used for every rest
  pass in this folder — produced by `clinosim` (a FHIR simulation data generator);
  the underlying patterns are Japanese-hospital-shaped, but the resources themselves
  are entirely synthetic, **not real patient data**
  (26 NDJSON files, ~620 MB; not committed — regenerated from source when needed).

## Passes

Four configurations were run against the same data:

| pass | file | chunk | parallel | HAPI JVM flag | error | timeouts |
|---|---|---:|---:|---|---:|---:|
| baseline | `raw/rest.meta.json` + `raw/rest.stdout.log` | 50 | 24 | default | 48 | **6** |
| smaller chunk | `raw/rest_chunk30.*` | **30** | 24 | default | 48 | **6** |
| longer socket timeout | `raw/rest_httpto180.*` | 50 | 24 | `-Dsun.net.client.defaultReadTimeout=180000` | 48 | **6** |
| low concurrency | `raw/rest_p6.*` | 30 | **6** | (same) | 48 | **6** |

All four passes returned the **same 48 errors**, of which **6 were the same
`java.net.SocketTimeoutException: Read timed out`** on the same six `Composition`
resources (identifiers listed in
[../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md)).
The remaining 42 errors are unrelated eReferral slice constraints from JP-CLINS
profiles.

## What was ruled out at this point

- fhirserver latency — direct `curl` against
  `POST /r4/CodeSystem/loinc/$validate-code` with `Accept-Language: ja`,
  `code=34823-5`, `display=リハビリテーション実施計画書` returned in **5–16 ms**
- Client concurrency and chunking
- Client JVM socket timeout

## Wrong hypothesis at the time (kept for the record)

The Japanese `summary.md` in this folder was written before running the cache-cleared
pass. It attributed the 6 timeouts to a HAPI validator "internal validation path"
triggered by `Composition.type = LOINC 34823-5` with no `meta.profile`. That
hypothesis was invalidated by v14 (see below).

## What actually happened

v14 (same data, same fhirserver, same `validator_cli.jar`, `-txCache` wiped)
returned **0 timeouts**. Each of the six previously-hanging Compositions
validated cleanly in 0.04–1.5 s. The 6 timeouts in this v12 run were being
served out of `<txCache>/loinc.cache` — where a previous run had persisted the
`SocketTimeoutException` as a `SERVER_ERROR` `CacheEntry`. Full explanation in
[../../docs/hapi-txcache-poisoning.md](../../docs/hapi-txcache-poisoning.md).

## Raw logs

- `raw/rest.meta.json` / `raw/rest.stdout.log` — baseline
- `raw/rest_chunk30.meta.json` / `raw/rest_chunk30.stdout.log`
- `raw/rest_httpto180.meta.json` / `raw/rest_httpto180.stdout.log`
- `raw/rest_p6.meta.json` / `raw/rest_p6.stdout.log`
- `raw/obs.meta.json` / `raw/obs.stdout.log` — Observation pass (0 errors)
- `raw/*.ndjson` — full OperationOutcome NDJSON (git-ignored due to size)
