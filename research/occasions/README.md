# Shop by Occasion — live collection layer

**Status: the six collections in this spec are CREATED and LIVE on jenjenivive.com
as of 2026-09-12.** This directory is now the record of what was built and why,
plus the follow-ups that were deliberately not done.

## What the live audit found (and what it corrected)

This spec was originally written against `js/books-data.js` — a 114-book scrape
that is out of date. Pulling the live store changed two conclusions:

**1. The occasion layer was already half-built.** The store has 35 collections:
a 12-strong mood layer (`mood-*`) *and* a search-facing occasion layer
(`funny-gifts-for-dad`, `funny-gifts-for-mum`, `funny-halloween-books`,
`lgbtq-funny-books`, `rude-stocking-fillers`,
`adult-books-that-look-like-childrens-books`). Most of what a generic occasion
audit would recommend already existed.

**2. There was no SEO to fix.** Every storefront collection already carries a
hand-written SEO title and meta description — the mood collections included.
`mood-hen-do` is already titled *"Hen Party Books – Funny Adult Gifts for the
Bride"*; `mood-hormones` is *"Funny Menopause Books – Cheeky Adult Gifts for
Women"*. Display name and SEO title were already correctly decoupled, which is
exactly the right pattern. The only collections with null SEO are
`discount-eligible`, `new-arrivals-discountable` and
`for-shopify-performance-tracking` — internal utility collections that should
stay unindexed. **No SEO changes were made.**

What remained genuinely missing across all 35 collections: six gift occasions
with real UK search demand and books already in the catalogue to fill them.

## The six collections created

| Collection | URL | Products | Target query | Trade safe |
| --- | --- | ---: | --- | --- |
| Vasectomy Gifts | `/collections/funny-vasectomy-gifts` | 13 | funny vasectomy gift | ✅ |
| Divorce & Break-Up Gifts | `/collections/funny-divorce-and-breakup-gifts` | 6 | funny divorce gift | ✅ |
| New Baby & Baby Shower | `/collections/inappropriate-baby-shower-gifts` | 5 | inappropriate baby shower gift | ❌ |
| Retirement Gifts | `/collections/funny-retirement-gifts` | 6 | funny retirement gift | ✅ |
| Valentine's Day | `/collections/rude-valentines-gifts` | 7 | rude valentines gift | ❌ |
| Body Confidence | `/collections/body-confidence-funny-books` | 8 | funny body positive gift | ❌ |

45 product placements. Each was created with an SEO title, meta description and
intro copy in brand voice, sorted by best-selling.

**Trade safe** flags sets a mainstream gift-shop buyer or a workplace Secret
Santa can be shown. Three of the six qualify.

## Files

| File | Use |
| --- | --- |
| `build_occasions.py` | Source of truth. Edit `OCCASIONS`, re-run to regenerate. |
| `live-catalogue.json` | 120 ACTIVE `product_type:Book` titles → product GIDs, pulled 2026-09-12 |
| `occasion-collections.json` | Full spec including every product GID per collection |
| `occasion-collections.csv` | One row per collection with SEO fields |
| `collection-products.csv` | One row per collection/product pair |

```bash
python3 research/occasions/build_occasions.py
```

The build **fails** on a handle missing from the live catalogue, a duplicate
collection handle, an over-length meta title/description, or an empty
collection — so the spec can't drift from the catalogue silently. Refresh
`live-catalogue.json` from the Admin API before re-running after new titles ship.

## Still to do

**1. Verify Online Store publication.** The API token used here lacks
`read_product_listings`, so publication status could not be confirmed. Check in
Shopify admin that all six are published to the Online Store channel before
expecting them to rank.

**2. Add the new titles to existing collections.** Three books live in the
catalogue but are not in any collection this spec created. They belong in
existing curated collections, which is an editorial call:

| Title | Suggested home |
| --- | --- |
| `the-bloody-fairy-godmother` | `mood-hormones` (period humour) |
| `the-newlywed-survival-guide` | `mood-hen-do` / `mood-couples` |
| `ive-always-wanted-a-bbc-the-search-for-a-big-black-cock` | `mood-couples` |

**3. Internal linking.** New collections need links from the footer and from
relevant product pages, not only a nav dropdown. They also need adding to the
sitemap with indexing requested.

**4. Personalisation cross-sell.** Several £12.99 books are the base versions of
£24.99 personalised titles (`fionas-fanny`, `taras-taco`, `beths-smelly-beaver`,
`wendys-wobblers`, `bens-baguette`, `kelly-s-kebab`, `simons-sword`,
`evans-eggplant`, `jakes-wiener-has-lice-a-day-in-the-life-of-a-vet`). Each base
product page should carry a "put your own name on it, £24.99" block. That is a
2x price upgrade on traffic that already exists, and it is the single highest-
margin change left in this area.

**5. Leave seasonal pages up year-round.** Valentine's needs to be indexed and
aged before February. Taking it down after the season resets it.

## What to measure

Non-brand organic sessions and organic revenue per collection. Ignore rankings as
a headline metric. Give it 8–12 weeks — search compounds slowly, then suddenly.
