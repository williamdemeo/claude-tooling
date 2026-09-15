---
name: deploying-to-cloudflare-pages
description: Publish a statically built site to Cloudflare Pages by direct upload from GitHub Actions, and cut a custom domain over to it — for a private repository, or anywhere GitHub Pages will not serve. Use when a site must move off GitHub Pages or GitLab Pages, when a repository goes private and its Pages site goes dark, or when wiring wrangler into a workflow. Covers the deploy script and its tested failure modes, the secret guard Actions will not let you write the obvious way, _redirects and _headers (including precedence and hostname scoping), the DNS cutover order with rollback, verifying a deployment rather than a build, and seeing what the edge injects into a response that no build-time check can see.
---

# Deploying to Cloudflare Pages

Worked end to end on williamdemeo.org, 2026-09-11, moving a 279-file MkDocs
site from GitHub Pages to Cloudflare Pages after the repository went private.
Every command and claim below was run and measured that day.

## When this is the answer

GitHub Pages on the Free plan serves **only public repositories**.  Make a
user-site repository private and the site goes dark within the hour:
`has_pages` flips to false and the URL 404s.  There is no setting to change.
Cloudflare Pages does not read the repository at all — Actions builds the
site and uploads the files — so the source stays private.

Confirm the diagnosis before acting:

    gh api repos/OWNER/REPO --jq '{private, has_pages}'
    curl -sS -o /dev/null -w '%{http_code}\n' https://OWNER.github.io/

## The shape

Keep whatever already builds the site (here, `nix build`).  Replace only the
publish step.  Do **not** use Cloudflare's own Git build: it is a second
build environment to keep honest, and it cannot run Nix.

Put the deploy in a script, not a `run:` block — it needs shell for the
idempotent project-create anyway, and a script can be tested.  The script
should exit **0 deployed, 1 the deploy failed, 2 could not run**; a missing
secret and a failed upload send you to different places.

    wrangler pages project list                      # guard
    wrangler pages project create NAME --production-branch main
    wrangler pages deploy DIR --project-name NAME --branch BRANCH \
      --commit-dirty=true

`--commit-dirty=true` is required: the built directory is untracked, so the
tree wrangler inspects is always dirty and it would otherwise prompt.

**Pin wrangler and take it from npm**, not from a Nix pin: `npx --yes
wrangler@4.129.0`.  It is a client for a hosted API, so being current matters
more than being reproducible, and nixpkgs lags (25.05 carried 4.17.0 in
September 2026).  Leave a `WRANGLER` override so a local wrangler can drive
the same script.  Set `WRANGLER_SEND_METRICS=false`.

**The project is created by the first run.**  The API token is a repository
secret and deliberately lives on no one's machine, so the job is the only
thing holding it.  Guard the create on `project list`, and make a *failing*
`list` exit 2 rather than falling through to a create — otherwise an expired
token surfaces as a confusing create failure.

## The secret guard Actions will not let you write

`secrets` is **not** a context a step's `if:` may read, and a step's own
`env:` is not reliably in scope for its own `if:`.  Hoist a boolean to the
job:

    jobs:
      build:
        env:
          HAVE_CLOUDFLARE: ${{ secrets.CLOUDFLARE_API_TOKEN != '' }}
        steps:
          - name: Deploy a preview
            if: github.event_name == 'pull_request' && env.HAVE_CLOUDFLARE == 'true'

Carrying the answer rather than the secret also keeps the token out of the
environment of every third-party action in the job.

Put the preview deploy in the **existing** PR job if that job already builds
the site.  A workflow of its own pays for a second runner and a second build
to upload the same bytes, and private-repository minutes are metered.

## Asking for the two secrets

`CLOUDFLARE_API_TOKEN`: dashboard → profile menu → My Profile → API Tokens →
Create Token → **Custom token**.  One permission, **Account → Cloudflare
Pages → Edit**.  No zone permissions — the custom domain and DNS are set by
hand.  `CLOUDFLARE_ACCOUNT_ID`: Workers & Pages → Overview, right column.

