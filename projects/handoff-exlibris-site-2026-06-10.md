# Handoff — Ex Libris site update (10 June 2026, session 2)

## RESUME INSTRUCTION
> "Here's a handoff from a previous Claude session. Read it, then continue from NEXT STEPS. [paste this document]"

**Open this session on the repo `lasource69/james-mcgrath-website` (Astro 6 / TS / Tailwind v4, Cloudflare Pages).** The prior session was mistakenly attached to `pinescript-agents` and could not reach the site repo, Cloudflare, or the open internet.

## CONTEXT
Ex Libris show, Old Battersea House, 11–20 June 2026. James logs artwork sales by chatting to Claude on mobile; the site must update without him touching the repo. Site reads Airtable **at build time only** — no rebuild = stale site.
- Site: https://james-mcgrath.com · works page `/works/london-2026/`
- Airtable base `appyde7xgU9D1VAOj` · London 2026 table `tblxrveO62owwQGWi` · Status field `fldZdNP2ok9liyklb` · Edition Sales `tblh0N3LgphfWRRE1` · Deliveries `tblQOu6dY9rXCRRxu`
- Status options: Available / Reserved / Sold / NFS → site labels map from these.

## VERIFIED CORRECT IN AIRTABLE (checked live 10 June, do not redo)
- **Strahov's Flowers** → Sold (Robbie Crittall, £6,600)
- **Clouds after Lunch** → Sold (Sophia Brown, £12,000, invoice EL-2026-001)
- **Folding Flowers** → Reserved (soft hold for Robbie, **expires 4pm Thu 11 June**)
- **A View, On Loan** → Available (edition 1/5 sold to Robbie; print stays available, 4 of 5 remain)
- Deliveries table pre-loaded with the three sales.

## STATE OF THE LIVE SITE
Stale until a rebuild runs. **Recommended manual fix (phone, no repo):** Cloudflare → Workers & Pages → the Pages project → Deployments → newest → ⋯ → **Retry deployment** (or **Create deployment** on `main` if Retry reuses cached data). James may already have done this — verify first.

## NEXT STEPS (in the james-mcgrath-website repo)
1. **Confirm the build fetches LIVE Airtable**, not committed/cached JSON. Check the Astro data layer (`src/`, any `airtable` fetch / content loader, `astro.config`). If it reads a checked-in JSON snapshot, that's the root cause of staleness — fix it to fetch at build time.
2. **Verify deploy is git-push driven** on Cloudflare Pages, then confirm the four works render correctly: Strahov's Flowers = Sold, Clouds after Lunch = Sold, A View On Loan = Available (ideally "1 of 5 sold" via Edition size − Edition Sales count).
3. **Reserved display decision (James):** recommendation is leave **Folding Flowers showing "Available"** until the hold firms up (it expires 4pm Thu 11 June; a public "Reserved" that reverts looks bad). Sold works show "Sold". Confirm with James before coding the label logic.
4. **Persistent deploy hook + self-updating pipeline:** create a Cloudflare Pages deploy hook (Settings → Builds & deployments → Deploy hooks, branch `main`), then an Airtable automation on London 2026 (trigger: Status is any of Sold/Reserved → action: POST to the deploy hook URL). Document the hook URL in the repo README. This is the core goal — site self-rebuilds minutes after each sale, no repo interaction.
5. **Fix `contact.astro` exposed Gmail** (mcgrathjames1@gmail.com) — obfuscated mailto or a form.
6. **Git health:** prior session flagged a broken `.git` situation (`.git` outside OneDrive on the laptop). Confirm the repo is healthy before pushing; develop on a feature branch and open a draft PR.

## ENVIRONMENT NOTES
- Airtable MCP works. GitHub MCP works only for the attached repo. Outbound internet is blocked by network policy (`Host not in allowlist`) — verify the live site via the Cloudflare dashboard / James, not `curl`. No `wrangler` or Cloudflare creds in-session; Cloudflare dashboard steps are done by James on mobile.
- Show closes 20 June; sold works stay on the walls until then.
