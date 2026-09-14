# Personalised-edition upsell — theme 3.6

Everything here is live on the **unpublished** theme
**Version 3.6 (personalised upsell, Fable)** — `gid://shopify/OnlineStoreTheme/182839968067`,
duplicated from the published Version 3.5 on 2026-09-14.

Preview: `https://jenjenivive.com/?preview_theme_id=182839968067`
(try any of the nine base books, e.g. `/products/bens-baguette`)

## The problem

Nine £12.99 books have a £24.99 personalised twin. The store already had a good
cross-sell module — `sections/jj-pairs-with.liquid`, fed by the `custom.pairs_with`
metafield, rendering image + title + price + a real Add-to-bag — but on every one
of those nine books the three slots held *other £12.99 books*. The 2x upgrade of
the exact book being viewed was never offered in the module that converts. It
appeared only as a plain text link at the very bottom of the description, below
Book Details and below "Want It Signed?", on six of the nine.

## Why it couldn't just be added

The personalised books capture the buyer's name through the **Live Product Options**
app embed, which injects its fields into the main product form. `jj-pairs-with`
builds its **own** minimal add-to-cart form containing only the variant id. Dropping
a personalised book into `pairs_with` as-is would therefore have let customers buy a
£24.99 personalised book straight from the strip **with no name on the order** — a
paid order Jen would have to chase by email, on every sale.

That is the whole reason for the theme change. It has to land before the data does.

## Theme changes (on 3.6 only)

| File | Change |
| --- | --- |
| `sections/jj-pairs-with.liquid` | Personalisation guard; pre-count pass; empty-grid fix |
| `assets/jj-pairs.css` | `--link` button style; 4-up grid; scoped the mobile odd-card rule |
| `templates/product.json` | `max_items` 3 → 4, plus the two new settings |
| `templates/product.sold-on-store.json` | Added the `jj_pairs` section (it had none) |

**The guard.** Any paired product whose `template_suffix` matches the new
`personalise_template` setting (default `sold-on-store` — all nine personalised books
use it) renders as a link to its own product page instead of an Add button, so the
name field is never bypassed. Configurable, and blank disables it.

**Two other fixes in the same file.** The section now counts eligible products before
rendering, which (a) lets it tag the grid `--four` for layout and (b) stops it
emitting an empty `<ul>` with heading and note when every paired product is
unavailable — the old version rendered the shell regardless.

**Layout.** Four cards lay out 2x2 on mobile and 4-across on desktop. The old
`:nth-child(3)` rule that made the third card a full-width row on small screens is
now scoped so it only applies to 3-up, leaving the 3-item layout byte-identical.

## Data change (store-level — applies to BOTH themes)

`custom.pairs_with` on the nine base books now has the personalised edition
**appended as the fourth entry**, keeping all three original order-data pairings.

This is deliberately safe to have done before publishing: the published theme 3.5
has `max_items: 3` and its copy of the section breaks out of the loop at three, so
**the fourth entry does not render on the live site.** It only appears once 3.6 is
published. Verified against 3.5's `templates/product.json` after the write.

| Base book | Personalised twin appended |
| --- | --- |
| bens-baguette | customised-bens-baguette |
| beths-smelly-beaver | customised-beths-smelly-beaver |
| evans-eggplant | customised-evans-eggplant |
| fionas-fanny | customised-fionas-fanny |
| jakes-wiener-has-lice-a-day-in-the-life-of-a-vet | customised-jakes-wiener-has-lice-… |
| kelly-s-kebab | customised-kellys-kebab |
| simons-sword | customised-simons-sword |
| taras-taco | customised-taras-taco |
| wendys-wobblers | customised-wendys-wobblers |

## Before publishing

1. **Preview the nine base books** on 3.6 and confirm the fourth card shows the
   personalised edition at £24.99 with a purple "Personalise it" link, not a pink
   Add button. Check mobile too (2x2).
2. **Click it** and confirm it lands on the personalised product page with the Live
   Product Options name field present.
3. **Check a normal book** (e.g. `/products/fisting`) still shows three cards with
   working Add buttons and the unchanged mobile layout.

## Description links (store-level — done 2026-09-14)

All nine base books now end their description with the same block the original six
used, so the fallback text link is consistent across the set and works on the
published theme today, independent of 3.6:

```html
<p>Want to personalise this book? <a href="/products/customised-XXX">Find the Customised version here.</a></p>
```

Added to `fionas-fanny`, `taras-taco` and `wendys-wobblers`. Descriptions were
re-read immediately before writing and the existing copy left byte-identical — only
the paragraph above was appended.

## Still outstanding

- **The nine personalised books have no `pairs_with` of their own**, so the section
  added to `product.sold-on-store.json` is inert on their pages until populated.
  Best filled with other personalised titles — cross-selling within the £24.99 tier
  rather than down to £12.99.
- **Consider raising the personalised price.** £24.99 for a near-identical unit cost,
  non-returnable, un-discountable and impossible for an Etsy dupe to undercut.
  Comparable personalised gift books sit at £29.99–£34.99.
