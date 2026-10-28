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

## Desktop app

**Step2HTML** is a small desktop app for the same conversion: choose (or drop) a STEP file, pick where
to save, press **Create viewer**. Options: viewer title and mesh detail (Coarse / Standard / Fine). It
follows the system's light/dark mode and can open the result in the browser when done.

- **macOS**: `Step2HTML-<version>-macos-<arch>.dmg`. Drag the app to Applications (first launch of
  a downloaded copy: right-click → Open, as it isn't notarized).
- **Linux**: `.deb` for Debian/Ubuntu, `.pkg.tar.zst` for Arch; both also install the `step2html`
  command.
- **Windows**: `Step2HTML-<version>-Setup.exe` (installer) or `Step2HTML-<version>-windows-x64.zip`
  (portable). Unsigned, so SmartScreen asks once: **More info → Run anyway**.

Everything is bundled (no Python setup needed). To build the packages yourself see
[packaging/README.md](packaging/README.md). To run the app from source:
`pip install cadquery-ocp PySide6-Essentials` and `python3 step2html_gui.py`.

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
- **Multi-select**: in the tree, Shift-click selects a range and Cmd-click (Mac) / Ctrl-click (Windows,
  Linux) adds or removes a part; in the 3D view Cmd/Ctrl-click adds or removes (on a Mac Ctrl-click stays
  the right-click menu). Right-click inside the selection, Isolate, Fit and the H/T/I/F keys act on all
  selected parts
- **Right-click** a part (or **long-press** on touch), in the 3D view or in the tree, for a menu:
  Hide · Make transparent / solid · Hide others · Zoom to part · Show all (· Make all solid)
- **View cube** (top right): click a face, edge or corner to snap to that view (26 views); drag it to
  orbit; in a straight (face-on) view the curved arrows roll the view 90° left/right; the house
  button returns to the default isometric view
- **Explode** (toolbar): spreads the assembly level by level with a distance slider; *Levels* sets how
  many layers of sub-assemblies come apart (1 = only the top level). While it is on, the right-click
  menu has an *Exploded view* section with two tick options: *Stay in place* (the part stays fixed
  and the rest spreads out around it)
  and *Keep together* (its assembly doesn't come apart, e.g. a PCB with its components; from the 3D
  view this applies to the part's parent assembly). Flagged rows get a small marker in the tree
- **Measure** (toolbar): click two items to measure between them: corners (snaps to mesh vertices), flat
  faces and holes/cylinders. Gives point/face/axis distances with ΔX/ΔY/ΔZ (in the CAD's axes), angles
  between faces/axes, and the diameter of any hole or cylinder you click. Results are listed in the panel
  (remove one with ×, or *Clear* all) and labelled in the 3D view; hover a row to find its label.
  Values are in mm. Flat faces and corners are exact; hole diameters are fitted through the mesh
  (shown as ≈). Measurements belong to the assembled model and are hidden while exploded
- **Lights** (toolbar): presets (Studio, Headlight, Soft, Dramatic) with colour-temperature
  (2700–8000 K) and brightness sliders; the choice is remembered
- **Parts panel** (left; *Parts* button to open on phones): filter box, *Expand all* / *Collapse all*,
  eye icon to hide/show each part or sub-assembly, click a name to select, double-click to zoom to it;
  transparent parts show a dashed swatch, fully transparent assemblies a small transparency icon;
  drag the panel's right edge to resize it (double-click the edge to reset; remembered per browser)
- **Toolbar**: Fit · Isolate (show only the selection) · Show all · Edges · light/dark theme
  (the theme follows the OS setting until toggled, then is remembered)
- **Keyboard**: `F` fit · `H` hide · `T` transparent · `I` isolate · `A` show all · `E` edges · `X` explode ·
  `M` measure · `L` lights · `Esc` deselect

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

## License

step2html is released under the [MIT License](LICENSE).

It builds on third-party components under their own licenses: three.js with its OrbitControls and
GLTFLoader (MIT; embedded in every generated viewer), cadquery-ocp (Apache-2.0) and OpenCASCADE
(LGPL-2.1 with exception) for the converter, and, in the desktop app packages, Qt/PySide6 (LGPL-3.0),
VTK (BSD-3-Clause) and Python (PSF License).
