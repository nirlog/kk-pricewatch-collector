# Task 004 — Generic Browser Price Collector

Target version: **0.4.0**.

Task 004 replaces the browser route's deterministic stub with a generic Selenium
single-price collector. It is not a browser-scenario engine and contains no
competitor-specific code.

## Architecture and options

The authenticated protocol request passes from FastAPI to `BrowserCollector`. The
collector validates strict browser options, opens exactly one session through Task
003's `BrowserSessionFactory`, processes items sequentially, and lets the factory quit
the driver and remove its temporary profile. Selenium explicit waits locate the
configured CSS or XPath element; no readiness sleeps or retry loop are used.

```json
{
  "browser": {
    "allowed_hosts": ["example.com", "www.example.com"],
    "price": {
      "by": "css",
      "selector": "meta[itemprop='price']",
      "source": "attribute",
      "attribute": "content"
    },
    "currency": "RUB",
    "decimal_separator": "dot",
    "wait_timeout_seconds": 15,
    "page_load_timeout_seconds": 30
  }
}
```

All `browser` and `price` fields are strict. Hosts are case-normalized, unique exact
matches without wildcards. Waits are limited to 1–60 seconds and page loading to 1–120
seconds. `attribute` is required in attribute mode and forbidden in text mode. Invalid
options yield a sanitized global `BROWSER_CONFIGURATION_ERROR`.

## Price normalization

The first ASCII-numeric token is normalized deterministically with `Decimal`, never
`float`. Ordinary spaces, NBSP, and narrow NBSP are supported. `none` has no decimal
part; `dot` or `comma` selects the only decimal mark. Malformed or ambiguous values are
rejected as `PRICE_INVALID` rather than guessed. Output remains a protocol 1.0 decimal
string.

## Navigation and SSRF baseline

Before every navigation the policy requires HTTP(S), a hostname, no user information,
and an exact allowlist match. Localhost and non-global literal addresses are rejected.
The injected resolver must return one or more addresses, all global. The final URL
after redirects must still use HTTP(S) and an allowlisted host.

This is baseline SSRF protection, not a claim of complete DNS-rebinding protection.
Operators should also enforce suitable host firewall and network egress controls.

## Error semantics and scope

Invalid URLs, navigation failures, missing values, and invalid prices become per-item
`INVALID_URL`, `PAGE_LOAD_FAILED`, `PRICE_NOT_FOUND`, and `PRICE_INVALID` failures.
Other items continue. Session failures become a sanitized global `COLLECTOR_ERROR`.
Protocol failures use HTTP 200; authentication, malformed JSON, and request-model
failures retain normal HTTP statuses. Selenium details, HTML, cookies, paths, secrets,
authorization values, and Pydantic diagnostics are never returned.

The Task 001 stub remains a deterministic test helper but is not the route default.
Task 003's isolated profiles, offline Selenium Manager production configuration,
preflight, LocalService identity, and cleanup remain unchanged. Automated tests use
fake sessions and injected DNS only.

Manual release acceptance remains: exercise one operator-approved public test page on
Windows LocalService, verify text and attribute extraction, profile cleanup, and
outbound firewall policy. Never use real competitor requests in CI.
