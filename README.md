# The Wapiti Bugle

A static GitHub Pages newspaper with an hourly, persistent RSS selection pipeline.
Custom domain: **wapitibugle.com**. Owner: **wapitibugle/news**.

## Current implementation

- Hourly collection at 17 minutes past the hour (GitHub schedules are best-effort).
- 45-story daily target, a 35-story initial edition when enough suitable reporting is available, hard maximum 50 new selections per Chicago calendar day. Early editions contain fewer stories. Never pad missing coverage with invented stories.
- Rotation between nine interests and source publishers. Source selection is configurable in `config.json`; no ideology score or engagement optimization.
- Three provisional tiers: The lead (human-reviewed), The daily brief (attributed headlines), Worth a second look (up to five science, technology, culture, outdoors selections). Original detailed tier definitions were not available in the imported conversation.
- Similar headline grouping with conservative word and number matching. Grouping is only a discovery aid, not independent corroboration.
- Explicit source-reported labels, cited human-review records, expandable context and correction/withdrawal support.
- Homepage eligibility ends 24 hours after the source publication time. Browser hides expired cards each minute, even if collection fails.
- Indefinite archive retention in monthly JSON shards; static monthly pages, permanent story URLs, and full-history browser search with 30-result pagination. No retention deletion policy.
- Public artifact allowlist: generated HTML, search indexes, stylesheet, JavaScript. Never publish an environment file or API credential.
- **Paid AI is not implemented or enabled. Cost is $0.** Code fails closed if AI is toggled on or the configured limit exceeds $10. This is a safe first release, not a completed AI editorial engine.

## Enable publication (one-time owner setup)

1. In this repository go to **Settings → Pages**.
2. Under **Build and deployment → Source**, select **GitHub Actions**.
3. In **Actions**, select **Collect news and publish → Run workflow → main**. Alternatively rerun a failed deployment after enabling Pages.
4. Check that the workflow passes. The initial address is `https://wapitibugle.github.io/news/` until a custom domain is configured.
5. If persistence fails due to repository policy, grant GitHub Actions write access to repository contents in Settings → Actions → General, or adjust the repository rules to permit the archive commit. The workflow requests only the permissions it needs.

The connector supports repository contents and workflows, but not the Pages administrative configuration or your domain registrar. These settings may require the owner to complete them.

## Custom domain

First configure **Settings → Pages → Custom domain → wapitibugle.com** and save. Verify domain ownership in the account Pages settings if offered. Then at your registrar/DNS provider, configure:

| Type | Name | Value |
| --- | --- | --- |
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | wapitibugle.github.io |

Keep unrelated mail and verification records. Resolve conflicting web-hosting records deliberately. After DNS and the certificate are ready, enable **Enforce HTTPS**. With Actions-based publication, GitHub ignores CNAME files; the custom domain is configured in Pages settings instead.

Official instructions: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

## Run locally

Python 3.12+; no packages, paid services, database, or API key required.

```sh
python -m unittest discover -s tests -v
python scripts/pipeline.py
python scripts/build.py
python -m http.server 8000 --directory dist
```

To rebuild without fetching feeds, run `python scripts/build.py` directly. `pipeline.py --offline` is for testing collection logic against existing records and marks the collection time unavailable; do not use it to report a live collection.

## Human editorial review

Reviewers must read the supporting reporting and preferably original records. A headline match, ideological agreement, or repeated wire copy is not sufficient verification. Automated checks do not verify facts, claims, quotes, or article bodies.

`data/reviews.json` maps a permanent story ID to an editorial decision:

```json
{
  "STORY_ID": {
    "status": "verified",
    "reviewed_at": "2026-10-15T15:00:00Z",
    "tier": "lead",
    "claims": [
      {"text": "A narrowly stated checked claim", "urls": ["EXACT_SOURCE_URL_FROM_STORY"]}
    ],
    "context": "A concise explanation supported by those sources.",
    "correction": ""
  }
}
```

