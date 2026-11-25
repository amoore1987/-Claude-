#!/usr/bin/env python3
"""
Build the missing "shop by occasion" collections for jenjenivive.com.

Regenerated 2026-09-12 against the LIVE Shopify catalogue (live-catalogue.json:
120 ACTIVE product_type:Book titles) and the live collection list, replacing an
earlier version built from the stale 114-book scrape in js/books-data.js.

Two findings from the live audit changed this spec:

1. The store already has 35 collections, including a mood layer (12 `mood-*`
   collections) AND a search-facing occasion layer (funny-gifts-for-dad,
   funny-gifts-for-mum, funny-halloween-books, lgbtq-funny-books,
   rude-stocking-fillers, adult-books-that-look-like-childrens-books).
   Most of what an occasion audit would recommend is already built.

2. Every storefront collection already carries a hand-written SEO title and
   meta description - the mood collections included. `mood-hen-do` is already
   "Hen Party Books - Funny Adult Gifts for the Bride"; `mood-hormones` is
   "Funny Menopause Books - Cheeky Adult Gifts for Women". Display name and SEO
   title are already correctly decoupled. There is no SEO remediation to do.
   The only null-SEO collections are discount-eligible,
   new-arrivals-discountable and for-shopify-performance-tracking, which are
   internal utility collections and should stay unindexed.

What remains genuinely missing across all 35 collections: six gift occasions
with real UK search demand and books already in the catalogue to fill them.
Those six are defined below.

Every product GID is validated against live-catalogue.json, so a stale or
mistyped handle fails the build rather than shipping a broken collection.
"""
import csv
import json
import pathlib
import sys

OUT = pathlib.Path(__file__).resolve().parent
FOOTER = "Free UK delivery over £25."

# Handles present in the live catalogue but not yet placed by this spec.
# They belong in EXISTING collections, which is an editorial call for the
# store owner, so they are reported rather than silently assigned.
UNPLACED_NEW_TITLES = {
    "the-bloody-fairy-godmother": "suggest mood-hormones (period humour)",
    "the-newlywed-survival-guide": "suggest mood-hen-do / mood-couples",
    "ive-always-wanted-a-bbc-the-search-for-a-big-black-cock": "suggest mood-couples",
}

OCCASIONS = [
    dict(
        handle="funny-vasectomy-gifts",
        title="Vasectomy Gifts",
        seo_title="Funny Vasectomy Gifts | Rude Books for the Snip | Jen Jenivive",
        seo_description="Funny vasectomy gifts for a man about to lose his best friends. Rude picture "
                        "books with innocent covers, signed by the author. " + FOOTER,
        target_query="funny vasectomy gift",
        intro="Someone you love is booked in for the snip. He is being very brave about it. "
              "This is the shelf you raid on the way to the waiting room.",
        trade_safe=True,
        books=["snip-happens", "my-best-friends-are-balls",
               "our-best-friend-dicky-my-best-friends-are-balls",
               "my-best-friends-are-balls-go-caving",
               "my-best-friends-are-balls-the-adventure-continues",
               "my-best-friends-are-balls-colouring-book-1", "the-missing-ball",
               "andys-salty-nuts", "a-z-of-balls", "i-love-balls",
               "who-will-hold-my-balls-the-who-will-adult-series",
               "betty-swollocks", "anita-seballs"],
    ),
    dict(
        handle="funny-divorce-and-breakup-gifts",
        title="Divorce & Break-Up Gifts",
        seo_title="Funny Divorce & Break-Up Gifts | Rude Books | Jen Jenivive",
        seo_description="Funny divorce and break-up gifts for a friend who needs a laugh more than a "
                        "casserole. Rude picture books from £12.99. " + FOOTER,
        target_query="funny divorce gift",
        intro="Flowers say sorry. A rude picture book says you are going to be absolutely fine, "
              "and also here is a drawing of a beaver.",
        trade_safe=True,
        books=["andrew-no-mates", "the-lonely-little-worm", "my-beaver-hates-wood",
               "the-dusty-clam", "rosie-a-girls-bestfriend", "the-knuckle-shuffle"],
    ),
    dict(
        handle="inappropriate-baby-shower-gifts",
        title="New Baby & Baby Shower",
        seo_title="Inappropriate Baby Shower Gifts | Funny Books | Jen Jenivive",
        seo_description="Inappropriate baby shower gifts that look exactly like a nursery book and "
                        "very much are not. £12.99 each. " + FOOTER,
        target_query="inappropriate baby shower gift",
        intro="It looks exactly like a nursery book. It gets shelved with the nursery books. "
              "It is discovered, out loud, roughly four months later.",
        trade_safe=False,
        books=["my-husband-spreads-his-seed", "the-creampie", "colins-creampies",
               "janes-juicebox", "the-little-bean"],
    ),
    dict(
        handle="funny-retirement-gifts",
        title="Retirement Gifts",
        seo_title="Funny Retirement Gifts | Rude Books | Jen Jenivive",
        seo_description="Funny retirement gifts for someone with a lot of free time coming up. "
                        "Cheeky picture books about gardening, golf and clocks. " + FOOTER,
        target_query="funny retirement gift",
        intro="Forty years of service, one carriage clock, and now an alarming amount of free time. "
              "Give them something to do with it.",
        trade_safe=True,
        books=["my-big-clock", "the-knuckle-shuffle", "andrew-no-mates",
               "graham-the-gardener-trims-a-neat-bush", "barry-the-beaver-photographer",
               "my-great-adventure"],
    ),
    dict(
        handle="rude-valentines-gifts",
        title="Valentine's Day",
        seo_title="Rude Valentine's Gifts | Funny Books for Him & Her | Jen Jenivive",
        seo_description="Rude Valentine's gifts that beat a card and a meal deal. Cheeky picture "
                        "books with innocent covers, £12.99. " + FOOTER,
        target_query="rude valentines gift",
        intro="A card is £4.99 and goes in the bin. This is £12.99 and gets brought out at dinner "
              "parties for years.",
        trade_safe=False,
        books=["the-pearl-necklace", "get-nailed", "coming", "edging", "riding",
               "the-tasty-taco", "my-magnificent-erection"],
    ),
    dict(
        handle="body-confidence-funny-books",
        title="Body Confidence",
        seo_title="Funny Body Confidence Books for Adults | Jen Jenivive",
        seo_description="Funny body confidence books for adults who would rather laugh about it. "
                        "Affectionate, filthy and beautifully illustrated, £12.99. " + FOOTER,
        target_query="funny body positive gift",
        intro="Everybody has a thing they are quietly self-conscious about. These are for the people "
              "who would rather turn theirs into a punchline than a problem.",
        trade_safe=False,
        books=["my-fat-ass-funny-adult-picture-book", "itty-bitty-titty-committee",
               "my-teeny-tiny-ween", "my-fat-pussy", "my-fat-cock", "look-at-my-boobies",
               "wendys-wobblers", "my-big-bushy-bush"],
    ),
]


