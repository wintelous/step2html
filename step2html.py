#!/usr/bin/env python3
"""
step2html.py — convert a STEP (ISO 10303) CAD file into a single, self-contained
HTML file that displays the 3D model in any modern browser, with a CAD-style
parts tree (select / highlight / hide / isolate).

Pipeline:
    STEP  --[OpenCASCADE XCAF: STEPCAFControl_Reader]-->  document with
          assembly tree + names + colors
          --[BRepMesh tessellation + RWGltf_CafWriter]-->  glTF/.glb
          --[base64 + name map + three.js viewer template]-->  standalone .html

What is preserved:
  * geometry (tessellated B-rep)
  * per-part colors that exist in the STEP (sRGB)
  * the assembly hierarchy
  * real part names (resolved from the product prototypes, not the raw
    NAUO instance ids), including non-ASCII names

The output HTML has no external dependencies (three.js, loader, geometry and
name map are all embedded), so it works offline and from file://.

Requires the `cadquery-ocp` package (OpenCASCADE bindings). The companion
launcher `step2html` installs it into a local virtual environment automatically.
"""

import argparse
import base64
import json
import os
import sys
import tempfile

__version__ = "1.0.0"

# When bundled into the desktop app (PyInstaller), the assets live in the unpacked bundle.
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib")


def die(msg, code=1):
    sys.stderr.write("error: " + msg + "\n")
    sys.exit(code)


def read_lib(name):
    path = os.path.join(LIB, name)
    if not os.path.isfile(path):
        die("missing required asset: %s (expected in %s)" % (name, LIB))
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0


