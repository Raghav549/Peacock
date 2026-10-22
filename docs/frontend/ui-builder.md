# Native दृश्य UI builder

`peacock/frontend/ui.py` and the `दृश्य` namespace implement a retained-mode UI
tree. `.सूत्र` programs can create panels, Unicode text, semantic buttons and
safe links; apply row/column flow or equal-column grids; compute absolute bounds;
hit-test points; audit accessibility; and export responsive HTML.

## Document and nodes

`दृश्य.सृज(शीर्षक, विस्तार, औन्नत्य, पृष्ठवर्ण)` returns opaque `दृश्यरचना`.
Node-producing calls return stable integer IDs. Parent `०` is the document root;
panels may contain children, while text/button/link nodes are leaves.

| Native | Purpose |
|---|---|
| `दृश्य.पटल(...)` | panel/container with background |
| `दृश्य.पाठ्य(...)` | Unicode text with foreground and font size |
| `दृश्य.नोदक(...)` | semantic button preview |
| `दृश्य.सम्पर्क(...)` | relative, HTTP(S) or mailto link |
| `दृश्य.ग्रन्थिसंख्या(रचना)` | node count including root |

Every node has explicit finite positive dimensions. Parents and node IDs are
checked. Active-content URL schemes such as `javascript:` and `data:` are
rejected.

## Layout and interaction geometry

* `दृश्य.प्रवाह(रचना, जनक, "स्तम्भ"|"पङ्क्ति", अन्तर, अन्तराल)` positions children
  in column/row order without changing their sizes.
* `दृश्य.जालक(रचना, जनक, स्तम्भानि, अन्तर, अन्तराल)` computes equal cell widths
  and row positions from the tallest cell in each row.
* `दृश्य.परिसीमा(रचना, ग्रन्थि)` returns `[x, y, width, height]` in document space.
* `दृश्य.स्पर्शपरीक्षा(रचना, क्ष, य)` returns the topmost containing node or `-१`.

These operations run natively in the VM; they do not ask a browser to calculate
the answers.

## Accessibility and export

`दृश्य.अन्वीक्षा(रचना)` returns structured findings for:

* child overflow outside its parent;
* empty text/link/button labels;
* WCAG foreground/background contrast below 4.5:1;
* interactive targets smaller than 44×44 design units.

`दृश्य.एचटीएमएलपाठ्य(रचना)` returns a complete `<html lang="sa">` document with
escaped Sanskrit text, responsive relative geometry, visible keyboard focus,
a mobile layout rule and `prefers-reduced-motion`. It contains no JavaScript.
`दृश्य.रक्ष(रचना, पथ)` writes the same document through the `सञ्चय` sandbox.

Run the working example:

```bash
./bin/peacock run examples/ui_builder.सूत्र --grant सञ्चय --root .
# writes examples/out/ui.html
```

## Boundary

This is a working static UI component/layout/export toolkit. Button event
handlers, an input/frame scheduler, native text shaping, native accessibility
APIs, desktop windows and a browser interaction runtime are not yet implemented.
The separate `चित्र.प्रदर्शय` frame API remains available for rendered canvas
presentation.
