#!/usr/bin/env python3
"""
DD SOAP — runtime validation, stages S0 / S1 / S2.  REQUIRES A GPU.

Run this on the pod before any SOAP command. It covers what
validate_lock.py deliberately could not check at Docker build time, because a
GPU-less build has no libcuda.so.1 and no CUDA device.

  S0  infrastructure   — driver, device, toolkit, torch/CUDA binding
  S1  critical imports — the CUDA-linked modules deferred from build time,
                         plus a re-run of the CPU-safe set in the real image
  S2  nvdiffrast smoke — rasterize one synthetic triangle with
                         RasterizeCudaContext. Uses NO SOAP asset, so a failure
                         is unambiguously the rasterizer and not the pipeline.

Exit code 0 only if every stage passes. Any non-zero exit is a STOP:
terminate the pod rather than spending GPU time on a broken environment.
"""
import subprocess
import sys
import time

# Reference values measured on the 2026-09-02 A40 pod.
REF = {
    "driver": "570.211.01",
    "nvcc": "12.1.105",
    "gpu": "A40",
    "torch": "2.3.1+cu121",
    "cuda": "12.1",
    "smoke_covered_px": 1352,
}


def stage_s0() -> list:
    fails = []
    print("=== S0 INFRASTRUCTURE ===")
    for cmd in (["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader"],
                ["nvcc", "--version"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            print("  $ %s\n%s" % (" ".join(cmd), out.stdout.strip()))
        except Exception as exc:  # noqa: BLE001
            fails.append("S0 %s: %s" % (cmd[0], exc))

    import torch

    print("  torch            %s" % torch.__version__)
    print("  torch.version.cuda %s" % torch.version.cuda)
    print("  cuda available   %s" % torch.cuda.is_available())
    print("  device_count     %d" % torch.cuda.device_count())
    if torch.cuda.is_available():
        print("  device_name      %s" % torch.cuda.get_device_name(0))

    if torch.__version__ != REF["torch"]:
        fails.append("S0 torch %s != %s" % (torch.__version__, REF["torch"]))
    if torch.version.cuda != REF["cuda"]:
        fails.append("S0 cuda %s != %s" % (torch.version.cuda, REF["cuda"]))
    if not torch.cuda.is_available():
        fails.append("S0 torch.cuda.is_available() is False")
    return fails


def stage_s1() -> list:
    fails = []
    print("=== S1 CRITICAL IMPORTS ===")
    mods = [
        # deferred from build time (CUDA-linked)
        "pytorch3d",
        "nvdiffrast",
        "nvdiffrast.torch",
        "torch_sparse",
        "torch_scatter",
        # re-verified in the real image
        "numpy",
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
    import importlib

    for mod in mods:
        try:
            importlib.import_module(mod)
            print("  PASS  %s" % mod)
        except Exception as exc:  # noqa: BLE001
            print("  FAIL  %s  %s: %s" % (mod, type(exc).__name__, str(exc)[:140]))
            fails.append("S1 %s" % mod)

    # mediapipe.solutions is an alias attribute, never a module path: the tree is
    # mediapipe/python/solutions/ and the wheel re-exports it. SOAP consumes it
    # the same way (src/utils/vis.py:4 `from mediapipe import solutions`), and
    # dropping this alias is exactly what mediapipe 1.0.1 did, producing the
    # measured pod failure. Probe by attribute, not by import_module.
    for mod, attr in [("mediapipe", "solutions")]:
        try:
            obj = importlib.import_module(mod)
            if hasattr(obj, attr):
                print("  PASS  %s.%s (alias)" % (mod, attr))
            else:
                print("  FAIL  %s.%s alias missing" % (mod, attr))
                fails.append("S1 %s.%s" % (mod, attr))
        except Exception as exc:  # noqa: BLE001
            print("  FAIL  %s.%s  %s" % (mod, attr, type(exc).__name__))
            fails.append("S1 %s.%s" % (mod, attr))
    return fails


def stage_s2() -> list:
    """Synthetic triangle only. No SOAP asset is touched."""
    fails = []
    print("=== S2 NVDIFFRAST CUDA SMOKE ===")
    try:
        import torch
        import nvdiffrast.torch as dr

        ctx = dr.RasterizeCudaContext()
        pos = torch.tensor(
            [[[-0.8, -0.8, 0.0, 1.0], [0.8, -0.8, 0.0, 1.0], [0.0, 0.8, 0.0, 1.0]]],
            dtype=torch.float32,
            device="cuda",
        )
        tri = torch.tensor([[0, 1, 2]], dtype=torch.int32, device="cuda")
        t0 = time.time()
        rast, _ = dr.rasterize(ctx, pos, tri, resolution=[64, 64])
        torch.cuda.synchronize()
        dt_ms = (time.time() - t0) * 1000.0
        covered = int((rast[..., 3] > 0).sum().item())
        print("  covered_px %d  (reference %d)" % (covered, REF["smoke_covered_px"]))
        print("  elapsed_ms %.2f" % dt_ms)
        if covered <= 0:
            fails.append("S2 covered_px == 0")
    except Exception as exc:  # noqa: BLE001
        print("  FAIL  %s: %s" % (type(exc).__name__, str(exc)[:200]))
        fails.append("S2 rasterize")
    return fails


def main() -> int:
    fails = stage_s0() + stage_s1() + stage_s2()
    print("=" * 46)
    if fails:
        print("RUNTIME_VALIDATION_FAIL")
        for f in fails:
            print("  " + f)
        print("ACTION: do not proceed to SOAP. Terminate the pod.")
        return 1
    print("RUNTIME_VALIDATION_OK  S0 S1 S2 all passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