def _html_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def convert_step_to_glb(inp, glb_path, tol_linear, tol_angular):
    """Read STEP via XCAF, tessellate, write a binary glTF. Returns (name_map,
    n_colors) where name_map is {instance-name -> product-name}."""
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString, TCollection_AsciiString
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorType
    from OCP.TDF import TDF_Label, TDF_Tool
    try:
        from OCP.TDF import TDF_LabelSequence                     # cadquery-ocp <= 7.7
    except ImportError:                                           # cadquery-ocp >= 7.8 moved it
        from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
    from OCP.TDataStd import TDataStd_Name
    from OCP.Quantity import Quantity_Color
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.RWGltf import RWGltf_CafWriter
    try:
        from OCP.TColStd import TColStd_IndexedDataMapOfStringString
    except ImportError:
        from OCP.collections import (IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString
                                     as TColStd_IndexedDataMapOfStringString)
    from OCP.Message import Message_ProgressRange

    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    sys.stderr.write("[1/4] reading STEP (OpenCASCADE) ...\n")
    if reader.ReadFile(inp) != IFSelect_RetDone:
        die("OpenCASCADE could not read the STEP file (parse error).")
    if not reader.Transfer(doc):
        die("OpenCASCADE could not transfer the STEP model.")

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def get_name(label):
        attr = TDataStd_Name()
        try:
            if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
                return attr.Get().ToExtString()
        except Exception:
            pass
        return None

    def entry(label):
        s = TCollection_AsciiString()
        TDF_Tool.Entry_s(label, s)
        return s.ToCString()

    # --- tessellate every free (top) shape ---
    free = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free)
    if free.Length() == 0:
        die("the STEP file contains no shapes.")
    sys.stderr.write("[2/4] tessellating ...\n")
    for i in range(1, free.Length() + 1):
        shp = shape_tool.GetShape_s(free.Value(i))
        BRepMesh_IncrementalMesh(shp, tol_linear, False, tol_angular, True)

    # --- build {instance-name -> product-name} map + count distinct colors ---
    name_map = {}
    colors = set()
    visited = set()

    def color_of(label):
        c = Quantity_Color()
        for t in (XCAFDoc_ColorType.XCAFDoc_ColorSurf,
                  XCAFDoc_ColorType.XCAFDoc_ColorGen):
            try:
                if color_tool.GetColor_s(label, t, c):
                    return (round(c.Red(), 4), round(c.Green(), 4), round(c.Blue(), 4))
            except Exception:
                pass
        return None

    def walk(label):
        comps = TDF_LabelSequence()
        shape_tool.GetComponents_s(label, comps, False)
        for i in range(1, comps.Length() + 1):
            comp = comps.Value(i)
            inst = get_name(comp)
            ref = TDF_Label()
            if shape_tool.GetReferredShape_s(comp, ref):
                prod = get_name(ref)
                if inst and prod:
                    name_map[inst] = prod
                col = color_of(comp) or color_of(ref)
                if col:
                    colors.add(col)
                e = entry(ref)
                if e not in visited:
                    visited.add(e)
                    walk(ref)

    for i in range(1, free.Length() + 1):
        walk(free.Value(i))

    # --- write binary glTF ---
    sys.stderr.write("[3/4] writing glTF ...\n")
    writer = RWGltf_CafWriter(TCollection_AsciiString(glb_path), True)
    # Merge all faces of each part into a single primitive. Colors here are per
    # part, so this is lossless, and it collapses tens of thousands of per-face
    # draw calls to one per solid — the difference between an interactive viewer
    # and a 90k-draw-call slideshow.
    try:
        writer.SetMergeFaces(True)
    except Exception:
        pass
    try:
        writer.SetParallel(True)
    except Exception:
        pass
    info = TColStd_IndexedDataMapOfStringString()
    if not writer.Perform(doc, info, Message_ProgressRange()):
        die("OpenCASCADE failed to write the glTF model.")

    return name_map, len(colors)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="step2html",
        description="Convert a STEP file into a self-contained 3D HTML viewer "
                    "with a parts tree (select / hide / isolate).",
    )
    ap.add_argument("input", help="input STEP file (.step / .stp)")
    ap.add_argument("-o", "--output", help="output HTML (default: <input>.html)")
    ap.add_argument("--title", help="title shown in the viewer (default: file stem)")
    ap.add_argument("--tol-linear", type=float, default=0.2,
                    help="linear tessellation deflection in model units; smaller = "
                         "finer mesh, larger file (default: 0.2)")
    ap.add_argument("--tol-angular", type=float, default=0.5,
                    help="angular tessellation deflection in radians (default: 0.5)")
    ap.add_argument("--keep-glb", metavar="PATH",
                    help="also write the intermediate .glb to PATH")
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = ap.parse_args(argv)
    try:                                        # never crash on a path the console code page can't show
        sys.stderr.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    inp = args.input
    if not os.path.isfile(inp):
        die("input file not found: %s" % inp)

    ext = os.path.splitext(inp)[1].lower()
    if ext in (".easm", ".eprt", ".edrw", ".sldasm", ".sldprt"):
        die("'%s' is a proprietary SolidWorks/eDrawings file, which cannot be read "
            "with free tooling. Export the assembly as STEP (.step/.stp) and pass "
            "that instead." % ext)
    if ext not in (".step", ".stp", ".stpz", ".p21"):
        sys.stderr.write("warning: '%s' is not a typical STEP extension; trying "
                         "anyway.\n" % ext)

    try:
        import OCP  # noqa: F401
    except ImportError:
        die("the 'cadquery-ocp' package (OpenCASCADE) is not installed.\n"
            "  Install it with:  python3 -m pip install cadquery-ocp\n"
            "  Or run this tool through the ./step2html launcher, which sets up a "
            "virtual environment automatically.")

    stem = os.path.splitext(os.path.basename(inp))[0]
    title = args.title or stem
    out_html = args.output or os.path.join(os.path.dirname(os.path.abspath(inp)),
                                           stem + ".html")

    glb_path = args.keep_glb
    cleanup = False
    if not glb_path:
        fd, glb_path = tempfile.mkstemp(suffix=".glb")
        os.close(fd)
        cleanup = True

    try:
        name_map, n_colors = convert_step_to_glb(inp, glb_path,
                                                 args.tol_linear, args.tol_angular)
        glb_size = os.path.getsize(glb_path)
        if glb_size == 0:
            die("conversion produced an empty model (no tessellated geometry).")
        with open(glb_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    finally:
        if cleanup and os.path.exists(glb_path):
            os.remove(glb_path)

    sys.stderr.write("[4/4] writing HTML (geometry %s, %d named parts, %d distinct "
                     "color%s) ...\n"
                     % (_human(glb_size), len(name_map), n_colors,
                        "" if n_colors == 1 else "s"))
    if n_colors <= 1:
        sys.stderr.write("note: the STEP encodes a single color for the whole model; "
                         "re-export from the CAD with appearances/colors enabled to "
                         "get per-part colors.\n")

    html = read_lib("viewer_template.html")
    repl = {
        "__TITLE__": _html_escape(title),
        "__THREE_JS__": read_lib("three.min.js"),
        "__ORBITCONTROLS_JS__": read_lib("OrbitControls.js"),
        "__GLTFLOADER_JS__": read_lib("GLTFLoader.js"),
        "__NAME_MAP__": json.dumps(name_map, ensure_ascii=False),
        "__MODEL_B64__": b64,
    }
    for k, v in repl.items():
        html = html.replace(k, v)

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    sys.stderr.write("done: %s  (%s)\n" % (out_html, _human(os.path.getsize(out_html))))


if __name__ == "__main__":
    main()
