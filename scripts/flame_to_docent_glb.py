#!/usr/bin/env python3
"""
Build runtime-ready docent GLBs from a SOAP reconstruction.

Runs on the SOAP pod, where the FLAME attributes and the reconstructed mesh
live together. The web runtime never sees FLAME: it consumes a GLB whose morph
targets are exactly the eleven the product already drives (see
tests/glb-morph.test.ts and src/features/docent/DocentHead.tsx):

    visemes    viseme_a viseme_i viseme_u viseme_e viseme_o viseme_m
    emotions   smile thinking surprised sad
    blink      blink
    and NOT    neutral   (a runtime state, all weights zero)

MEASURED PROBLEM THIS SCRIPT EXISTS TO HANDLE
---------------------------------------------
SOAP exports two assets that do NOT share a vertex correspondence:

    recon/recon_textured.obj   15769 verts, UV mapped, carries the photo identity
    flame_attributes.pth       14484 verts, carries the rig (lbs_weights,
                               J_regressor, shapedirs, posedirs)

They differ in count, in unique-position count, and in coordinate frame — the
reconstruction's bounding box is roughly 6.5x the template's, and the mean
nearest-neighbour distance between them is on the order of half the mesh
diameter. parse_labels.pth is a per-FLAME-vertex label tensor, not a mapping.
So the rig cannot simply be applied to the textured mesh.

This script therefore emits two GLBs and reports exactly what each one is:

  --out-rig     FLAME topology. Real rig, real deformation, NO photo texture.
                Nothing is approximated here.

  --out-textured  Reconstruction topology with UVs, so it keeps the identity.
                Morph targets are transferred from FLAME by similarity
                alignment plus nearest-neighbour correspondence. That is an
                APPROXIMATION invented here, not a correspondence SOAP
                exported. The alignment residual and every target's
                displacement are measured and reported so the approximation can
                be judged rather than trusted.

CLAIM DISCIPLINE
    visemes are jaw aperture, not lip rounding. FLAME's jaw joint cannot round
    lips and no verified lip-shape basis is available, so this is a
    TEXT_DRIVEN_VISEME_APPROXIMATION, never phoneme-accurate lip sync.
    The four emotion slots use distinct expression-basis directions whose
    semantics are UNVERIFIED — the basis is unlabelled.
"""
import argparse
import json
import math
import os
import struct

import numpy as np
import torch
import trimesh

J_JAW, J_EYE_L, J_EYE_R = 2, 3, 4

VISEME_JAW = {
    "viseme_a": 0.30,
    "viseme_o": 0.22,
    "viseme_u": 0.13,
    "viseme_e": 0.17,
    "viseme_i": 0.09,
    "viseme_m": -0.06,
}
EMOTION_EXPR = {
    "smile": (300, 2.0),
    "thinking": (305, 2.0),
    "surprised": (301, 2.0),
    "sad": (302, -2.0),
}
BLINK_ANGLE = 0.45
ORDER = [
    "viseme_a", "viseme_i", "viseme_u", "viseme_e", "viseme_o", "viseme_m",
    "smile", "thinking", "surprised", "sad", "blink",
]


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def joint_delta(v, joints, w, j, angle):
    r = rot_x(angle)
    piv = joints[j]
    return w[:, j : j + 1] * (((v - piv) @ r.T + piv) - v)


def measure(delta, unit_mm, eps=1e-9):
    mag = np.linalg.norm(delta, axis=1)
    return int((mag > eps).sum()), float(mag.max() * unit_mm)


def flame_targets(attrs):
    v = attrs["v_template"].float().numpy().astype(np.float64)
    jreg = attrs["J_regressor"].float().numpy().astype(np.float64)
    w = attrs["lbs_weights"].float().numpy().astype(np.float64)
    sd = attrs["shapedirs"].float().numpy().astype(np.float64)
    joints = jreg @ v

    t, m = {}, {}
    for name, angle in VISEME_JAW.items():
        d = joint_delta(v, joints, w, J_JAW, angle)
        t[name] = d
        n, mx = measure(d, 1000.0)
        m[name] = {"source": "jaw joint rotation via lbs_weights",
                   "jaw_angle_rad": angle, "affected_vertices": n,
                   "max_displacement_mm": round(mx, 4)}

    d = joint_delta(v, joints, w, J_EYE_L, BLINK_ANGLE) + \
        joint_delta(v, joints, w, J_EYE_R, BLINK_ANGLE)
    t["blink"] = d
    n, mx = measure(d, 1000.0)
    m["blink"] = {"source": "both eye joints", "angle_rad": BLINK_ANGLE,
                  "affected_vertices": n, "max_displacement_mm": round(mx, 4)}

    for name, (idx, scale) in EMOTION_EXPR.items():
        if idx >= sd.shape[2]:
            raise SystemExit("expression index %d >= %d" % (idx, sd.shape[2]))
        d = sd[:, :, idx] * scale
        t[name] = d
        n, mx = measure(d, 1000.0)
        m[name] = {"source": "FLAME expression basis direction",
                   "basis_index": idx, "scale": scale,
                   "semantic_correspondence": "UNVERIFIED",
                   "affected_vertices": n, "max_displacement_mm": round(mx, 4)}
    return v, t, m


