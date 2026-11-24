"""Shared helpers for the shell-casting-gating skill.

Conventions used by every script (keep them, the rules in SKILL.md depend on them):
  * Units: mm, kg, s, degC.
  * Casting local frame after `orientation` is applied: parting plane Z = 0, draw direction Z,
    the face chosen for feeding faces +Y, the lever/long axis runs along X.
  * One JSON job config (see templates/job_config.example.json) drives all scripts.
"""
import json, math, os, hashlib, functools
import numpy as np

# ----------------------------------------------------------------------------- config
def load_config(path):
    with open(path) as f:
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    cfg["_dir"] = base
    out = cfg.get("output_dir", "out")
    cfg["_out"] = out if os.path.isabs(out) else os.path.join(base, out)
    os.makedirs(cfg["_out"], exist_ok=True)
    st = cfg["part"]["step"]
    cfg["part"]["_step"] = st if os.path.isabs(st) else os.path.join(base, st)
    return cfg

def out_path(cfg, name):
    return os.path.join(cfg["_out"], name)

def save_json(cfg, name, data):
    p = out_path(cfg, name)
    with open(p, "w") as f:
        json.dump(data, f, indent=1, default=float)
    return p

def read_json(cfg, name):
    with open(out_path(cfg, name)) as f:
        return json.load(f)

# ----------------------------------------------------------------------------- OCC helpers
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakeSphere, BRepPrimAPI_MakePrism)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut, BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Pnt, gp_Ax1, gp_Ax2, gp_Dir, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.collections import List_TopoDS_Shape

def read_step(path):
    r = STEPControl_Reader()
    if int(r.ReadFile(path)) != 1:
        raise RuntimeError(f"cannot read STEP {path}")
    r.TransferRoots()
    return r.OneShape()

def write_step(shape, path):
    w = STEPControl_Writer(); w.Transfer(shape, STEPControl_AsIs); w.Write(path)

def vol(s):
    p = GProp_GProps(); BRepGProp.VolumeProperties_s(s, p); return p.Mass()

def area(s):
    p = GProp_GProps(); BRepGProp.SurfaceProperties_s(s, p); return p.Mass()

def bbox(s):
    b = Bnd_Box(); BRepBndLib.Add_s(s, b, True)
    return np.array(b.CornerMin().Coord()), np.array(b.CornerMax().Coord())

def valid(s):
    return BRepCheck_Analyzer(s).IsValid()

def box(x0, x1, y0, y1, z0, z1):
    return BRepPrimAPI_MakeBox(gp_Pnt(min(x0, x1), min(y0, y1), min(z0, z1)),
                               gp_Pnt(max(x0, x1), max(y0, y1), max(z0, z1))).Shape()

def cyl(p, d, r, h):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*p), gp_Dir(*d)), r, h).Shape()

def cone(p, r0, r1, h):
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(*p), gp_Dir(0, 0, 1)), r0, r1, h).Shape()

def boolop(kind, a, tools, fuzzy=0.01):
    A = List_TopoDS_Shape(); T = List_TopoDS_Shape()
    for s in (a if isinstance(a, list) else [a]): A.Append(s)
    for s in tools: T.Append(s)
    op = {"fuse": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut, "common": BRepAlgoAPI_Common}[kind]()
    op.SetArguments(A); op.SetTools(T); op.SetRunParallel(True); op.SetFuzzyValue(fuzzy); op.Build()
    if not op.IsDone():
        raise RuntimeError(f"boolean {kind} failed")
    return op.Shape()

def fuse(shapes):
    return shapes[0] if len(shapes) == 1 else boolop("fuse", shapes[0], shapes[1:])

def capsule(x, y, z0, z1, r):
    """Vertical blind riser: cylinder with hemispherical bottom and dome top, Z from z0 to z1."""
    return boolop("fuse", cyl((x, y, z0 + r), (0, 0, 1), r, max(z1 - z0 - 2 * r, 0.01)),
                  [BRepPrimAPI_MakeSphere(gp_Pnt(x, y, z0 + r), r).Shape(),
                   BRepPrimAPI_MakeSphere(gp_Pnt(x, y, z1 - r), r).Shape()])

def placed(shape, xo, yo, rot180):
    """Copy of a casting-local shape placed at (xo, yo), optionally rotated 180 deg about Z."""
    tr = gp_Trsf()
    if rot180:
        tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.pi)
    t2 = gp_Trsf(); t2.SetTranslation(gp_Vec(xo, yo, 0)); t2.Multiply(tr)
    return BRepBuilderAPI_Transform(shape, t2, True).Shape()

def mesh_to_stl(shape, path, lin=0.1, ang=0.3):
    BRepMesh_IncrementalMesh(shape, lin, False, ang, True)
    StlAPI_Writer().Write(shape, path)