def main():
    live = json.loads((OUT / "live-catalogue.json").read_text())["books"]
    errors, spec, pairs, rows = [], [], [], []
    seen = set()

    for occ in OCCASIONS:
        if occ["handle"] in seen:
            errors.append(f"duplicate collection handle: {occ['handle']}")
        seen.add(occ["handle"])
        if len(occ["seo_title"]) > 70:
            errors.append(f"{occ['handle']}: seo_title {len(occ['seo_title'])} chars (>70)")
        if len(occ["seo_description"]) > 165:
            errors.append(f"{occ['handle']}: seo_description {len(occ['seo_description'])} chars (>165)")

        products = []
        for h in occ["books"]:
            if h not in live:
                errors.append(f"{occ['handle']}: handle not in live catalogue: '{h}'")
                continue
            products.append({"handle": h, "gid": f"gid://shopify/Product/{live[h]}"})
        if not products:
            errors.append(f"{occ['handle']}: no valid products")

        spec.append({**{k: v for k, v in occ.items() if k != "books"},
                     "url": f"/collections/{occ['handle']}",
                     "product_count": len(products),
                     "products": products})
        rows.append({"handle": occ["handle"], "title": occ["title"],
                     "target_query": occ["target_query"], "seo_title": occ["seo_title"],
                     "seo_description": occ["seo_description"], "intro": occ["intro"],
                     "product_count": len(products),
                     "trade_safe": "yes" if occ["trade_safe"] else "no"})
        for p in products:
            pairs.append({"collection": occ["handle"], "product_handle": p["handle"], "gid": p["gid"]})

    if errors:
        print("BUILD FAILED:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        return 1

    (OUT / "occasion-collections.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    for name, data in (("occasion-collections.csv", rows), ("collection-products.csv", pairs)):
        with open(OUT / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader(); w.writerows(data)

    placed = {p["product_handle"] for p in pairs}
    print(f"OK  {len(spec)} collections to create, {len(pairs)} product placements")
    print(f"    live catalogue: {len(live)} active books; {len(placed)} distinct titles placed here")
    print(f"    new live titles left for existing collections ({len(UNPLACED_NEW_TITLES)}):")
    for h, note in UNPLACED_NEW_TITLES.items():
        print(f"      {h} -> {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
