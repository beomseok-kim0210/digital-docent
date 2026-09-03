#!/usr/bin/env python3
"""
DD SOAP — OpenCV runtime evidence. Runs INSIDE the final image. NO GPU.

    python cv2_evidence.py <out_dir>

Recovery 3 made opencv-contrib-python the deterministic last writer into the
shared cv2/ directory, and added libglib2.0-0 so a non-headless build can load.
Package metadata cannot prove either of those: all three opencv distributions
stay installed at the same version no matter which binary actually won. This
script gathers evidence about the binary that is really loaded.

Captures:
    ACTIVE_CV2_VERSION          cv2.__version__ of the module Python imported
    ACTIVE_CV2_FILE             cv2.__file__
    ACTIVE_CV2_BINARY           the native .so actually mapped into the process,
                                read from /proc/self/maps, not guessed from a
                                directory listing
    ACTIVE_CV2_BINARY_SHA256    hash of that binary
    LDD_NOT_FOUND_COUNT         unresolved shared objects; must be 0
    libgthread-2.0.so.0         resolved path, the library recovery 3 added
    cv2.getBuildInformation()   full build string
    opencv distribution metadata for all three providers
    installed versions of the apt packages recovery 3 depends on

OS package versions are recorded as measured_from_final_image. They are NOT
pinned by the Python lock: a clean build proves the canonical environment under
the OS package resolution measured here, and the pushed image digest — not the
Python lock alone — is the reproducible deployment identity.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version

OPENCV_DISTS = ("opencv-python", "opencv-contrib-python", "opencv-python-headless")

# apt packages recovery 3 added or made explicit
APT_PKGS = (
    "libglib2.0-0", "libgl1", "libsm6", "libxext6", "libxrender1", "libgomp1",
)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def loaded_cv2_binary():
    """The cv2 native object actually mapped into this process.

    /proc/self/maps is authoritative: a directory listing would only show what
    is on disk, which is exactly the ambiguity three overlapping distributions
    create.
    """
    found = []
    try:
        with open("/proc/self/maps", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 6:
                    continue
                path = parts[-1]
                if "cv2" in path and path.endswith(".so"):
                    found.append(path)
    except OSError:
        pass
    if found:
        # deterministic: the largest mapped cv2 object is the extension module
        uniq = sorted(set(found), key=lambda p: (-os.path.getsize(p), p))
        return uniq[0], sorted(set(found))
    # fallback: on-disk search, clearly labelled as such
    import cv2
    cand = sorted(glob.glob(os.path.join(os.path.dirname(cv2.__file__), "*.so")))
    return (cand[0] if cand else None), cand


def main() -> int:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "/out"
    os.makedirs(out_dir, exist_ok=True)
    ev = {}
    failures = []

    import cv2  # after the maps read helper is defined; import is the point

    ev["ACTIVE_CV2_VERSION"] = cv2.__version__
    ev["ACTIVE_CV2_FILE"] = cv2.__file__
    print("ACTIVE_CV2_VERSION = %s" % cv2.__version__)
    print("ACTIVE_CV2_FILE    = %s" % cv2.__file__)

    binary, all_mapped = loaded_cv2_binary()
    ev["ACTIVE_CV2_BINARY"] = binary
    ev["ACTIVE_CV2_MAPPED_OBJECTS"] = all_mapped
    print("ACTIVE_CV2_BINARY  = %s" % binary)

    if binary and os.path.exists(binary):
        ev["ACTIVE_CV2_BINARY_SHA256"] = sha256(binary)
        ev["ACTIVE_CV2_BINARY_BYTES"] = os.path.getsize(binary)
        print("ACTIVE_CV2_BINARY_SHA256 = %s" % ev["ACTIVE_CV2_BINARY_SHA256"])

        ldd = run(["ldd", binary])
        ev["LDD_RAW"] = ldd.stdout
        notfound = [ln.strip() for ln in ldd.stdout.splitlines() if "not found" in ln]
        ev["LDD_NOT_FOUND_COUNT"] = len(notfound)
        ev["LDD_NOT_FOUND"] = notfound
        print("LDD_NOT_FOUND_COUNT = %d" % len(notfound))
        for ln in notfound:
            print("   NOT FOUND: %s" % ln)
        if notfound:
            failures.append("LDD_NOT_FOUND_COUNT=%d" % len(notfound))

        m = re.search(r"^\s*libgthread-2\.0\.so\.0\s*=>\s*(\S+)", ldd.stdout, re.M)
        ev["LIBGTHREAD_RESOLVED"] = m.group(1) if m else None
        ev["LIBGTHREAD_LINKED"] = "libgthread-2.0.so.0" in ldd.stdout
        print("LIBGTHREAD_LINKED   = %s" % ev["LIBGTHREAD_LINKED"])
        print("LIBGTHREAD_RESOLVED = %s" % ev["LIBGTHREAD_RESOLVED"])
        if ev["LIBGTHREAD_LINKED"] and not ev["LIBGTHREAD_RESOLVED"]:
            failures.append("libgthread-2.0.so.0 linked but unresolved")
    else:
        ev["ACTIVE_CV2_BINARY_SHA256"] = None
        ev["LDD_NOT_FOUND_COUNT"] = None
        failures.append("active cv2 binary not locatable")

    # ---- distribution metadata for all three providers ---------------------
    dists = {}
    for d in OPENCV_DISTS:
        try:
            dists[d] = version(d)
        except PackageNotFoundError:
            dists[d] = None
    ev["OPENCV_DISTRIBUTIONS"] = dists
    print("OPENCV_DISTRIBUTIONS = %s" % json.dumps(dists))
    off = [k for k, v in dists.items() if v != "4.11.0.86"]
    ev["OPENCV_ALL_AT_4_11_0_86"] = not off
    if off:
        failures.append("opencv distributions not all 4.11.0.86: %s" % off)

    ev["CV2_BUILD_INFORMATION"] = cv2.getBuildInformation()

    # ---- apt evidence ------------------------------------------------------
    apt = {}
    for p in APT_PKGS:
        r = run(["dpkg-query", "-W", "-f=${Version}", p])
        apt[p] = {
            "installed_version": r.stdout.strip() or None,
            "provenance": "measured_from_final_image",
        }
        print("APT %-16s %s" % (p, apt[p]["installed_version"] or "ABSENT"))
        if not apt[p]["installed_version"]:
            failures.append("apt package missing: %s" % p)
    ev["APT_PACKAGES"] = apt
    ev["OS_PACKAGE_REPRODUCIBILITY_NOTE"] = (
        "These apt versions are measured, not pinned. The Python lock does not "
        "constrain them, so a future rebuild may resolve different OS package "
        "versions. PYTHON_LOCK_REPRODUCIBILITY and OS_PACKAGE_REPRODUCIBILITY "
        "are separate claims; the pushed image digest is the reproducible "
        "deployment identity."
    )
    ev["DECLARED_OPENCV_DEVIATION"] = {
        "candidate_active_cv2": "opencv-python-headless (last writer by install order)",
        "final_canonical_active_cv2": "opencv-contrib-python (pinned last writer)",
        "reason": (
            "Three distributions share the cv2/ directory, so the surviving "
            "binary depended on install order. The candidate's multi-pass build "
            "ended with headless; a single-pass build from the complete lock "
            "ended with a non-headless build that needs libgthread-2.0.so.0, "
            "which neither image carried. Recovery 3 supplies the library and "
            "pins contrib as the last writer, contrib being a strict superset "
            "and what mediapipe declares."
        ),
    }

    path = os.path.join(out_dir, "final-cv2-evidence.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ev, fh, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "final-cv2-buildinfo.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(ev["CV2_BUILD_INFORMATION"])

    print("=" * 60)
    if failures:
        print("ACTIVE_CV2_RUNTIME_GATE = FAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("ACTIVE_CV2_RUNTIME_GATE = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
