#!/usr/bin/env python3
"""
Build the "shop by occasion" collection layer for jenjenivive.com.

Source of truth is the OCCASIONS list below. Every product handle is validated
against the live catalogue scrape in js/books-data.js, so a typo or a delisted
title fails the build instead of shipping a 404 into a collection.

Outputs (written next to this file):
  occasion-collections.json  - full spec, machine readable
  occasion-collections.csv   - one row per collection, for the Shopify admin
  collection-products.csv    - one row per collection/product pair
"""
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent

# --- Occasion definitions -------------------------------------------------
# target_query   what a buyer types into Google before they've heard of Jen
# trade_safe     True if the whole set is mainstream-retail / office friendly
#                (matters for wholesale and for "Secret Santa at work")

OCCASIONS = [
    dict(
        handle="funny-vasectomy-gifts",
        title="Vasectomy Gifts",
        seo_title="Funny Vasectomy Gifts | Rude Books for the Snip | Jen Jenivive",
        seo_description="Funny vasectomy gifts for a man about to lose his best friends. Cheeky illustrated books that look innocent and absolutely are not. Free UK delivery over £25.",
        target_query="funny vasectomy gift",
        intro="Someone you love is booked in for the snip. He is being very brave about it. "
              "These are the books you give him in the waiting room, loudly, in front of other people.",
        trade_safe=True,
        books=["snip-happens", "my-best-friends-are-balls", "our-best-friend-dicky-my-best-friends-are-balls",
               "my-best-friends-are-balls-go-caving", "my-best-friends-are-balls-the-adventure-continues",
               "a-z-of-balls", "i-love-balls", "who-will-hold-my-balls-the-who-will-adult-series",
               "betty-swollocks", "anita-seballs", "my-best-friends-are-balls-colouring-book-1"],
    ),
    dict(
        handle="hen-party-gifts",
        title="Hen Party Gifts",
        seo_title="Funny Hen Party Gifts & Games | Rude Books | Jen Jenivive",
        seo_description="Rude hen party gifts that get read out loud and ruin everyone. Illustrated innuendo books from £12.99. Free UK delivery over £25.",
        target_query="funny hen party gifts",
        intro="The bit of the hen do where someone reads aloud and the room falls apart. "
              "Pick one per guest, or one for the bride and let her find out in public.",
        trade_safe=False,
        books=["sarahs-sausage-party", "claire-goes-to-the-sausage-market", "gobble-my-sausage",
               "spit-or-swallow", "meat-two-veg", "bens-baguette", "evans-eggplant", "simons-sword",
               "hubbys-weapon", "the-local-bike", "the-mattress-actress", "kelly-s-kebab"],
    ),
    dict(
        handle="funny-menopause-gifts",
        title="Menopause Gifts",
        seo_title="Funny Menopause Gifts | Perimenopause Books | Jen Jenivive",
        seo_description="Funny menopause and perimenopause gifts for women who have earned a laugh. Cheeky illustrated books, £12.99. Free UK delivery over £25.",
        target_query="funny menopause gift",
        intro="For everyone currently negotiating with their own thermostat. "
              "Nobody warned her, so the least you can do is make her snort.",
        trade_safe=True,
        books=["peri-normal-activity-a-tale-of-the-perimenopause", "the-dusty-clam",
               "my-beaver-hates-wood", "the-bald-beaver", "ive-got-the-painters-in", "grannys-growler"],
    ),
    dict(
        handle="secret-santa-gifts-under-15",
        title="Secret Santa Gifts Under £15",
        seo_title="Secret Santa Gifts Under £15 | Funny Books | Jen Jenivive",
        seo_description="Secret Santa gifts under £15 that actually get a reaction. Funny illustrated books, £12.99 each. Free UK delivery over £25.",
        target_query="secret santa gifts under £15",
        intro="The office Secret Santa budget is £10 and your reputation is on the line. "
              "These are £12.99, which is close enough, and nobody will forget who drew whose name.",
        trade_safe=True,
        books=["snip-happens", "my-best-friends-are-balls", "the-little-bean", "andrew-no-mates",
               "jakes-wiener-has-lice-a-day-in-the-life-of-a-vet", "i-trip-over-my-wiener",
               "man-vs-bear", "my-big-clock", "where-can-i-sit", "buster-knutt",
               "graham-the-gardener-trims-a-neat-bush", "dads-deck"],
    ),
    dict(
        handle="funny-christmas-gifts-for-adults",
        title="Christmas Gifts",
        seo_title="Funny Christmas Gifts for Adults | Rude Books | Jen Jenivive",
        seo_description="Funny Christmas gifts for adults who never grew up. Cheeky illustrated books and stocking fillers from £6.99. Free UK delivery over £25.",
        target_query="funny christmas gifts for adults",
        intro="Wrap it, put it under the tree, and wait for someone's nan to open it first. "
              "Christmas is the one day a year the whole family is trapped in a room together. Use it.",
        trade_safe=False,
        books=["santas-sack", "mums-christmas-wish", "blow-me-out-a-birthday-book-for-grown-ass-adults-1",
               "the-little-bean", "my-best-friends-are-balls", "snip-happens", "dads-deck",
               "mums-great-tits", "pennys-pumpkins"],
    ),
    dict(
        handle="funny-fathers-day-gifts",
        title="Father's Day & Gifts for Dad",
        seo_title="Funny Father's Day Gifts | Rude Books for Dad | Jen Jenivive",
        seo_description="Funny Father's Day gifts for a dad with a filthy sense of humour. Illustrated innuendo books from £12.99. Free UK delivery over £25.",
        target_query="funny fathers day gift",
        intro="He has enough socks. He has enough novelty beer glasses. "
              "Give him something he will read out at the table and then have to explain.",
        trade_safe=True,
        books=["dads-deck", "my-husband-spreads-his-seed", "snip-happens", "my-big-clock",
               "the-massive-banker", "my-extra-bone", "graham-the-gardener-trims-a-neat-bush",
               "meet-my-friend-little-willy"],
    ),
    dict(
        handle="funny-mothers-day-gifts",
        title="Mother's Day & Gifts for Mum",
        seo_title="Funny Mother's Day Gifts | Rude Books for Mum | Jen Jenivive",
        seo_description="Funny Mother's Day gifts for a mum who swears more than you do. Cheeky illustrated books from £12.99. Free UK delivery over £25.",
        target_query="funny mothers day gift",
        intro="Your mum is filthier than you think. She has simply been waiting for permission.",
        trade_safe=False,
        books=["mums-great-tits", "mums-christmas-wish", "ive-got-the-painters-in", "jugosaurus",
               "wendys-wobblers", "mandys-melons-need-squeezing", "pennys-pumpkins"],
    ),
    dict(
        handle="funny-40th-birthday-gifts",
        title="Milestone Birthdays",
        seo_title="Funny 40th & 50th Birthday Gifts | Rude Books | Jen Jenivive",
        seo_description="Funny 40th and 50th birthday gifts for grown-ups. Cheeky illustrated books, £12.99. Free UK delivery over £25.",
        target_query="funny 40th birthday gift",
        intro="A big round number deserves a big rude book. "
              "Read it out before the speeches so everyone knows what kind of evening this is.",
        trade_safe=False,
        books=["blow-me-out-a-birthday-book-for-grown-ass-adults-1",
               "the-birthday-blowjob-a-story-of-a-candle", "my-big-clock", "the-massive-banker",
               "the-knuckle-shuffle", "my-great-adventure"],
    ),
    dict(
        handle="lgbtq-pride-gifts",
        title="Pride & LGBTQ+ Gifts",
        seo_title="Funny LGBTQ+ & Pride Gifts | Rude Books | Jen Jenivive",
        seo_description="Funny Pride and LGBTQ+ gifts with the innuendo turned all the way up. Illustrated books from £12.99. Free UK delivery over £25.",
        target_query="funny lgbtq gifts",
        intro="Tried and tested on an actual Pride stall, where a group of strangers took turns "
              "reading these to each other and called it the highlight of their day.",
        trade_safe=False,
        books=["scissoring", "the-69-club", "breastfriends", "my-pussycat-needs-a-playmate",
               "lucy-loves-her-pussy", "a-z-of-pussies", "a-z-of-cocks", "rosie-a-girls-bestfriend",
               "flicking-the-bean-1"],
    ),
    dict(
        handle="funny-divorce-and-breakup-gifts",
        title="Divorce & Break-Up Gifts",
        seo_title="Funny Divorce & Break-Up Gifts | Rude Books | Jen Jenivive",
        seo_description="Funny divorce and break-up gifts for a friend who needs a laugh more than a casserole. Books from £12.99. Free UK delivery over £25.",
        target_query="funny divorce gift",
        intro="Flowers say sorry. A rude book says you are going to be absolutely fine, "
              "and also here is a drawing of a beaver.",
        trade_safe=True,
        books=["andrew-no-mates", "the-lonely-little-worm", "my-beaver-hates-wood",
               "the-dusty-clam", "rosie-a-girls-bestfriend", "the-knuckle-shuffle"],
    ),
    dict(
        handle="inappropriate-baby-shower-gifts",
        title="New Baby & Baby Shower",
        seo_title="Inappropriate Baby Shower Gifts | Funny Books | Jen Jenivive",
        seo_description="Inappropriate baby shower gifts that look like a sweet picture book and very much are not. £12.99. Free UK delivery over £25.",
        target_query="inappropriate baby shower gift",
        intro="It looks exactly like a nursery book. It is shelved with the nursery books. "
              "It is discovered, out loud, roughly four months later.",
        trade_safe=False,
        books=["my-husband-spreads-his-seed", "the-creampie", "colins-creampies",
               "janes-juicebox", "the-little-bean"],
    ),
    dict(
        handle="funny-retirement-gifts",
        title="Retirement Gifts",
        seo_title="Funny Retirement Gifts | Rude Books | Jen Jenivive",
        seo_description="Funny retirement gifts for someone with a lot of free time coming up. Cheeky illustrated books, £12.99. Free UK delivery over £25.",
        target_query="funny retirement gift",
        intro="Forty years of service, one carriage clock, and now an enormous amount of free time. "
              "Give them something to do with it.",
        trade_safe=True,
        books=["my-big-clock", "the-knuckle-shuffle", "andrew-no-mates",
               "graham-the-gardener-trims-a-neat-bush", "barry-the-beaver-photographer",
               "my-great-adventure"],
    ),
    dict(
        handle="rude-gifts-for-couples",
        title="Anniversary & Gifts for Couples",
        seo_title="Rude Anniversary Gifts for Couples | Funny Books | Jen Jenivive",
        seo_description="Rude anniversary gifts for couples who find the same things funny. Illustrated innuendo books from £12.99. Free UK delivery over £25.",
        target_query="rude anniversary gift",
        intro="You have been together long enough that romance is now mostly just making each other laugh. "
              "Lean in.",
        trade_safe=False,
        books=["the-69-club", "riding", "edging", "coming", "stretching", "scissoring",
               "the-pearl-necklace", "get-nailed"],
    ),
    dict(
        handle="rude-valentines-gifts",
        title="Valentine's Day",
        seo_title="Rude Valentine's Gifts | Funny Books for Him & Her | Jen Jenivive",
        seo_description="Rude Valentine's gifts that beat a card and a meal deal. Cheeky illustrated books from £12.99. Free UK delivery over £25.",
        target_query="rude valentines gift",
        intro="A card is £4.99 and gets binned. This is £12.99 and gets brought out at dinner parties for years.",
        trade_safe=False,
        books=["the-pearl-necklace", "get-nailed", "coming", "edging", "riding",
               "the-tasty-taco", "my-magnificent-erection"],
    ),
    dict(
        handle="body-confidence-funny-books",
        title="Body Confidence",
        seo_title="Funny Body Confidence Books for Adults | Jen Jenivive",
        seo_description="Funny body confidence books for adults who would rather laugh about it. Illustrated and affectionate, £12.99. Free UK delivery over £25.",
        target_query="funny body positive gift",
        intro="Everybody has a thing they are quietly self-conscious about. "
              "These are for the people who would rather turn it into a punchline than a problem.",
        trade_safe=False,
        books=["my-fat-ass-funny-adult-picture-book", "itty-bitty-titty-committee",
               "my-teeny-tiny-ween", "my-fat-pussy", "my-fat-cock", "look-at-my-boobies",
               "wendys-wobblers"],
    ),
    dict(
        handle="gifts-for-gardeners-and-hobbyists",
        title="Hobbies & Occupations",
        seo_title="Funny Gifts for Gardeners, Vets & Hobbyists | Jen Jenivive",
        seo_description="Funny gifts for gardeners, vets, photographers and DIYers with a filthy mind. Books from £12.99. Free UK delivery over £25.",
        target_query="funny gardener gift",
        intro="The hardest person to buy for is the one with a hobby. "
              "Here is their hobby, ruined, in book form.",
        trade_safe=True,
        books=["graham-the-gardener-trims-a-neat-bush", "my-beaver-loves-wood",
               "barry-the-beaver-photographer", "jakes-wiener-has-lice-a-day-in-the-life-of-a-vet",
               "billys-banjo-string", "rons-rocket-voyage-to-uranus", "the-massive-banker",
               "tinas-tip-jar"],
    ),
    dict(
        handle="stocking-fillers-under-10",
        title="Stocking Fillers Under £10",
        seo_title="Funny Stocking Fillers Under £10 | Jen Jenivive",
        seo_description="Funny stocking fillers under £10 — cheeky mugs at £6.99. Free UK delivery over £25.",
        target_query="funny stocking fillers under £10",
        intro="Small, cheap, and guaranteed to be the thing they actually take a photo of.",
        trade_safe=False,
        books=[],
        merch=["scissoring-is-my-favourite-craft-mug", "need-a-bone-mug", "ice-ice-babies-mug",
               "its-not-going-to-suck-itself-mug", "snip-happens-mug",
               "high-fives-are-good-but-fisting-is-better-mug"],
    ),
    dict(
        handle="personalised-rude-gifts",
        title="Put Their Name On It",
        seo_title="Personalised Rude Books | Funny Named Gifts | Jen Jenivive",
        seo_description="Personalised rude books with their name printed throughout. The gift they never live down, £24.99. Free UK delivery over £25.",
        target_query="personalised rude gift",
        intro="Their actual name, printed through an actual filthy story. "
              "There is no coming back from this and that is rather the point.",
        trade_safe=False,
        books=[],
        custom=["customised-fionas-fanny", "customised-wendys-wobblers", "customised-taras-taco",
                "customised-simons-sword", "customised-evans-eggplant", "customised-beths-smelly-beaver",
                "customised-bens-baguette", "customised-kellys-kebab",
                "customised-jakes-wiener-has-lice-a-day-in-the-life-of-a-vet"],
    ),
]


