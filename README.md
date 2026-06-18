# step2html — STEP → self-contained 3D HTML viewer

Converts a **STEP** CAD file (`.step` / `.stp`, ISO 10303) into a **single, self-contained
HTML file** that displays the 3D model in any modern browser, with a **CAD-style parts tree**
(select, highlight, hide, isolate). The output has no external dependencies — three.js, the
loader, the geometry, and the part names are all embedded — so it works offline and by simply
opening the file (`file://`). Works in **desktop and mobile/tablet** browsers (touch supported).

Runs natively on **macOS and Linux**.

```
STEP  ──[OpenCASCADE XCAF]──►  glTF (geometry + colors + names + tree)  ──►  embedded three.js HTML
```

## Usage

```bash
./step2html my_assembly.step
# -> writes my_assembly.html next to the input

./step2html my_assembly.stp -o viewer.html --title "My Assembly"
```

First run creates a local virtual environment in `./.venv` and installs the one dependency
([`cadquery-ocp`](https://pypi.org/project/cadquery-ocp/), the OpenCASCADE bindings — a few
hundred MB, downloaded once). Later runs reuse it.

### Viewer controls
- **Rotate**: drag (one finger on touch) · **Pan**: right-drag / two-finger drag · **Zoom**: scroll / pinch
- **Tap/click a part** in the 3D view to select + highlight it (and reveal it in the tree)
- **Parts panel** (left; ☰ to open on phones): filter box, expand/collapse tree, 👁 to hide/show each
  part or sub-assembly, click a name to select
- **Buttons**: Fit · Isolate (show only the selection) · Show all · Edges · BG

### Options

| Option | Default | Meaning |
|---|---|---|
| `-o, --output PATH` | `<input>.html` | Output HTML path |
| `--title TEXT` | input file name | Label shown in the viewer |
| `--tol-linear N` | `0.2` | Linear tessellation deflection (model units). Smaller = finer mesh, bigger file |
| `--tol-angular N` | `0.5` | Angular tessellation deflection (radians) |
| `--keep-glb PATH` | — | Also write the intermediate `.glb` |

## What is preserved (and the color caveat)

`step2html` reads the STEP through OpenCASCADE's **XCAF** layer, so it keeps:

- **geometry** (tessellated B-rep),
- the **assembly hierarchy**,
- real **part names** — resolved from the product prototypes, not the raw `NAUO…` instance
  ids, and including non-ASCII names (e.g. Cyrillic), and
- any **per-part colors that exist in the STEP**.

⚠️ **Colors are only as good as the STEP export.** A STEP file carries color only if the CAD
exported it. In testing, the SolidWorks export of this assembly contained a *single* color for
all parts (the default light blue-gray), so the model renders monochrome — that is faithful to
the file, not a converter bug. To get per-part colors, re-export from SolidWorks with appearance
/ color export enabled (and make sure the parts actually have distinct appearances assigned).
The tool prints how many distinct colors it found.

## Performance

CAD assemblies can be huge (this one is ~2,300 parts / 1.2M triangles). Two things keep
the viewer fast and the page from crashing the browser:

- **Merged faces at conversion time.** OpenCASCADE otherwise writes one glTF primitive per
  B-rep face, which for this model meant ~93,000 draw calls — enough to peg the CPU and lock
  up the browser. The converter calls `SetMergeFaces`, collapsing each solid to a single
  primitive: **~1,900 draw calls instead of ~93,000**, same geometry and colors. This is the
  same idea CAD web viewers (eDrawings / HOOPS) rely on — batch geometry to minimize draw calls.
- **Lazy parts tree + render-on-demand.** The tree builds rows only as you expand them (not all
  ~96k instances up front), filtering searches a lightweight index, static transforms are frozen,
  and the scene only re-renders when something actually changes.

If a model is still heavy on a low-end device, export with a coarser `--tol-linear` to reduce
triangles.

## Why STEP and not EASM?

The original eDrawings `.EASM` stores geometry in SolidWorks' proprietary, undocumented
`SWeModels` binary, and the eDrawings `.html` embeds a closed HOOPS Communicator Stream Cache
payload. Neither can be read or produced with free, cross-platform tooling. **STEP** is an open
ISO standard with a mature free reader (OpenCASCADE), so exporting to STEP makes a license-free
conversion possible. Passing a `.easm`/`.sldasm`/etc. file makes the tool refuse with a clear
message.

## Layout

```
step2html              launcher (bash) — provisions ./.venv, runs the converter
step2html.py           the converter (Python + OpenCASCADE/XCAF)
requirements.txt       the single dependency (cadquery-ocp)
lib/
  three.min.js         three.js r136 (UMD, offline)
  GLTFLoader.js        glTF loader (UMD)
  OrbitControls.js     camera controls (UMD)
  viewer_template.html HTML template (parts tree + viewer)
.venv/                 created on first run (Python env with cadquery-ocp)
```

## Requirements

- Python 3.8+ (`python3` on PATH)
- macOS or Linux with a `pip`-installable `cadquery-ocp` wheel (current macOS/Linux,
  x86-64 and Apple Silicon)
- Internet access on the **first run only**, to install the dependency