Send the person the repository's **Settings → Secrets and variables →
Actions** page.  Do **not** tell them to run `gh secret set NAME` inside an
agent shell: with no TTY `gh` does not prompt, it reads stdin, gets EOF, and
sets an **empty** secret with no output.  And `gh secret list` shows names
only — it cannot tell a good secret from an empty one, so the real check is
the first deploy.

## _redirects and _headers

Both live at the deployment root and Cloudflare serves neither.

**`_redirects` beats static assets.**  Cloudflare: "redirects are always
followed, regardless of whether or not an asset matches the incoming
request."  So a rule wins over a file at the same path — which is what lets a
real 301 override a meta-refresh stub, and which also means a rule whose
source is a real page makes that page **unreachable**.  Generate the file
from the same rule set the rest of the build uses, and check the two agree.

Format `/from  /to  301`; limits 2,000 static and 100 dynamic rules.
**Trailing slashes are distinct sources** — `/a` and `/a/` are different.
Emitting only the slashed form is fine: Pages normalizes `/a` to `/a/` when
`a/index.html` exists, so the slashless form arrives in two hops.  Measure
it rather than assuming.

**`_headers` can be scoped by hostname**, which is the one thing worth
setting.  Cloudflare adds `X-Robots-Tag: noindex` to *preview* deployments
itself but **not** to the production `pages.dev` subdomain, which is
otherwise a second indexable copy of the site:

    https://:project.pages.dev/*
      X-Robots-Tag: noindex

    /*
      X-Content-Type-Options: nosniff
      Referrer-Policy: strict-origin-when-cross-origin

Limits: 100 rules, 2,000 characters a line.  Skip a CSP unless you are ready
to generate per-build hashes; most theme frameworks emit inline script.

## The cutover, in order

1. **Deploy to `PROJECT.pages.dev` first** and verify everything there.  No
   DNS has changed, so nothing is at risk.
2. **Move the canonical origin before the DNS change, not after.**  Whatever
   renders canonical links and the sitemap (`site_url` for MkDocs) plus every
   absolute URL in generated artifacts — an `llms.txt`, a CV's contact URL,
   any committed PDF.  Moving it afterwards means the domain's first live
   minutes serve pages naming a dead address as canonical.
   Beware a blanket string rewrite: an address like
   `owner.github.io/OtherProject/` is a *different* repository's project
   Pages site and may still be live.
3. **Record the existing DNS for rollback.**  Export the zone or note the
   apex and `www` rows verbatim — with a proxied record the origin is not
   visible from outside, so this cannot be recovered later.
4. **Add the custom domains.**  Workers & Pages → project → Custom domains.
   Cloudflare proposes a `CNAME @ → PROJECT.pages.dev`; that is correct, not
   a mistake — CNAME flattening makes an apex CNAME legal here, and there is
   no A-record alternative.  **Add `www` as its own custom domain**, even if
   it CNAMEs to the apex: the Pages project has to know the hostname or it
   will not serve it.  (A `www` that inherits the apex but is unknown to the
   *old* host is the usual cause of a `www` that was already broken.)
5. **Turn on Always Use HTTPS** (SSL/TLS → Edge Certificates).  Check it
   first; it is often off.
6. Rollback is restoring the recorded rows.  Keep the old deployment's domain
   verification in place until the cutover has held, because removing it is
   what ends the one-edit rollback.

## Verify the deployment, not the build

A build check cannot tell you the host obeys any of it.  Write a live checker
and hold two distinctions:

- **A 200 is not "fine".**  Report the status, the `Location`, and where the
  chain ended — not a boolean.  A redirect source answering 200 means the
  rule did not fire and a stub was served instead, which is a specific cause.
- **A failure is not "dead".**  Reserve the error case for "no HTTP response
  happened" (DNS, TLS, refused, proxy denial, timeout).  Every HTTP response,
  a 503 included, is a success with a finding.  In Python, `HTTPError`
  subclasses `URLError`, so catch it first or the two collapse.

Follow redirects by hand (`HTTPRedirectHandler.redirect_request` returning
`None`) so the chain survives into the report.

Then check **every file the build wrote** against the host.  It is the only
check that sees an upload which dropped a PDF, a font, a social card or a
`llms.txt`, and no map check will ever look at those.  Expect a redirect at a
stub's path and a 404 for `_headers` and `_redirects`.

**Run the checker against the old host before trusting it.**  Ours failed
129 of 152 map checks and 254 of 281 asset checks against the pre-cutover
site — a checker that passes there is measuring nothing.

## What the host injects, and how to see it

A Cloudflare-proxied zone can add script tags to every HTML response at the
edge, downstream of any build; Web Analytics automatic injection and email
obfuscation both do.  Nothing in the repository records it, and a build-time
audit that serves the built directory from `127.0.0.1` cannot see it by
construction, because those bytes never pass through Cloudflare.  On
williamdemeo.org that blindness hid a live analytics beacon on every page for
months, and the issue asking which analytics to install turned out to be an
issue about one already running.

**curl will tell you there is nothing there.**  Injection is gated on the
request's `Accept` header, and curl's default `*/*` is not offered one:

    curl -sS https://example.org/ | grep cloudflareinsights                          # nothing
    curl -sS -H 'Accept: text/html' https://example.org/ | grep cloudflareinsights   # the tag

A request with no `Accept` header at all, which is what Python's `urllib`
sends, is injected too.  So a probe of any edge behavior has to send what a
browser sends, or it measures the edge's opinion of curl.  A real headless
browser is better still, and it is the only thing that shows where the beacon
reports to, and whether a cookie is set.

**Date it with the Internet Archive, and use a control.**  The archive stores
pages as they were served, injections included:

    curl -sS "http://web.archive.org/cdx/search/cdx?url=example.org&fl=timestamp,statuscode&collapse=timestamp:6"
    curl -sSL --compressed "https://web.archive.org/web/<timestamp>id_/https://example.org/"

The `id_` suffix returns the original bytes rather than the replay-rewritten
page.  A snapshot without the injection proves nothing on its own, since the
crawler may not have been offered one; look in the same snapshot for a
*different* Cloudflare injection (`/cdn-cgi/l/email-protection`,
`/cdn-cgi/scripts/`) as the control.  With the control present and the thing
you are hunting absent, the absence is real.

**Pin what it adds, in both directions.**  Compare the other-origin URLs the
host serves against the ones the build wrote, and name per host exactly what
that host is expected to add.  An injection that is not on the list fails, and
a listed one that stopped arriving fails too: "the analytics quietly stopped"
is as much a defect as "something new appeared", and an allowlist catches only
the second.  Match by prefix, because an injected beacon URL carries a version
segment that rotates with its `integrity` hash.

Parse the HTML rather than grepping it.  `<a href>` and `<link href>` are the
same three characters and a page of prose is mostly the first kind; and a
`<link>` whose `rel` is `canonical` or `alternate` is a statement about the
page, not a request it makes, so counting it reports every page's own
canonical URL as an other-origin fetch whenever the check runs against a
preview host.

**Injection is scoped to the zone.**  A Pages project's own `*.pages.dev`
hostname is not the zone, so a preview is served exactly as built.  Measure
that rather than assuming it; it is worth knowing either way, because it means
preview traffic never enters the numbers.

## Two traps worth their own line

**A generated redirect's target is not its source path.**  If a plugin
rewrites URLs (MkDocs' blog plugin serves `blog/posts/2014-02-13-isotopy.md`
at `/blog/isotopy/`), only the build knows where a page landed.  Read the
generated `_redirects` rather than re-deriving a target from configuration;
re-deriving is silent, because the file exists and the URL is served by
nothing.

**A test that writes an executable at runtime must not use
`#!/usr/bin/env bash`.**  A Nix sandbox need not have `/usr/bin/env`, and
`patchShebangs` cannot reach a file that does not exist until the test runs.
Write `printf '#!%s\n' "$BASH"`.  Worse than the failure is how it hides: a
stub that cannot execute "fails", and tests asserting *failure* then pass for
the wrong reason.  Probe that the stub runs before taking any verdict, and
print the captured output on every failed assertion — without it a red CI run
says "expected 0, got 2" and costs a round-trip to explain.
