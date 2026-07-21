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

Running large validation batches (~178k FHIR R4 resources per pass — a **synthetic**
JP Core / JP-CLINS dataset produced by `clinosim`, **not real patient data**) against a
healthy HL7 fhirserver instance with JP Core + JP-CLINS packages loaded, six specific
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

## Reproducing this locally

Everything below assumes you have Docker, Python 3, and a JDK 17+ on `PATH`. It is
independent of the rest of this project — no JP data or `docker-compose` needed.

### 1. Grab a stock `validator_cli.jar`

```bash
curl -L -o /tmp/validator_cli.jar \
  https://github.com/hapifhir/org.hl7.fhir.core/releases/download/6.9.12/validator_cli.jar
java -jar /tmp/validator_cli.jar 2>&1 | head -1
# → FHIR Validation tool Version 6.9.12 (…)
```

Any tx server the validator will accept is fine; the reproduction just needs a live
one for HAPI to boot against. The two easiest options are:

- **HL7 fhirserver** as this project ships in
  [`scripts/setup-fhirserver.sh`](../scripts/setup-fhirserver.sh) (Pascal, Rosetta-friendly)
- **Any other approved tx endpoint** you already have

### 2. Cause one tx call to fail

Point the validator at a proxy that either delays or errors on the first
`$validate-code` request. A minimal Python one is enough:

```python
# save as delay-proxy.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request, sys, time, threading

UPSTREAM = sys.argv[1]                 # e.g. http://localhost:8181
PORT     = int(sys.argv[2])            # e.g. 9999
HITS = {"n": 0}
LOCK = threading.Lock()

class H(BaseHTTPRequestHandler):
    def _fwd(self, method):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        if method == "POST" and "$validate-code" in self.path:
            with LOCK:
                HITS["n"] += 1
                n = HITS["n"]
            if n == 1:
                time.sleep(40)          # first call: exceed HAPI's tx read timeout
        req = urllib.request.Request(
            UPSTREAM + self.path,
            data=body,
            method=method,
            headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            self.send_response(r.status)
            for k, v in r.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
    def do_GET(self):  self._fwd("GET")
    def do_POST(self): self._fwd("POST")
    def log_message(self, *a, **kw): pass

HTTPServer(("127.0.0.1", PORT), H).serve_forever()
```

```bash
python3 delay-proxy.py http://localhost:8181 9999 &
```

### 3. Start the validator with a fresh cache

```bash
rm -rf /tmp/tx-cache-repro && mkdir -p /tmp/tx-cache-repro
java -Xmx2g -jar /tmp/validator_cli.jar server 9001 \
  -version 4.0.1 \
  -tx http://localhost:9999/r4 \
  -txCache /tmp/tx-cache-repro &
```

### 4. Send one validation, then inspect the cache

```bash
# Minimum Composition wrapped in a Bundle. Adjust "code"/"display" to whatever
# your tx server can look up (LOINC 34823-5 is used below as an example).
cat > /tmp/bundle.json <<'JSON'
{ "resourceType": "Bundle", "type": "collection", "entry": [
  { "fullUrl": "http://example.org/Composition/repro",
    "resource": { "resourceType": "Composition", "status": "final",
      "type": { "coding": [{ "system": "http://loinc.org", "code": "34823-5" }] },
      "date": "2026-01-01",
      "author": [{ "reference": "Practitioner/example" }],
      "title": "repro",
      "section": [{ "code": { "coding": [{ "system": "http://loinc.org", "code": "29308-4" }] } }]
    }
  }
]}
JSON

curl -s -X POST http://localhost:9001/validateResource \
  -H "Content-Type: application/fhir+json" \
  --data-binary @/tmp/bundle.json | python3 -m json.tool | head -40

grep -l 'SocketTimeout\|SERVER_ERROR' /tmp/tx-cache-repro/*.cache
```

You will find the `SocketTimeoutException` (or whichever tx failure the proxy
produced) written to `/tmp/tx-cache-repro/<system>.cache` as a persistent
`SERVER_ERROR` entry.

### 5. Confirm every subsequent call replays the cached failure

Restart the proxy so it responds instantly to *every* call:

```bash
pkill -f delay-proxy.py
python3 delay-proxy.py http://localhost:8181 9999 &      # HITS resets, no more delay
```

Then re-run the same validation — the response still contains
`java.net.SocketTimeoutException: Read timed out` and no request reaches the
proxy. The failure is being served from the cache indefinitely.

### 6. Confirm the recovery

```bash
rm -rf /tmp/tx-cache-repro/* && curl -s -X POST http://localhost:9001/validateResource ...
```

The same validation now completes without the timeout — the underlying tx server
was always healthy.

## Recovery today (production workaround)

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