# ----------------------------------------------------------------------------- part
def _orient(shape, cfg):
    """Apply cfg['orientation']['rotations'] = [["x", 90], ["z", 180], ...] then translate so that
    cfg['orientation']['origin'] (in rotated coords, default bbox-centre X/Y and Z=0 kept) becomes 0."""
    o = cfg.get("orientation", {})
    for ax, deg in o.get("rotations", []):
        d = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[ax]
        tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(*d)), math.radians(deg))
        shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
    off = o.get("translate", [0, 0, 0])
    if any(off):
        tr = gp_Trsf(); tr.SetTranslation(gp_Vec(*off)); shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
    return shape

@functools.lru_cache(maxsize=4)
def _load(step, orient_key):
    cfg = {"orientation": json.loads(orient_key)}
    return _orient(read_step(step), cfg)

def load_part(cfg):
    return _load(cfg["part"]["_step"], json.dumps(cfg.get("orientation", {}), sort_keys=True))

def part_key(cfg):
    h = hashlib.md5()
    with open(cfg["part"]["_step"], "rb") as f:
        h.update(f.read())
    h.update(json.dumps(cfg.get("orientation", {}), sort_keys=True).encode())
    return h.hexdigest()[:10]

# ----------------------------------------------------------------------------- voxels
def fine_voxels(cfg, pitch=0.35):
    """Filled voxel model of the oriented casting (bool array, origin of voxel centres, pitch).
    Cached in the output folder. Surface voxels make it ~5-7 % heavy; use calibrated_grid() for simulation."""
    import trimesh
    cache = out_path(cfg, f"vox_{part_key(cfg)}_{pitch}.npz")
    if os.path.exists(cache):
        z = np.load(cache); return z["m"], z["o"], float(z["p"])
    shape = load_part(cfg)
    stl = out_path(cfg, "part_oriented.stl")
    mesh_to_stl(shape, stl, 0.05, 0.2)
    m = trimesh.load(stl); m.merge_vertices()
    try:
        trimesh.repair.fill_holes(m)
    except Exception:
        pass
    v = m.voxelized(pitch).fill()
    M = v.matrix.copy(); o = v.transform[:3, 3].copy()
    np.savez_compressed(cache, m=M, o=o, p=pitch)
    return M, o, pitch

def calibrated_grid(cfg, dx):
    """Casting occupancy on a dx grid (casting-local), threshold calibrated so the voxel volume equals
    the exact CAD volume. Returns (mask, origin_of_cell_corners)."""
    cache = out_path(cfg, f"grid_{part_key(cfg)}_{dx}.npz")
    if os.path.exists(cache):
        z = np.load(cache); return z["m"], z["o"]
    F, fo, fp = fine_voxels(cfg)
    lo = fo - 2.0; hi = fo + np.array(F.shape) * fp + 2.0
    n = np.ceil((hi - lo) / dx).astype(int)
    acc = np.zeros(n); sub = (np.arange(4) + 0.5) / 4
    for sx in sub:
        for sy in sub:
            for sz in sub:
                X = lo[0] + (np.arange(n[0]) + sx) * dx; Y = lo[1] + (np.arange(n[1]) + sy) * dx; Z = lo[2] + (np.arange(n[2]) + sz) * dx
                ix = np.round((X - fo[0]) / fp).astype(int); iy = np.round((Y - fo[1]) / fp).astype(int); iz = np.round((Z - fo[2]) / fp).astype(int)
                okx = (ix >= 0) & (ix < F.shape[0]); oky = (iy >= 0) & (iy < F.shape[1]); okz = (iz >= 0) & (iz < F.shape[2])
                v = F[np.ix_(np.clip(ix, 0, F.shape[0] - 1), np.clip(iy, 0, F.shape[1] - 1), np.clip(iz, 0, F.shape[2] - 1))].astype(float)
                v *= okx[:, None, None] * oky[None, :, None] * okz[None, None, :]
                acc += v
    acc /= 64.0
    target = vol(load_part(cfg)) / dx ** 3
    vals = np.sort(acc[acc > 0])[::-1]
    thr = vals[min(int(round(target)), len(vals) - 1)] if len(vals) else 0.5
    m = acc >= max(thr, 0.3)
    np.savez_compressed(cache, m=m, o=lo)
    return m, lo

def silhouette(cfg, z_min=None):
    """Plan silhouette polygons (list of Nx2 arrays) of the casting, optionally only material above z_min."""
    from skimage import measure
    F, fo, fp = fine_voxels(cfg)
    if z_min is not None:
        z = fo[2] + np.arange(F.shape[2]) * fp
        F = F & (z >= z_min)[None, None, :]
    img = F.any(axis=2)
    out = []
    for c in measure.find_contours(np.pad(img.astype(float), 1), 0.5):
        out.append(np.c_[fo[0] + (c[:, 0] - 1) * fp, fo[1] + (c[:, 1] - 1) * fp])
    return out

def thin(F, fo, fp, axis, pos):
    k = int(round((pos - fo[axis]) / fp)); k = min(max(k, 0), F.shape[axis] - 1)
    return np.take(F, k, axis=axis)
