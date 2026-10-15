# The Wapiti Bugle

Live site: https://wapitibugle.com · Repository: wapitibugle/news

A GitHub Pages news selection for American readers. Hourly public-feed collection, a searchable permanent archive, and an optional budget-controlled AI editor.

## Editorial direction

Prioritize U.S. elections and polling, people exercising power, institutional scrutiny, investigations, campaign money, courts, national policy/economics, consequential science, medicine, AI, and major international developments with U.S. or global consequences. No sports, celebrity gossip, games, routine foreign local government, or isolated overseas tragedies. Public-policy hard news involving a celebrity can qualify on substance. Apply evidence standards across parties, without copying sensational framing from aggregation sites.

Target 35–50 new selections daily: initial edition of up to 35 when suitable reporting is available, target 45 by day's end, hard maximum 50 per Chicago calendar day. Never invent coverage to fill a quota. Homepage eligibility ends 24 hours after the original publisher timestamp. Headline clicks open the publisher's story in a new tab. Sources/context expand inline. There is no separate Lead or Standards page. A static red `!!` marks an expressly assessed major development, not verified truth.

The Daily Brief carries main coverage. Worth a Second Look highlights up to five substantive discovery stories. Monthly archive shards and permanent IDs are retained without deliberate expiry. Out-of-scope early launch selections were removed at the owner's request during calibration. Finite GitHub capacity will eventually require archive/search infrastructure changes.

## AI activation — owner steps

The implementation is installed, but **no paid calls occur without a private API key**. Local runs cannot make paid calls; only the serialized main-branch GitHub Actions workflow can do so.

1. Sign into https://platform.openai.com/ and check API billing. ChatGPT subscription billing is separate.
2. Use a dedicated OpenAI project for this publication. Enable API billing or fund it. If using prepaid credits, leave automatic recharge disabled unless you deliberately want it.
3. Create a project API key. Do not paste it into chat, code, configuration, an issue, or a log.
4. In GitHub, open **Settings → Secrets and variables → Actions → New repository secret**.
5. Name it **OPENAI_API_KEY**; paste the key into the secret value and save.
6. Tell the maintainer the secret is saved. The next hourly workflow can activate automatically; a supervised first run should verify API/model access and the actual response format. A billing balance alone does not guarantee model access.

Secret setup: https://github.com/wapitibugle/news/settings/secrets/actions

No API key has been committed. Only the collection step receives this secret. Pull-request checks never receive it. Public website packaging uses an explicit allowlist of generated pages, search indexes and assets; it does not publish the ledger, cache, configuration, environment, or source files. The public repository does contain budget metadata and editorial decision records, not credentials.

## Budget controls

- Authorized ceiling: **$20 per UTC calendar month** for this integration. The code stops new reservations at **$19**, leaving a $1 buffer. Aim is around $10; a daily allowance spreads it across the month. Important context audits can use part of the additional room.
- Model locked to `gpt-6.1-sol`, standard processing. No model-controlled tools, paid search, file storage, conversation history, or automatic paid retries.
- Conservative accounting uses $3/million input and $15/million output tokens, above the documented standard rates at implementation. It ignores caching discounts. These are budget guard rates, not a claim about the exact provider bill.
- Before each call, reserve a conservative input bound (UTF-8 request bytes plus protocol headroom) and the entire 2,400-token output allowance, including reasoning. The ledger must be successfully committed **and pushed** before the request is sent.
- Settled usage replaces the reservation only after reported counts are validated. Timed-out or uncertain requests retain their full reservation and suspend further AI calls. A cancelled runner leaves a durable pending reservation that prevents silent retries.
- Missing/corrupt ledgers, unknown models, excessive configuration limits, failed checkpoints, or unresolved charges fail closed. The free collector continues. Never delete or reinitialize the ledger to clear an error; inspect and reconcile the corresponding API usage first.
- Cached decisions avoid repeated assessments of the same headline/feed excerpt. Up to 12 fresh candidates and four calls per hourly run. Selection and context auditing each consume a call.
- Pricing must be rechecked **by November 15, 2026**. After that date AI pauses automatically until the checked rates and expiry are deliberately updated. Basic collection continues.
- These controls govern this workflow, not unrelated account/project usage or charges from a copied key. Use a dedicated project/key. Provider billing budgets should be an additional alert, not the only spend safeguard.