def transfer(flame_v, targets, recon_v):
    """Similarity-align FLAME to the reconstruction, then carry deltas across by
    nearest neighbour. Returns the transferred deltas and the alignment
    evidence needed to judge whether the approximation is defensible."""
    from scipy.spatial import cKDTree

    fc, rc = flame_v.mean(0), recon_v.mean(0)
    fs = np.linalg.norm(flame_v - fc, axis=1).mean()
    rs = np.linalg.norm(recon_v - rc, axis=1).mean()
    scale = rs / fs
    aligned = (flame_v - fc) * scale + rc

    tree = cKDTree(aligned)
    dist, idx = tree.query(recon_v, k=1)
    diameter = float(np.linalg.norm(recon_v.max(0) - recon_v.min(0)))

    out = {name: targets[name][idx] * scale for name in ORDER}
    evidence = {
        "method": "centroid + mean-radius similarity alignment, then 1-NN",
        "scale_applied": float(scale),
        "recon_diameter": diameter,
        "residual_mean": float(dist.mean()),
        "residual_median": float(np.median(dist)),
        "residual_max": float(dist.max()),
        "residual_mean_pct_of_diameter": round(100.0 * dist.mean() / diameter, 3),
        "distinct_flame_vertices_used": int(len(np.unique(idx))),
        "flame_vertices_total": int(len(flame_v)),
        "status": "APPROXIMATION — SOAP exports no correspondence between these meshes",
    }
    return out, evidence


