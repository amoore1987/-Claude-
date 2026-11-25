# templates/product.sold-on-store.json — change

This is the template all nine personalised (£24.99) books use. It had no curated
cross-sell at all — only Dawn's generic `related-products`. Adding the `jj_pairs`
section gives personalised pages the same order-data module every other book has.

```diff
   "sections": {
     "main": { ... unchanged ... },
+    "jj_pairs": {
+      "type": "jj-pairs-with",
+      "settings": {
+        "eyebrow": "Readers also grabbed",
+        "heading": "Pairs well with <em>this one</em>",
+        "subheading": "Real pairings from real orders.",
+        "button_label": "Add to bag",
+        "personalise_label": "Personalise it",
+        "personalise_template": "sold-on-store",
+        "note": "Free delivery over £25 to the UK, Europe and USA, or £40 worldwide.",
+        "max_items": 3
+      }
+    },
     "177213712113ec00f2": { ... judge.me ... },
     "related-products": { ... unchanged ... }
   },
   "order": [
     "main",
+    "jj_pairs",
     "177213712113ec00f2",
     "related-products"
   ]
```

The section hides itself when `custom.pairs_with` is empty, so this is inert
until those nine products get pairings of their own — see the README.
