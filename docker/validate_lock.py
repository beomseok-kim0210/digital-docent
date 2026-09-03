#!/usr/bin/env python3
"""
DD SOAP — build-time lock validation.  NO GPU REQUIRED.

(a) Metadata assertions for every locked package. importlib.metadata reads
    dist-info; it does not execute the package, so nothing touches CUDA.
    This is the check that catches the nvdiffrast "UNKNOWN 0.0.0" failure mode,
    where only _nvdiffrast_c*.so lands and the package directory is absent.

(b) Real imports only for modules that do not link CUDA at import time.
    pytorch3d / nvdiffrast.torch / torch_sparse / torch_scatter load CUDA
    extensions and need libcuda.so.1, which a GPU-less `docker build` does not
    have. Those are verified at runtime by validate_runtime.py (stage S1).

    deep3dface/__init__.py is empty at the pinned SHA, so importing it is
    side-effect free. The namespace was read from the repository tree at that
    SHA, not guessed.
"""
import importlib
import sys
from importlib.metadata import PackageNotFoundError, version

# key = distribution name (not import name); value = expected version
EXPECT = {
    # Tier 0 — core runtime, frozen by Human runbook
    "torch": "2.3.1+cu121",
    "torchvision": "0.18.1+cu121",
    "torchaudio": "2.3.1+cu121",
    # Tier 1 — git dependencies, exact revisions
    "pytorch3d": "0.7.9",
    "nvdiffrast": "0.3.3",
    "chumpy": "0.71",
    "smplx": "0.0.1",
    "deep3dface": "0.0.1",
    # Tier 1 — compiled extensions
    "torch-sparse": "0.6.18",
    "torch-scatter": "2.1.2",
    "dlib": "20.0.1",
    # Tier 1 — drift corrections
    "numpy": "1.23.1",
    "kiui": "0.2.17",
    "mediapipe": "0.10.21",
    "protobuf": "4.25.8",
    "tensorboard": "2.19.0",
    # Tier 1 — contemporaneous alignment
    "face-alignment": "1.4.1",
    "trimesh": "4.7.1",
    "kornia": "0.8.1",
    # Tier 1 — pinned upstream by SOAP
    "transformers": "4.44.2",
    "diffusers": "0.27.2",
    "imageio-ffmpeg": "0.4.7",
    "huggingface-hub": "0.24.6",
    # build tooling
    "pip": "26.2.1",
    "setuptools": "59.6.0",
    "wheel": "0.48.0",
    "ninja": "1.13.2",
}

CPU_SAFE_IMPORTS = [
    "numpy",
    "torch",
    "trimesh",
    "chumpy",
    "smplx",
    "deep3dface",
    "dlib",
    "kiui.op",
    "kornia",
    "mediapipe",
    "mediapipe.framework.formats.landmark_pb2",
]

# (module, attribute) probes — for APIs exposed as an alias rather than a real
# submodule, where import_module() would report a false failure.
#
# mediapipe.solutions has NEVER been a module path in any version: the package
# tree is mediapipe/python/solutions/, and the wheel's __init__.py re-exports it
# with `import mediapipe.python.solutions as solutions`. SOAP consumes it the
# same way — src/utils/vis.py:4 `from mediapipe import solutions`.
#
# This attribute is exactly what the drift broke: mediapipe 1.0.1 dropped the
# legacy alias, producing the measured pod failure
#     ImportError: cannot import name 'solutions' from 'mediapipe'
# so probing it by attribute is both correct and the regression guard.
CPU_SAFE_SYMBOLS = [
    ("mediapipe", "solutions"),
]

DEFERRED_TO_RUNTIME = [
    "pytorch3d",
    "nvdiffrast.torch",
    "torch_sparse",
    "torch_scatter",
]


def main() -> int:
    bad = []
    for dist, want in EXPECT.items():
        try:
            got = version(dist)
        except PackageNotFoundError:
            bad.append((dist, "MISSING", want))
            continue
        if got != want:
            bad.append((dist, got, want))

    # explicit regression guard for the observed nvdiffrast failure mode
    try:
        if version("nvdiffrast") == "0.0.0":
            bad.append(("nvdiffrast", "UNKNOWN-0.0.0 regression", "0.3.3"))
    except PackageNotFoundError:
        pass

    if bad:
        print("LOCK_VIOLATION", file=sys.stderr)
        for dist, got, want in bad:
            print("  %-22s got=%-28s want=%s" % (dist, got, want), file=sys.stderr)
        return 1

    failed = []
    for mod in CPU_SAFE_IMPORTS:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001 - report, do not mask
            failed.append((mod, type(exc).__name__, str(exc)[:160]))

    for mod, attr in CPU_SAFE_SYMBOLS:
        try:
            obj = importlib.import_module(mod)
            if not hasattr(obj, attr):
                failed.append((mod + ":" + attr, "AttributeError", "alias missing"))
        except Exception as exc:  # noqa: BLE001
            failed.append((mod + ":" + attr, type(exc).__name__, str(exc)[:160]))

    if failed:
        print("CPU_IMPORT_FAILURE", file=sys.stderr)
        for mod, kind, msg in failed:
            print("  %-42s %s: %s" % (mod, kind, msg), file=sys.stderr)
        return 1

    print(
        "BUILD_VALIDATION_OK  packages=%d  cpu_imports=%d  symbol_probes=%d"
        % (len(EXPECT), len(CPU_SAFE_IMPORTS), len(CPU_SAFE_SYMBOLS))
    )
    print("DEFERRED_TO_RUNTIME_S1: " + ", ".join(DEFERRED_TO_RUNTIME))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
