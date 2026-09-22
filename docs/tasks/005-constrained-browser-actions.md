# Task 005 — Constrained Browser Actions

Target version: **0.5.0**

## Purpose and execution order

The generic collector can perform a short, strictly typed sequence of browser actions
before the unchanged Task 004 price extraction. One browser session is still created
per collector request and items are still handled sequentially:

1. validate and navigate to the item URL;
2. validate the resulting URL;
3. execute configured actions in declaration order;
4. validate the current URL after every click;
5. extract and parse the price with the Task 004 selector and parser.

Omitting `actions`, or supplying an empty list, has the Task 004 behavior.

## Options contract

`options.browser.actions` is optional and accepts at most ten actions. Every action has
a strict integer `timeout_seconds` from 1 through 30 (default 5) and a strict Boolean
`required` (default `true`). The sum of all configured action timeouts may not exceed 60
seconds. Selectors must be non-blank strings no longer than 2048 characters. Unknown
fields, action types, locator types, and states are rejected. Invalid configuration is
the sanitized global protocol failure `BROWSER_CONFIGURATION_ERROR`.

Only these discriminated shapes exist:

```json
{
  "type": "click",
  "by": "css",
  "selector": "#cookie-accept",
  "timeout_seconds": 5,
  "required": false
}
```

`click` supports `by: "css"` and `by: "xpath"`. It explicitly waits for the element to
be clickable and then clicks it.

```json
{
  "type": "wait_for",
  "by": "xpath",
  "selector": "//div[@id='overlay']",
  "state": "hidden",
  "timeout_seconds": 5,
  "required": true
}
```

`wait_for` supports the same locator types and exactly three states: `present`,
`visible`, and `hidden`. Selenium explicit waits are used; there are no sleeps.

## Required, optional, and error semantics

A timeout or item-local WebDriver error in a required action returns item error
`ACTION_FAILED` with the fixed message `Required browser action could not be
completed.` Processing then continues with the next item. The same safe, item-local
failure in an optional action is skipped and action processing continues.

An invalid Selenium selector is a sanitized global `BROWSER_CONFIGURATION_ERROR`. A
lost session/window or other session-fatal failure is global `COLLECTOR_ERROR`.
Selenium exception text is never included in protocol output. Existing `INVALID_URL`,
`PAGE_LOAD_FAILED`, `PRICE_NOT_FOUND`, and `PRICE_INVALID` behavior remains unchanged.

## URL security boundary

Actions cannot directly navigate. A click can nevertheless cause navigation, so the
collector applies the existing exact-host URL policy to `driver.current_url` after
every successful click. A disallowed redirect produces item error `INVALID_URL` before
any subsequent action or price extraction. Navigation to another explicitly allowed
host continues normally. The existing public-DNS pre-navigation check remains a
baseline rather than a claim of complete DNS-rebinding protection.

The typed union is the command allowlist. JSON cannot select Python/Selenium methods,
expected-condition names, expressions, or code. This prevents the feature from
becoming an arbitrary remote browser automation language.

## Explicitly out of scope

There is no navigation/link-follow action, `send_keys`, login or credential support,
cookie injection or persistence, profile persistence, arbitrary sleep, JavaScript or
`execute_script`, evaluation, custom snippets, iframe/tab/window switching, file
transfer, scrolling, hover, dropdown selection, keyboard action, CAPTCHA/Cloudflare
bypass, proxy, stealth, user-agent spoofing, retry/backoff, screenshot, DOM dump, regex
transform, availability/multiple-price extraction, persistence, queue, or worker.

## Acceptance

Automated tests use fake drivers and injected waits; they make no network calls and do
not start Chrome. Manual Windows acceptance should install/update version 0.5.0 through
the existing updater, run provisioning and offline browser runtime checks, verify
startup preflight and `/health`, then exercise no-action, optional-action,
required-action failure, allowed redirect, and rejected redirect requests end to end.
Confirm the LocalService profile is removed and `driver.quit()` runs after each case,
then exercise rollback to the prior immutable release.
