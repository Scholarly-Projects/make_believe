# Interact Wall — Deployment Guide

A 3D-flippable tile visualization for the Make Believe costume catalog exhibit.

---

## Files & Where They Go

| File (from download) | Destination in repo |
|---|---|
| `interact.md` | `pages/interact.md` |
| `interact.html` | `_layouts/interact.html` |
| `interact_type.csv` | `_data/interact_type.csv` |
| `interact_ethnic.csv` | `_data/interact_ethnic.csv` |

Images referenced by the CSVs (e.g. `interact_38.png`) should live at:

```
objects/interact/interact_38.png
objects/interact/interact_13.png
... etc.
```

---

## How It Works

### Data
Jekyll reads `_data/interact_type.csv` and `_data/interact_ethnic.csv` at build time and serializes them to JavaScript inside the layout. No external fetch calls — the visualization works offline and in any deployment environment.

**interact_type.csv columns:**
- `filename` — image filename (e.g. `interact_38.png`), leave blank if no image
- `title` — display label for the category
- `count` — number of catalog items in this category
- `percentage` — e.g. `17.1%`
- `examples` — short comma-separated list for the tile tooltip/lightbox
- `description` — 1–3 paragraph body text shown in the lightbox detail view
- `full` — complete comma-separated list of all costumes in this category

**interact_ethnic.csv columns:**
- `image` — image filename, or blank
- `category` — display label
- (same remaining columns as above)

### Tile Sizing
Tile sizes are computed algorithmically: the JavaScript runs a binary-search to find a scaling factor such that, when tiles are laid out left-to-right with `sqrt(percentage / max_percentage)` proportional sizing, they fill the square wall without overflow or excess blank space. This means adding a new row to either CSV will automatically reflow the layout — no manual sizing needed.

### 3D Flip (Desktop)
The wall uses CSS 3D transforms (`rotateY`) with `perspective: 2000px`. The front face shows **Costume Type** data; the back face (rotated 180° around the Y axis) shows **National or Ethnic Costumes** data. The surrounding orb ring captures pointer-drag events to rotate the card in real time; releasing snaps it to the nearest face.

### Mobile
On screens narrower than 768px:
- The 3D transform is disabled (the browser's touch scroll would conflict with the drag gesture)
- Faces are toggled via CSS class — only one face is visible at a time
- The **Flip Wall** button becomes the primary navigation

### Keyboard Access
- `Tab` moves through tiles in frequency order (most → least)
- `Enter` or `Space` opens the lightbox detail view for the focused tile
- `F` flips the wall (when lightbox is closed and focus is not in a form field)
- `Escape` closes the lightbox or the intro modal
- The **Flip Wall** button is in the natural tab order after the last tile

---

## Updating Content

**Changing descriptions:** Edit `description` column in the relevant CSV. The field supports plain text; use a newline (`\n`) to create paragraph breaks in the lightbox.

**Adding a new category:** Add a row to the CSV in the correct frequency order. The layout will reflow automatically on next Jekyll build.

**Swapping an image:** Replace the file in `objects/interact/` and update the `filename` / `image` column in the CSV. If a row has no image, the tile displays a hatched placeholder.

**Adjusting minimum/maximum tile size:** In `_layouts/interact.html`, find the JavaScript block near the top of the `<script>` section:
```js
var MIN_TILE = 62;   // px minimum tile side
var MAX_TILE = 220;  // px maximum tile side (unconstrained)
```
Increasing `MIN_TILE` makes small tiles larger (useful if many categories have very low percentages).

---

## Dependencies
None. The visualization uses vanilla JavaScript and CSS — no npm, no build step beyond Jekyll's normal process.