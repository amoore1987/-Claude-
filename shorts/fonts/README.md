# Fonts

Static TTF instances of the brand fonts, generated from the variable-font
`.woff2` files in `assets/fonts/` — ffmpeg and Pillow cannot read woff2, and the
variable originals default to Thin, so each weight is pinned here.

| File | Family | Weight |
| --- | --- | --- |
| `librefranklin-900.ttf` | Libre Franklin | 900 (Black) |
| `librefranklin-700.ttf` | Libre Franklin | 700 (Bold) |
| `montserrat-700.ttf` | Montserrat | 700 (Bold) |
| `montserrat-500.ttf` | Montserrat | 500 (Medium) |
| `borel-400.ttf` | Borel | 400 (Regular) |

All three families are licensed under the
[SIL Open Font License 1.1](https://openfontlicense.org), which permits
redistribution of modified versions — instancing a variable font is such a
modification.

To regenerate after a font change:

```bash
python3 - <<'PY'
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
for src, wght, dst in [
    ("assets/fonts/librefranklin-900.woff2", 900, "shorts/fonts/librefranklin-900.ttf"),
    ("assets/fonts/librefranklin-700.woff2", 700, "shorts/fonts/librefranklin-700.ttf"),
    ("assets/fonts/montserrat-700.woff2",    700, "shorts/fonts/montserrat-700.ttf"),
    ("assets/fonts/montserrat-500.woff2",    500, "shorts/fonts/montserrat-500.ttf"),
]:
    f = instancer.instantiateVariableFont(TTFont(src), {"wght": wght}, updateFontNames=True)
    f.flavor = None
    f["OS/2"].usWeightClass = wght
    f.save(dst)
PY
```

`borel-400.woff2` is not variable; it is converted straight across by setting
`flavor = None`.