Budget state: `data/ai-ledger.json`. Decision cache: `data/ai-cache.json`. Run status: `data/status.json`. The status reports conservative accounted spending, including unresolved reservations; it is not a provider invoice.

## What the AI does and does not establish

The editor evaluates bounded publisher headlines/excerpts and, where accessible, public article paragraphs. It obeys robots.txt, skips explicitly marked paywalls, follows redirects only to configured publisher hosts, and does not log in or bypass access restrictions. When article text is inaccessible, it can rank a headline but cannot claim it read the article.

Structured decisions set relevance, priority, a discovery-section suggestion, and related-event hints. Grouping needs reciprocal model decisions within the same batch and a bounded publication-time gap. Grouping or publisher count never establishes independent corroboration.

Generated context requires a short exact supporting passage from supplied evidence and a separate model request that audits the whole proposed explanation. Rejected, incomplete, uncited, or unaudited context is not displayed. Major AI markers require exceptional priority, substantive article text, and accepted contextual evidence. Both passes use the same model; this is a second check, not independent reporting or a guarantee of accuracy.

AI context is labeled **AI-assisted context**. Publisher headlines remain **source-reported**, even after AI assessment. Only explicit human claim-review records can produce **Human reviewed**. AI never writes into human review records or claims to have independently fact-checked an article.

### Medical evidence standard

Publish hard science, retain study limitations, and distinguish animal/lab findings from human trials. Do not promote pseudoscience or manufacture false balance. Automated headline flags cover disputed medical claims and RFK/Kennedy medical assertions. Those items remain withheld unless a real human review supplies cited evidence, critical context and `scientific_assessment: evidence-based-critique`. A headline containing “debunked” does not automatically pass. Criticism/satire must still be factual. Genuine vaccine/clinical research is not excluded merely for discussing medicine.

This gate is intentionally conservative. The system can operate unattended by withholding material it cannot support rather than asking the owner to approve each story. Headline screening and model audits remain imperfect.

## Human corrections and exceptional reviews

`data/reviews.json` maps permanent story IDs to decisions. Verification requires `status: verified`, an ISO `reviewed_at`, and nonempty `claims` with supporting `urls` already present in the story's `sources`. Add primary evidence to the source record before citing it. `context` must be supported by those sources.

`tier: lead` places a human-reviewed major story at the top of the brief with `!!`; it does not create an empty section. `tier: second` selects a discovery story. `status: withdrawn` with a `correction` keeps a visible tombstone and preserves the ID. Never set human-reviewed status based on model output alone.

## Operation and recovery

Collection is scheduled at 17 minutes past each hour. GitHub schedules are best-effort and can be delayed or disabled after inactivity. The most recent successful collection time is visible on the site. If all feeds fail, the previous deployment remains. Individual feed failures are displayed.

If AI status is `missing_key`, add the private secret after enabling billing. For `uncertain_request` or `unresolved_request`, compare the reserved request time to provider usage; settle conservatively or retain the full charge before clearing suspension. Keep the original entry for auditability. Do not reset the entire ledger. For `pricing_review_due`, verify current official pricing before extending the date. A failure or budget pause does not stop free feed publication.

Actions workflow: https://github.com/wapitibugle/news/actions/workflows/news.yml
API docs: https://developers.openai.com/api/docs/guides/structured-outputs
Pricing: https://developers.openai.com/api/docs/pricing

## Local checks

Python 3.12+; no third-party packages required.

```sh
python -m unittest discover -s tests -v
python scripts/pipeline.py
python scripts/build.py
python -m http.server 8000 --directory dist
```

Local collection always skips paid AI. Tests use fake keys and injected responses, never real API requests. A live first call is still necessary after billing, secret storage and model access are confirmed.
