# counter: Spec

Status: data model approved by Avi, 2026-10-16. Phase 1 built in dev, see
[backlog.md](backlog.md). Data model: [data_model.md](data_model.md). Process and rules:
[building_an_app.md](../building_an_app.md).

## 1. What counter is

Counter is a small capability service for Avi's own sites. His static pages
(mostly GitHub Pages repos, some inside this Django site) load a tiny JS
snippet. The snippet sends events to counter over REST, and can ask counter
for numbers and for which of Avi's own apps to advertise.

It is for Avi. It is not a product and not a public site. It can be shared
with others later, but that is not a goal now.

## 2. What it does

1. **Counts.** Page views first. Unique visitors second (a random anonymous id
   kept in the browser; IP is optional and low priority). Clicks and custom
   interactions use the same event mechanism.
2. **Returns statistics.** Plain code over database rows: totals, per page,
   per day, top pages. A page can ask for its own count and show it.
3. **Serves promos.** For a site and page, returns which of Avi's apps or
   features to advertise. Promo clicks are tracked as events (low priority).
4. **Dashboard.** Only Avi sees it, signed in with his babook login.
5. **Track this site (phase 2).** In the GUI Avi registers a site. Counter
   makes its identifier and produces the exact snippet. Claude then inserts it
   into the repo (local checkout or `gh`), commits and pushes. Counter itself
   holds no GitHub credentials.

## 3. Decisions so far (Avi, 2026-10-16)

- Every site has its own identifier (a public key in the snippet).
- Security is deliberately light: sites are small, abuse is not a concern,
  and a flood of fake hits is acceptable.
- Only Avi sees the dashboard. Pages may show their own count.
- Unique visitors: nice to have, second priority.
- Promo click tracking: low priority.
- URL path: `/counter/`.
- No AI. Statistics are plain code.

## 4. What it is not

Not a full analytics suite, not public, not an ad network, no AI, and it
never edits GitHub on its own.

## 5. Phases

1. Counting: sites, events, stats API, snippet, dashboard.
2. Promos and click tracking.
3. "Track this site" workflow.

## 6. How a page uses it

```html
<script defer src="https://babook.co.il/counter/c.js" data-site="KEY"></script>
<p>This page: <span data-counter="views"></span> views,
   <span data-counter="uniques"></span> unique.
   Whole site: <span data-counter="views" data-counter-scope="site"></span></p>
<a href="/x" data-counter-click="download">Download</a>
```

`counter.track("name")` records a custom event from a page's own script. On
localhost the snippet counts nothing and only reads, unless the script tag
has `data-allow-local`.

## 7. API

Public, no login, key in the request, any origin allowed:
`POST /counter/api/hit/` (JSON body, sent as text/plain), `GET
/counter/api/stats/<key>/?path=`, `GET /counter/api/promo/<key>/?path=`.

Owner side, Avi only, browsable at `/counter/api/`: full CRUD on sites,
pages, events, promos, placements, plus `sites/<id>/stats/`.

## 8. Rules specific to counter

- Fail soft: a failed hit or stats call never breaks the host page.
- Never store a raw IP.
- The dashboard is English and left to right: it is a tool for Avi, not a
  Hebrew-first product page.
- The site key is an identifier, not a secret. Anyone can add a hit to a site
  whose key they have seen; that was accepted on purpose.