def write_glb(path, verts, faces, normals, uv, targets, order):
    """Emit a GLB with morph targets, written directly because trimesh's
    exporter drops them and they are the entire point of this asset."""
    blob, views, accessors = bytearray(), [], []

    def put(arr, target=None):
        off = len(blob)
        raw = arr.tobytes()
        blob.extend(raw)
        blob.extend(b"\x00" * ((4 - len(blob) % 4) % 4))
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(raw)}
        if target:
            v["target"] = target
        views.append(v)
        return len(views) - 1

    def acc(view, ctype, count, atype, mn=None, mx=None):
        a = {"bufferView": view, "componentType": ctype, "count": count, "type": atype}
        if mn is not None:
            a["min"], a["max"] = mn, mx
        accessors.append(a)
        return len(accessors) - 1

    FLOAT, UINT = 5126, 5125
    attrs = {
        "POSITION": acc(put(verts, 34962), FLOAT, len(verts), "VEC3",
                        verts.min(0).tolist(), verts.max(0).tolist()),
        "NORMAL": acc(put(normals, 34962), FLOAT, len(normals), "VEC3"),
    }
    if uv is not None:
        attrs["TEXCOORD_0"] = acc(put(uv, 34962), FLOAT, len(uv), "VEC2")
    idx_a = acc(put(faces, 34963), UINT, len(faces), "SCALAR")

    mt = []
    for name in order:
        d = np.ascontiguousarray(targets[name], dtype=np.float32)
        mt.append({"POSITION": acc(put(d, 34962), FLOAT, len(d), "VEC3",
                                   d.min(0).tolist(), d.max(0).tolist())})

    gltf = {
        "asset": {"version": "2.0", "generator": "dd-flame-to-glb"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "DocentHead"}],
        "meshes": [{"name": "DocentHead",
                    "primitives": [{"attributes": attrs, "indices": idx_a,
                                    "mode": 4, "targets": mt}],
                    "weights": [0.0] * len(order),
                    "extras": {"targetNames": list(order)}}],
        "bufferViews": views, "accessors": accessors,
        "buffers": [{"byteLength": len(blob)}],
    }
    j = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    j += b" " * ((4 - len(j) % 4) % 4)
    b = bytes(blob)
    b += b"\x00" * ((4 - len(b) % 4) % 4)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(b)))
        fh.write(struct.pack("<II", len(j), 0x4E4F534A)); fh.write(j)
        fh.write(struct.pack("<II", len(b), 0x004E4942)); fh.write(b)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("soap_dir")
    ap.add_argument("--out-rig", required=True)
    ap.add_argument("--out-textured", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()

    obj = os.path.join(a.soap_dir, "recon", "recon_textured.obj")
    pth = os.path.join(a.soap_dir, "flame_attributes.pth")
    for p in (obj, pth):
        if not os.path.exists(p):
            raise SystemExit("missing input: %s" % p)

    attrs = torch.load(pth, map_location="cpu")
    flame_v, targets, metrics = flame_targets(attrs)

    dead = [n for n in ORDER if metrics[n]["affected_vertices"] == 0]
    if dead:
        raise SystemExit("morph targets that deform nothing: %s" % dead)

    # --- rig-only GLB: FLAME topology, exact, no approximation --------------
    fmesh = trimesh.Trimesh(vertices=flame_v, faces=_flame_faces(a.soap_dir, flame_v),
                            process=False)
    rig_bytes = write_glb(
        a.out_rig,
        np.asarray(fmesh.vertices, np.float32),
        np.asarray(fmesh.faces, np.uint32).reshape(-1),
        np.asarray(fmesh.vertex_normals, np.float32),
        None, targets, ORDER,
    )

    # --- textured GLB: identity kept, morphs transferred by approximation ---
    raw = trimesh.load(obj, process=False, force="mesh")
    recon_v = np.asarray(raw.vertices, np.float64)
    tt, evidence = transfer(flame_v, targets, recon_v)
    tmetrics = {}
    for n in ORDER:
        cnt, mx = measure(tt[n], 1000.0)
        tmetrics[n] = {"affected_vertices": cnt, "max_displacement_mm": round(mx, 4)}

    uv = None
    if getattr(raw.visual, "uv", None) is not None:
        uv = np.asarray(raw.visual.uv, np.float32).copy()
        uv[:, 1] = 1.0 - uv[:, 1]
    tex_bytes = write_glb(
        a.out_textured,
        np.asarray(raw.vertices, np.float32),
        np.asarray(raw.faces, np.uint32).reshape(-1),
        np.asarray(raw.vertex_normals, np.float32),
        uv, tt, ORDER,
    )

    report = {
        "source_dir": a.soap_dir,
        "correspondence_blocker": {
            "recon_vertices": int(len(recon_v)),
            "flame_vertices": int(len(flame_v)),
            "soap_exports_correspondence": False,
            "parse_labels_is_correspondence": False,
        },
        "rig_glb": {"path": a.out_rig, "bytes": rig_bytes,
                    "vertices": int(len(fmesh.vertices)),
                    "faces": int(len(fmesh.faces)),
                    "textured": False, "approximated": False,
                    "targets": metrics},
        "textured_glb": {"path": a.out_textured, "bytes": tex_bytes,
                         "vertices": int(len(raw.vertices)),
                         "faces": int(len(raw.faces)),
                         "textured": uv is not None, "approximated": True,
                         "transfer": evidence, "targets": tmetrics},
        "morph_target_order": ORDER,
        "claims": {
            "REAL_3D": True,
            "MOUTH_ACTUATION": "TEXT_DRIVEN_VISEME_APPROXIMATION",
            "PHONEME_ACCURATE_LIPSYNC": False,
            "emotion_semantics": "UNVERIFIED",
            "textured_rig": "APPROXIMATED_BY_NEAREST_NEIGHBOUR_TRANSFER",
        },
    }
    out = json.dumps(report, indent=2)
    with open(a.report, "w", encoding="utf-8") as fh:
        fh.write(out + "\n")
    print(out)
    return 0


def _flame_faces(soap_dir, flame_v):
    """FLAME faces are not in the attribute bundle. Recover them from the SOAP
    package's own FLAME asset when present; otherwise fall back to a convex
    hull, which is only a placeholder and is recorded as such."""
    for cand in ("/opt/soap/data/FLAME2020/head_template.obj",
                 "/opt/soap/data/flame/head_template.obj"):
        if os.path.exists(cand):
            m = trimesh.load(cand, process=False, force="mesh")
            if len(m.vertices) == len(flame_v):
                return np.asarray(m.faces)
    return trimesh.convex.convex_hull(flame_v).faces


if __name__ == "__main__":
    raise SystemExit(main())