def load_catalogue():
    src = (ROOT / "js" / "books-data.js").read_text()
    data = json.loads(src[src.index("{"):].rstrip().rstrip(";"))
    return {
        "books": {b["h"]: b for b in data["books"]},
        "custom": {b["h"]: b for b in data["custom"]},
        "merch": {b["h"]: b for b in data["merch"]},
        "bundles": {b["h"]: b for b in data["bundles"]},
    }


def main():
    cat = load_catalogue()
    errors, rows, pairs, spec = [], [], [], []
    seen_handles = set()

    for occ in OCCASIONS:
        if occ["handle"] in seen_handles:
            errors.append(f"duplicate collection handle: {occ['handle']}")
        seen_handles.add(occ["handle"])

        if len(occ["seo_title"]) > 65:
            errors.append(f"{occ['handle']}: seo_title {len(occ['seo_title'])} chars (>65)")
        if len(occ["seo_description"]) > 160:
            errors.append(f"{occ['handle']}: seo_description {len(occ['seo_description'])} chars (>160)")

        products = []
        for key, source in (("books", "books"), ("custom", "custom"), ("merch", "merch")):
            for h in occ.get(key, []):
                if h not in cat[source]:
                    errors.append(f"{occ['handle']}: unknown {source} handle '{h}'")
                    continue
                item = cat[source][h]
                products.append({"handle": h, "title": item["t"], "price": item["p"], "type": source})

        if not products:
            errors.append(f"{occ['handle']}: no valid products")

        spec.append({**{k: v for k, v in occ.items() if k not in ("books", "custom", "merch")},
                     "url": f"/collections/{occ['handle']}",
                     "product_count": len(products),
                     "products": products})
        rows.append({
            "handle": occ["handle"], "title": occ["title"], "target_query": occ["target_query"],
            "seo_title": occ["seo_title"], "seo_description": occ["seo_description"],
            "intro": occ["intro"], "product_count": len(products),
            "trade_safe": "yes" if occ["trade_safe"] else "no",
        })
        for p in products:
            pairs.append({"collection": occ["handle"], "product_handle": p["handle"],
                          "product_title": p["title"], "price_gbp": p["price"], "type": p["type"]})

    if errors:
        print("BUILD FAILED:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        return 1

    (OUT / "occasion-collections.json").write_text(json.dumps(spec, indent=2) + "\n")
    with open(OUT / "occasion-collections.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    with open(OUT / "collection-products.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0]))
        w.writeheader(); w.writerows(pairs)

    covered = {p["product_handle"] for p in pairs if p["type"] == "books"}
    print(f"OK  {len(spec)} collections, {len(pairs)} product placements")
    print(f"    books covered: {len(covered)}/{len(cat['books'])}")
    uncovered = sorted(set(cat["books"]) - covered)
    print(f"    books in no occasion ({len(uncovered)}):")
    for h in uncovered:
        print(f"      {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