Each evidence URL must already be linked on the story. Add primary evidence to that story's `sources` record before citing it in a review, using the same source metadata shape as the feed entries. Only mark verified after a real review. Use `status: withdrawn` with a correction to publish a tombstone, retaining the identity. Use `tier: second` for a reviewed discovery choice. The site limits the active lead and discovery displays to five each; unverified stories cannot enter the lead tier.

## Honest launch limitations / remaining work

- This is an RSS aggregator, not automated investigative verification. The lead section stays empty until a human reviews claims. Deep context is written by a reviewer, not fabricated.
- Source rotation provides variety of interests and publishers, not proof of ideological or geographic balance. The initial pool is limited; continue expanding reputable primary and independent reporting sources.
- Original extensive editorial rules were not retrievable; confirm tier definitions, category weighting, exclusion rules, and verification thresholds before treating this as the final editorial product.
- Paid AI integration is deliberately absent. A future implementation needs a dedicated secret API key, explicit model pricing, bounded inputs/outputs, pre-call maximum-cost reservations persisted before requests, no automatic retries after uncertain outcomes, serialized runs, a durable monthly ledger, alerts and a fail-closed cutoff below $10. A provider project budget alone is not a guaranteed hard cap. Never place a key in browser code, config, logs, or committed data.
- Publisher feeds can fail, mislabel content, change article headlines, or syndicate the same report. Source count never changes factual verification status. Existing selections preserve their original headline and timestamp; source corrections require an editorial update.
- The archive grows without deliberate pruning, but GitHub Pages/repository capacity is finite. Search loads the monthly metadata indexes on demand and will eventually need a scalable external index. Preserve permanent IDs and shard history during any migration.
- GitHub can delay schedules and automatically disable inactive schedules. Check Actions periodically and re-enable if needed. The site displays its last successful collection time and feed failures.

Workflow deployment documentation: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## Audience and editorial scope (updated October 15, 2026)

American readers are the primary audience. Prioritize U.S. elections, polling, competitive races, voting rules, national policy, and the U.S. economy. International stories need a clear global or U.S. consequence (for example the Ukraine war, major geopolitical developments, security, trade, energy, and supply chains). Exclude sports, celebrity/entertainment coverage, routine foreign local government, foreign domestic economic commentary, and isolated overseas tragedies. Public-policy hard news involving a celebrity can qualify on its substance.

The `editorial` rules in config apply to both new collection and homepage rendering; out-of-scope prelaunch selections were removed at the owner’s request while coverage is being calibrated; future out-of-scope candidates are rejected before archival. Elections receive dedicated priority within the daily quota. This initial relevance filter is headline-based and imperfect; it does not read whole articles or guarantee comprehensive polling coverage. Specific polling numbers require cited poll methodology and dates before any synthesis is published.

## Reader interest refinement (October 15, 2026)

The reader’s highlighted Drudge screenshot is a topic-preference reference, not evidence for its claims or a request to copy its tone. Elevate public accountability, officeholder scrutiny, investigations, court fights, citizenship/immigration policy, campaign finance and polling, U.S. military activity, consequential geopolitics, and science/AI/medical research with human consequences. Lower routine photo features and agency event previews. Apply these interests regardless of party or ideological direction.

Selection now prioritizes consequential subject matter before category rotation; interests remain balanced within a priority band. ProPublica, KFF Health News, and Science News expand the source pool beyond the original general-news feeds. Medical and AI research headlines remain attributed reports, not endorsed conclusions or independently verified findings.

## Medical evidence standard

Publish hard science. Do not promote pseudoscience or manufacture false balance between supported findings and unsupported medical assertions. Reporting on disputed medical claims, including RFK Jr. claims about medicine, must undergo a real human evidence review and provide factual critical context before publication. An automatically detected headline containing “debunked” is not enough.

Flagged headlines fail closed: publication requires valid cited human-review claims, a nonempty contextual explanation, and `scientific_assessment: evidence-based-critique` in `data/reviews.json`. This gate applies at collection and homepage build time. It is a conservative headline screen, not a complete medical fact-checker. Criticism or satire must not invent facts; study design, uncertainty, and limitations still matter. Genuine clinical research is not excluded merely because it discusses vaccines or medicine.
