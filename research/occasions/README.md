# Shop by Occasion — collection spec

A search-acquisition layer for jenjenivive.com. **This sits underneath the existing
"shop by mood" browse, it does not replace it.** The two do different jobs:

| | Shop by mood | Shop by occasion |
| --- | --- | --- |
| Who it serves | Someone already on the site | Someone on Google who has never heard of Jen |
| Job | Help them pick → raises AOV | Win the click → brings new traffic |
| Organised by | Vibe / theme | What the buyer types before they buy |
| Success metric | Products per order | Non-brand organic sessions |

Mood is merchandising. Occasion is distribution. A mood page can't rank for
*"funny vasectomy gift"* because nothing on it — URL, title tag, H1, body copy —
matches the phrase. That's the gap these 18 collections fill.

## Why this is the highest-ROI change available

Every acquisition channel the brand has today is **rented**. TikTok (~197K),
Instagram (~161K) and TikTok Shop all run on someone else's algorithm and can be
throttled overnight. Organic search is the only channel that is **owned**, compounds
over time, and reaches buyers at the exact moment they have a wallet open and a
problem ("what do I get him for the snip").

The catalogue is already sitting on that demand — 114 books organised by anatomy,
which is the one thing nobody searches for. Reorganising by occasion costs nothing
but collection setup.

Secondary benefit: it fixes choice paralysis. A buyer landing on *Vasectomy Gifts*
sees 11 books, not 114.

## Files

| File | Use |
| --- | --- |
| `build_occasions.py` | Source of truth. Edit the `OCCASIONS` list, re-run to regenerate. |
| `occasion-collections.json` | Full spec incl. every product per collection |
| `occasion-collections.csv` | One row per collection — collection setup + SEO fields |
| `collection-products.csv` | One row per collection/product pair — bulk assignment |

Regenerate with:

```bash
python3 research/occasions/build_occasions.py
```

The build **fails** on an unknown product handle, a duplicate collection handle, an
over-length meta title/description, or a collection with no products — so the spec
can't drift from the catalogue silently.

## The 18 collections

| Collection | Target query | Products | Trade safe |
| --- | --- | ---: | --- |
| Vasectomy Gifts | funny vasectomy gift | 11 | ✅ |
| Hen Party Gifts | funny hen party gifts | 12 | ❌ |
| Menopause Gifts | funny menopause gift | 6 | ✅ |
| Secret Santa Under £15 | secret santa gifts under £15 | 12 | ✅ |
| Christmas Gifts | funny christmas gifts for adults | 9 | ❌ |
| Father's Day & Dad | funny fathers day gift | 8 | ✅ |
| Mother's Day & Mum | funny mothers day gift | 7 | ❌ |
| Milestone Birthdays | funny 40th birthday gift | 6 | ❌ |
| Pride & LGBTQ+ | funny lgbtq gifts | 9 | ❌ |
| Divorce & Break-Up | funny divorce gift | 6 | ✅ |
| New Baby & Baby Shower | inappropriate baby shower gift | 5 | ❌ |
| Retirement Gifts | funny retirement gift | 6 | ✅ |
| Anniversary & Couples | rude anniversary gift | 8 | ❌ |
| Valentine's Day | rude valentines gift | 7 | ❌ |
| Body Confidence | funny body positive gift | 7 | ❌ |
| Hobbies & Occupations | funny gardener gift | 8 | ✅ |
| Stocking Fillers Under £10 | funny stocking fillers under £10 | 6 | ❌ |
| Put Their Name On It | personalised rude gift | 9 | ❌ |

**Trade safe** flags the sets that can be shown to mainstream gift-shop buyers and
used for workplace Secret Santa. Seven of the eighteen qualify — that's the
starting shortlist for the wholesale conversation, and it means the wholesale range
already exists without commissioning anything new.

## Titles deliberately left out

86 of 114 books land in at least one occasion. The other 28 are the pure-innuendo
titles with no gifting hook — *Fisting*, *Squirting*, *The Glorious Hole*, the
*Who Will…?* series and so on. That is the correct result, not a gap: those titles
are **mood-layer inventory**. They convert on browse and on TikTok, not on search
intent, and forcing them into an occasion page would dilute the page for the
titles that do convert there.

Two follow-ups worth doing separately:

1. **Series pages.** Six of the orphans are the *Who Will…?* series and several
   others are sequels (*Helen's Hole* / *Helen's Hole Refilled*, *Ron's Rocket* ×2).
   Series collections capture "book 2" and sequel searches and drive multi-buy.
2. **Personalisation cross-sell.** Several orphans (*Fiona's Fanny*, *Tara's Taco*,
   *Beth's Smelly Beaver*) are the £12.99 base versions of £24.99 personalised
   titles. They're kept out of *Put Their Name On It* on purpose so that page
   converts at the higher price — but each base product page should carry a
   "put your own name on it, £24.99" block. That's a margin upgrade on traffic
   that already exists.

## Implementation notes

- **Manual collections, not automated rules.** These are editorial groupings; a tag
  rule will get them wrong.
- **Put the intro copy above the product grid.** A collection page with no body text
  will not rank. The `intro` field is written for that slot, in brand voice.
- **One collection per URL, permanently.** Don't reuse a seasonal handle for a
  different occasion next year — it throws away the ranking.
- **Seasonal pages stay live year-round.** Christmas and Valentine's pages need to
  be indexed and aged *before* the season; taking them down resets them.
- **Internal links matter.** Link the occasion pages from the footer and from
  relevant product pages, not only from a nav dropdown.
- **Add these to the sitemap and request indexing** once the copy is live.

## What to measure

Non-brand organic sessions, and organic revenue per collection. Ignore rankings as
a headline metric. Give it 8–12 weeks before judging — search compounds slowly and
then all at once.
