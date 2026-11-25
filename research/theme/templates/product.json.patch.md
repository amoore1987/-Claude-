# templates/product.json — change

Only the `jj_pairs` section settings change. Everything else is byte-identical.

```diff
     "jj_pairs": {
       "type": "jj-pairs-with",
       "settings": {
         "eyebrow": "Readers also grabbed",
         "heading": "Pairs well with <em>this one</em>",
         "subheading": "Real pairings from real orders.",
         "button_label": "Add to bag",
+        "personalise_label": "Personalise it",
+        "personalise_template": "sold-on-store",
         "note": "Free delivery over £25 to the UK, Europe and USA, or £40 worldwide.",
-        "max_items": 3
+        "max_items": 4
       }
     },
```

`max_items` goes to 4 so the personalised edition can be added as a fourth card
without displacing any of the three order-data pairings. The section already
allowed 4 (`"max": 4` in its schema range); the CSS now lays 4 out as 2x2 on
mobile and 4-across on desktop.
