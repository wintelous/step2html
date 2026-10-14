#!/usr/bin/env python3
"""Write a tiny two-part STEP assembly (a box and a cylinder) for build smoke tests."""
import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.Interface import Interface_Static

Interface_Static.SetIVal_s("write.step.verbose", 0)
w = STEPControl_Writer()
w.Transfer(BRepPrimAPI_MakeBox(40, 30, 10).Shape(), STEPControl_AsIs)
w.Transfer(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(60, 0, 0), gp_Dir(0, 0, 1)), 6, 20).Shape(), STEPControl_AsIs)
w.Write(sys.argv[1] if len(sys.argv) > 1 else "smoke.step")
