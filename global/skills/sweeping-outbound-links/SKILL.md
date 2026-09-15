---
name: sweeping-outbound-links
description: Build or fix a scheduled check that fetches every link a site points off itself and reports only the ones a reader cannot reach. Use when adding link-rot detection to a docs site or CI, when an existing sweep reports dead links that are not dead, or when deciding what a 403, a 429, a 503, a TLS error or a redirect loop should mean. Covers the classification that decides whether anything is reported at all, the per-host threading that avoids earning a 429, the calibration hosts for certificate failures, and the one-tracking-issue reporting that keeps a weekly check from being muted.
---

# Sweeping outbound links

Measured on williamdemeo.org, 2026-09-12: 209 outbound links on 67 hosts.  A
first version reported **7 broken and 5 of the 7 were the checker's fault**.
A weekly check that cries wolf gets muted, and a muted check is worse than no
check, so the classification is the design and everything else is plumbing.

## The three verdicts, and only the first opens an issue

| verdict | means | examples |
| --- | --- | --- |
| `broken` | a reader cannot reach this, and an author can act | 404, 410, 451, 400; 5xx after retries; DNS failure; connection refused; timeout; a redirect loop; an expired, self-signed or wrong-hostname certificate |
| `blocked` | the server will not say, and nothing here can fix it | 401, 403, 407, 429; a certificate chain missing its intermediate |
| `ok` | 2xx at the end of the chain | |

Report all three and gate on one.  Listing the `blocked` ones matters: a link
that *stops* being merely blocked is visible when it happens.

## Certificate failures are not one class

OpenSSL's verify code separates what a browser recovers from and a client does
not.  Calibrate against these four, which is quicker than reasoning about it:

```
about.ifa.hawaii.edu      verify_code=20  'unable to get local issuer certificate'
expired.badssl.com        verify_code=10  'certificate has expired'
wrong.host.badssl.com     verify_code=62  'Hostname mismatch, ...'
self-signed.badssl.com    verify_code=18  'self-signed certificate'
```

Only **20 and 21** are excused: the server did not send the intermediate and a
browser fetches it from the certificate's AIA extension.  Expired, self-signed
and wrong-hostname stop a reader too.  In Python, `reason.verify_code` on the
`ssl.SSLCertVerificationError` (reach it through `URLError.reason`), and
`getattr(..., "verify_code", None)` because a plain `SSLError` has none.

Return a **structured** transport error, not a string: an incomplete chain and
a host that no longer exists read almost the same in a message and mean
opposite things, so the caller needs to sort on a field.

## A redirect loop is usually a cookie handshake

`doi.org` to `link.springer.com` to `idp.springer.com` and back is five hops,
and a client that drops the cookie is sent around again, arriving at
`?error=cookies_not_supported`.  Three DOI links looked dead for exactly that.

Give each request its own `http.cookiejar.CookieJar` through an
`HTTPCookieProcessor` (per call, not shared: a jar shared across a thread pool
is shared state between unrelated hosts), and raise the hop limit to 8.  Then a
loop that *still* does not settle is rot, because a browser caps redirects too.

## 429 is a threading bug before it is a finding

Eight threads over a list sorted by URL put eight simultaneous requests on
whichever host owns the current run of the alphabet.  That is how a sweep earns
a 429 from a host that would have answered every request in sequence.

**Group by host and run one thread per host**, with a small delay between two
requests to the same one.  With 91 of 209 links on `github.com`, that removed
the 429 entirely and cost about forty seconds.

## "Not now" needs more than one ask

Retry an unsettled answer three times with a lengthening pause, and return the
**best** of the attempts rather than the last: a 429 followed by a timeout is
still a rate limit.  Unsettled means a 5xx or a transport failure; a 404, a 403
and a certificate that does not verify are settled, and asking again is rude.

Measured reason for three rather than one: `www.cs.nott.ac.uk` answers 503 and
200 alternately within the same minute, and one retry five seconds later cannot
tell that from a host that is down.

## Read the links out of the built HTML, and only `href`

Not the Markdown: pages rendered from data at build time (a CV from a YAML
file) carry a large share of the outbound links and exist in no source file.
Not the whole built tree either: the theme's bundled JavaScript carried **114**
more URLs here (licence headers, source maps, template strings with `${...}`
still in them), and not one is a link a reader can follow or an author can
repair.  Drop the fragment before deduplicating, and keep the set of pages each
URL appears on so one repair is one repair.

## Reporting: one tracking issue, and say nothing when nothing changed

A weekly comment repeating two links that have been dead since March is how a
tracking issue becomes something to mute.

+  End the report with a fingerprint of the **broken set** (a short hash of the
   sorted URLs) in an HTML comment, invisible in the rendered issue and
   greppable in its source.
+  Keep one open issue, found by exact title.  Compare the fingerprint against
   the newest thing written on it: the last comment, or the body when there is
   none.  Comment only when the set changed; close the issue when it empties.
+  Write the report as Markdown once and use it for both the terminal and the
   issue body, or the two come to disagree.

### Three ways this reporting goes wrong quietly

All three were found by review rather than by testing, and all three are one
line each:

1. **A sweep that exits 0 without printing a report is believed.**  Guard the
   fingerprint's presence on *every* report status, not just the failing one:
   the clean branch closes the tracking issue, so a regression closes an issue
   about links that are still broken.
2. **A tracker that cannot be read looks like a tracker with nothing in it.**
   `gh issue list | head -1` discards the exit status, so an authentication
   blip reads as "no issue is open" and the next branch opens a second one.
   Check the status and exit before any write.  The `issue view` beside it has
   the same defect one line down.
3. **A crash that happens to exit 1** becomes an issue whose body is a stack
   trace.  A report with no fingerprint is not a report; treat it as a check
   that could not run.

Exit 0 whether or not links are broken (the issue is the report), and non-zero
only when the sweep could not run or a write was refused.

## Test the classifier offline

Every case is a constructed answer rather than a request, so the test needs no
network and runs in a sandbox.  This is the part that gets skipped, and it is
the part that decides whether anything is reported at all: the classification
above had no test until a review found two whole classes in the wrong bucket.
