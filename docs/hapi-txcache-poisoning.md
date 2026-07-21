# HAPI validator on-disk txCache poisoning

## Executive summary

The HAPI FHIR Validator (`org.hl7.fhir.validation.cli`, tested on 6.9.11 and 6.9.12)
persists **any tx server error other than `CODESYSTEM_UNSUPPORTED`** — including
`SERVER_ERROR` (any HTTP failure such as `java.net.SocketTimeoutException`) and
`NOSERVICE` — to the on-disk `-txCache` directory. Once persisted, the failure is served
back for every subsequent identical request forever, across validator restarts, jar
upgrades, and even after the underlying tx server has fully recovered. Deleting the cache
directory by hand is the only recovery.

This page documents how the failure showed up in this project, what we ruled out, and how
the cache and its lookup work. It links out to concrete before/after evidence.

## Where the failure showed up

Running large validation batches (~178k FHIR R4 resources per pass) against a healthy
HL7 fhirserver instance with JP Core + JP-CLINS packages loaded, six specific
`Composition` resources always returned:

```
Bundle.entry[…].resource/*Composition/*/.type
  java.net.SocketTimeoutException: Read timed out
```

The failure was completely deterministic — the same six Composition ids failed on every
single run — and could not be moved by any of the following configurations:

| Change | Timeout count |
|---|---:|
| baseline (`--chunk 50`, `--parallel 24`) | 6 |
| `--chunk 30` | 6 |
| `-Dsun.net.client.defaultReadTimeout=180000` on the validator JVM | 6 |
| `--parallel 6` (one Bundle per JVM) | 6 |
| `validator_cli.jar` upgraded 6.9.11 → 6.9.12 (the switch to okhttp3 in #2519) | 6 |
| all of the above combined | 6 |

Full logs for each of these are archived in
[`validation-results/2026-07-21_full_v12_p1000/`](../validation-results/2026-07-21_full_v12_p1000/).

## What ruled out the "obvious" explanations

- **fhirserver is not the bottleneck.** Direct `curl` against the same
  `POST /r4/CodeSystem/loinc/$validate-code` (`code=34823-5`, JA `Accept-Language`,
  Japanese `display`) returned in **5–16 ms**. `$expand doc-typecodes` returned in
  **~800 ms**. Nothing at the tx side gets close to any reasonable timeout.
- **Client-side chunking / concurrency is not the bottleneck.** Dropping to 1 Bundle
  per JVM (`--parallel 6`) reproduces the exact same six failures.
- **Client-side JVM socket timeout is not what's firing.**
  `-Dsun.net.client.defaultReadTimeout=180000` had no effect because okhttp3 does not
  honor those system properties. But even before adopting okhttp3 (6.9.11), the same six
  Compositions failed the same way — so the read timeout is being served from cache, not
  from a live socket.

## The actual failure trace

`<txCache>/loinc.cache` contained entries like:

```
{"code" : {
  "coding" : [{"system":"http://loinc.org","code":"34823-5"}],
  "text" : "リハビリテーション実施計画書"
}, "url":"http://hl7.org/fhir/ValueSet/doc-typecodes", ...}
####
e: {
  "error" : "java.net.SocketTimeoutException: Read timed out",
  "class" : "SERVER_ERROR",
  "issues" : { … }
}
```

Every subsequent `validate-code` for the same tuple returns this cached error in
~1 second, without contacting the tx server at all.

## How the cache-poisoning happens

`org.hl7.fhir.r5.terminologies.utilities.TerminologyCache#store` currently persists any
entry whose `errorClass` is anything other than `CODESYSTEM_UNSUPPORTED`:

```java
public void store(CacheToken cacheToken, boolean persistent, NamedCache nc, CacheEntry e) {
    if (noCaching) {
      return;
    }
    if ( !cacheErrors &&
        ( e.v!= null
        && e.v.getErrorClass() == TerminologyServiceErrorClass.CODESYSTEM_UNSUPPORTED
        && !cacheToken.hasVersion)) {
      return;
    }
    CacheEntry previous = nc.map.put(cacheToken.key, e);
    if (persistent) {
      …
      nc.dirty = true;
      … save(nc, now);
    }
}
```

`TerminologyServiceErrorClass` already exposes the semantic that would fix this:

```java
public boolean isInfrastructure() {
    return this == NOSERVICE || this == SERVER_ERROR || this == VALUESET_UNSUPPORTED;
}
```

but nothing in `TerminologyCache` consults it.

## Confirming it is the cache

Backing up the current `-txCache` directory and re-running validation on **the same
data** against **the same fhirserver instance** produced **0 timeouts** — the six
Compositions all validated cleanly in 0.04–1.5 s each on the live tx server.

Full before/after logs:

- Before (poisoned cache): [`validation-results/2026-07-21_full_v12_p1000/`](../validation-results/2026-07-21_full_v12_p1000/) — 6 timeouts across all seven configurations tried
- After (cache cleared): [`validation-results/2026-07-21_full_v14_p1000/`](../validation-results/2026-07-21_full_v14_p1000/) — 0 timeouts

Individually replaying each of the six Compositions against a freshly-cleared cache also
produced 0 timeouts:

| Composition id | Live response time |
|---|---:|
| `comp-ENC-POP-000033-224923531116-187` | 1.51 s |
| `comp-ENC-POP-000270-188036175455-107` | 0.20 s |
| `comp-ENC-POP-000380-231140288681-119` | 1.28 s |
| `comp-ENC-POP-000411-281839974939-149` | 1.27 s |
| `comp-ENC-POP-000546-245245476108-135` | 0.04 s |
| `comp-ENC-POP-000631-093553807940-85`  | 0.04 s |

## Recovery today

Clearing the `-txCache` directory before running the cluster is the only recovery for a
cache that has already been poisoned. This project's `scripts/hapi-cluster.sh` accepts a
`HAPI_TX_CACHE` env; wipe that directory (`rm -rf "$HAPI_TX_CACHE"`) before
`hapi-cluster.sh start` if you see repeated `SocketTimeoutException` errors on tuples
that a direct `curl` shows the tx server is happily answering.

## Upstream fix

A minimal guard in `TerminologyCache#store` using the existing `isInfrastructure()`
marker prevents future poisoning. Reported upstream with a JUnit reproduction and the
patch attached.

## Notes

- These findings are independent of any of this project's own fhirserver patches —
  clearing the cache alone restores clean operation on unmodified fhirserver.
- The r4 and r4b copies of `TerminologyCache` in `org.hl7.fhir.core` have a similar
  `store` shape and would benefit from the same guard, though we have only reproduced
  against the r5 implementation (which the validator uses internally regardless of the
  target FHIR version).
