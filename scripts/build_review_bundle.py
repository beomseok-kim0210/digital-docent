#!/usr/bin/env python3
"""
Assemble the Human review bundle from a preserved SOAP output tree.

    scripts/build_review_bundle.py <qka2_raw_dir> <out_dir>

Runs locally against the archive already pulled off the Pod, so no GPU time is
spent on presentation. SOAP itself renders six views and two videos; this
gathers them, builds one contact sheet so the Human can judge identity from a
single image, and records what each artifact does and does not prove.

The Human scores identity, appeal, stylization intent and uncanniness. Nothing
here scores them, and nothing here should be read as claiming the likeness is
good — only that these are the real generated views.
"""
import hashlib
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw

# SOAP's own six-view render order. The camera angle behind each index is NOT
# documented in the output and an earlier guess at it was wrong — index 2 is the
# back of the head, not a right-45. Naming them by their source index is the
# only labelling that is actually verified, and a wrong angle label would
# corrupt the very Human judgement this bundle exists to support.
VIEW_LABELS = [
    ("0.png", "view_0.png", "view 0  (frontal)"),
    ("1.png", "view_1.png", "view 1"),
    ("2.png", "view_2.png", "view 2"),
    ("3.png", "view_3.png", "view 3"),
    ("4.png", "view_4.png", "view 4"),
    ("5.png", "view_5.png", "view 5"),
]

README = """DIGITAL DOCENT — QK-A2 HUMAN REVIEW
====================================

Open contact_sheet.png first. It is the six SOAP views in one image, and it is
what the identity judgement should be made from.

WHAT EACH FILE IS

  contact_sheet.png   all six generated views in one image
  view_0 … view_5.png the individual views at full resolution.
                      view_0 is frontal. The camera angles behind the other
                      five are not documented in SOAP's output, so they are
                      deliberately numbered rather than named — an earlier
                      guess labelled the back of the head as "right 45".
  reconstruction.mp4  SOAP's own turntable of the reconstructed head
  rig_motion.mp4      SOAP's own animation render — this is SOAP's animation,
                      not the web runtime's rig being driven
  albedo.png          the texture SOAP fitted to the mesh
  input.webp          the exact image this was generated from

WHAT THIS DOES AND DOES NOT PROVE

  Proven: a real 3D mesh was reconstructed, and a FLAME rig with working jaw,
  eye and expression controls exists. Both were measured.

  Not proven here: that the web runtime animates this asset. The textured GLB's
  morph targets were transferred from the FLAME rig by nearest-neighbour
  approximation, because SOAP exports no correspondence between its textured
  mesh and its rig. That approximation's alignment residual is recorded in
  evidence/glb_report.json.

  Never claimed: phoneme-accurate lip sync. The visemes are jaw apertures.

YOUR SCORES (1-5; uncanny is better when lower)

  identity recognizability   ___
  character appeal           ___
  stylization intentionality ___
  uncanny                    ___

  Kill if identity <= 2, or appeal <= 2, or it is not controllable real 3D,
  or there is no plausible mouth/voice path.
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def contact_sheet(images, out_path, cols=3, cell=420, pad=10):
    """One image the Human can open and judge from, rather than six files."""
    rows = (len(images) + cols - 1) // cols
    label_h = 26
    W = cols * cell + (cols + 1) * pad
    H = rows * (cell + label_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (W, H), (24, 24, 27))
    draw = ImageDraw.Draw(sheet)
    for i, (path, label) in enumerate(images):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + label_h + pad)
        im = Image.open(path).convert("RGB")
        im.thumbnail((cell, cell), Image.LANCZOS)
        sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        draw.text((x + 4, y + cell + 6), label, fill=(215, 215, 220))
    sheet.save(out_path, "PNG", optimize=True)
    return out_path


def main():
    raw = sys.argv[1]
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    six = os.path.join(raw, "6-views")
    newest = os.path.join(six, "newest")

    copied, sheet_inputs = [], []
    for src_name, dst_name, label in VIEW_LABELS:
        src = os.path.join(six, "images", src_name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(out, dst_name)
        shutil.copy2(src, dst)
        copied.append(dst)
        sheet_inputs.append((dst, label))

    for src, dst_name in (
        (os.path.join(newest, "video", "reconstruction.mp4"), "reconstruction.mp4"),
        (os.path.join(newest, "video", "animation-0000.mp4"), "rig_motion.mp4"),
        (os.path.join(newest, "recon", "recon_textured_albedo.png"), "albedo.png"),
    ):
        if os.path.exists(src):
            dst = os.path.join(out, dst_name)
            shutil.copy2(src, dst)
            copied.append(dst)

    if sheet_inputs:
        copied.append(contact_sheet(sheet_inputs, os.path.join(out, "contact_sheet.png")))

    readme = os.path.join(out, "README-HUMAN-REVIEW.txt")
    with open(readme, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(README)
    copied.append(readme)

    files = {}
    total = 0
    for p in copied:
        b = os.path.getsize(p)
        total += b
        files[os.path.basename(p)] = {"bytes": b, "sha256": sha256(p)}

    manifest = {
        "source_raw_dir": raw,
        "file_count": len(files),
        "total_bytes": total,
        "files": files,
        "claims": {
            "REAL_3D": "measured — mesh and FLAME rig both present",
            "views_are_soap_renders": True,
            "rig_motion_is_soap_animation_not_runtime": True,
            "PHONEME_ACCURATE_LIPSYNC": False,
            "identity_and_appeal": "NOT SCORED — Human gate",
        },
    }
    mpath = os.path.join(out, "review-manifest.json")
    with open(mpath, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    print("REVIEW_FILE_COUNT = %d" % (len(files) + 1))
    print("REVIEW_TOTAL_BYTES = %d" % (total + os.path.getsize(mpath)))
    for name in sorted(files):
        print("  %-24s %10d  %s" % (name, files[name]["bytes"], files[name]["sha256"][:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
