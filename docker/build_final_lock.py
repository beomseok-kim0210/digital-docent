#!/usr/bin/env python3
"""
DD SOAP — M2: generate the canonical final LOCK SET from a candidate manifest.

    python build_final_lock.py <manifest_dir> <out_dir>

requirements-dd-lock.txt alone is NOT the lock. The canonical environment is a
LOCK SET of ordered layers, because several distributions must be installed by
dedicated layers and would be wrong to place in a plain requirements file:

  1 build_tools     pip/setuptools/wheel/ninja — pinned before anything else
  2 torch_tier      needs --index-url cu121, and must precede every
                    --no-build-isolation build that imports torch at build time
  3 dlib            isolated: it failed inside the aggregate build on the pod
                    and succeeded standalone. Root cause UNKNOWN; this is a
                    mitigation, not a proven fix.
  4 main_lock       requirements-dd-lock.txt — 4 git packages + all PyPI
  5 smplx_no_deps   --no-deps, because its setup.py at the pinned SHA carries
                    an unpinned direct git URL for nvdiffrast

Being excluded from requirements-dd-lock.txt therefore does NOT mean unlocked.
Every distribution in the image must be covered by exactly one layer, and
lockset.json makes the order and the coverage machine-verifiable.

Emits:
    requirements-dd-lock.txt
    requirements-dd-lock.provenance.json
    lockset.json
    tier2-recovery-report.txt

PROVENANCE RULE, enforced in code and not negotiable:

    Versions measured in the 2026-09-03 candidate image are labelled
    measured_from_candidate_image. They are NEVER relabelled as the
    2026-09-02 RunPod measurements. The pod's Tier-2 versions were never
    recorded and remain unrecoverable. The candidate image establishes a NEW
    canonical deterministic environment going forward; it does not prove
    equality with the pod environment.
"""
import json
import os
import sys

TORCH_STACK = ("torch", "torchvision", "torchaudio")
BUILD_TOOLS = ("pip", "setuptools", "wheel", "ninja")
DEDICATED = ("dlib",)
NO_DEPS_PKGS = ("smplx",)

# Distributions installed by a dedicated layer rather than by the main
# requirements file. Excluded from the body, still fully locked.
EXCLUDE = set(TORCH_STACK) | set(BUILD_TOOLS) | set(DEDICATED) | set(NO_DEPS_PKGS)

# Measured on the RunPod A40 pod, 2026-09-02, from filtered `pip list`.
# Everything else in the image was first measured in the candidate build.
POD_MEASURED = {
    "torch", "torchvision", "torchaudio", "pytorch3d", "nvdiffrast", "chumpy",
    "smplx", "deep3dface", "torch-sparse", "torch-scatter", "dlib", "numpy",
    "kiui", "mediapipe", "protobuf", "tensorboard", "face-alignment",
    "trimesh", "kornia", "transformers", "diffusers", "huggingface-hub",
    "pip", "setuptools", "wheel", "ninja",
}

# Declared upstream by SOAP requirements.txt; the pod's installed build of this
# was never measured.
REPORTED_BY_SOURCE = {"imageio-ffmpeg"}

# How each git revision was SELECTED. The commit actually installed is always
# measured_from_candidate_image; these four must never be promoted to measured.
GIT_SHA_SELECTION = {
    "nvdiffrast": (
        "measured_from_execution_log",
        "SHA read from the successful 2026-09-02 install command. Repository "
        "HEAD installs as UNKNOWN 0.0.0 with project name 'unknown'.",
    ),
    "pytorch3d": (
        "historically_derived",
        "main@2026-08-27T13:32:44Z, default-branch HEAD throughout the run. "
        "__version__ at this SHA is 0.7.9, matching the pod measurement.",
    ),
    "chumpy": (
        "historically_derived",
        "master@2025-08-18T15:12:28Z, default-branch HEAD throughout the run. "
        "chumpy/version.py at this SHA is 0.71, matching the pod measurement.",
    ),
    "smplx": (
        "historically_derived",
        "main@2025-06-24T00:52:08Z, default-branch HEAD throughout the run. "
        "Version corroboration is weak: the fork is 0.0.1 at every commit.",
    ),
    "deep3dface": (
        "historically_derived",
        "main@2025-04-08T12:55:36Z, default-branch HEAD throughout the run. "
        "Version corroboration is weak: the fork is 0.0.1 at every commit.",
    ),
}

SMPLX_REASON = (
    "setup.py at the pinned SHA declares "
    "'nvdiffrast @ git+https://github.com/NVlabs/nvdiffrast.git' with no "
    "revision. Resolving it pulls mutable HEAD, which conflicts with the "
    "verified nvdiffrast revision. pip constraints do not apply to direct URL "
    "requirements, so dependency installation is controlled externally "
    "instead. Upstream source is NOT patched and the smplx SHA is unchanged."
)

DLIB_REASON = (
    "Failed inside the aggregate requirements build on the pod (gmake Error 2) "
    "and succeeded standalone. Resource exhaustion was hypothesised and "
    "DISPROVEN by measurement. ROOT CAUSE UNKNOWN; isolation is a mitigation, "
    "not a proven fix."
)


def pip_vcs_url(du):
    """Recombine a PEP 610 direct_url record into a pip-installable requirement.

    direct_url.json stores the bare repository URL in `url` and the VCS scheme
    separately in vcs_info.vcs, e.g.
        url = "https://github.com/NVlabs/nvdiffrast.git", vcs = "git"
    pip needs "git+https://github.com/NVlabs/nvdiffrast.git@<commit>". Emitting
    the bare URL would make pip treat it as an archive download instead.
    """
    return "%s+%s@%s" % (du.get("vcs"), du.get("url"), du.get("commit_id"))


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(path, default=""):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main() -> int:
    man = sys.argv[1] if len(sys.argv) > 1 else "manifest"
    out = sys.argv[2] if len(sys.argv) > 2 else "docker"
    os.makedirs(out, exist_ok=True)

    pkgs = load(os.path.join(man, "candidate-python-packages.json"), {}) or {}
    direct = load(os.path.join(man, "candidate-direct-urls.json"), {}) or {}
    tier2 = load(os.path.join(man, "candidate-tier2-resolution.json"), {}) or {}
    metrics = load(os.path.join(man, "candidate-build-metrics.json"), {}) or {}
    soap_sha = read(os.path.join(man, "candidate-soap-sha.txt")).strip()

    if not pkgs:
        print("ERROR: no candidate-python-packages.json in %s" % man, file=sys.stderr)
        return 1

    def ver(key):
        return pkgs[key]["version"] if key in pkgs else None

    body, prov = [], {}
    git_count = pin_count = 0

    for key in sorted(pkgs):
        entry = pkgs[key]
        name, version = entry["name"], entry["version"]
        du = direct.get(key)
        is_git = bool(du and du.get("vcs"))

        record = {
            "name": name,
            "version": version,
            "installed_version_provenance": "measured_from_candidate_image",
            "measured_at": "2026-09-03",
            "in_requirements_body": key not in EXCLUDE,
        }
        if key in EXCLUDE:
            record["dedicated_layer"] = (
                "build_tools" if key in BUILD_TOOLS else
                "torch_tier" if key in TORCH_STACK else
                "smplx_no_deps" if key in NO_DEPS_PKGS else "dlib"
            )
        if key in POD_MEASURED:
            record["also_measured_on_pod_2026_09_02"] = True
        if key in REPORTED_BY_SOURCE:
            record["version_provenance_note"] = (
                "reported_by_source in SOAP requirements.txt; the pod's "
                "installed build was never measured"
            )
        if is_git:
            record.update({
                "source": "git",
                "url": du.get("url"),
                "vcs": du.get("vcs"),
                "commit_id": du.get("commit_id"),
                "requested_revision": du.get("requested_revision"),
                "installed_commit_provenance": "measured_from_candidate_image",
            })
            sel = GIT_SHA_SELECTION.get(key)
            if sel:
                record["sha_selection_provenance"] = sel[0]
                record["sha_selection_reason"] = sel[1]
        else:
            record["source"] = "pypi"

        if key in NO_DEPS_PKGS:
            record["install_mode"] = "--no-deps"
            record["install_mode_reason"] = SMPLX_REASON
        if key in DEDICATED:
            record["isolation_reason"] = DLIB_REASON

        prov[key] = record

        if key in EXCLUDE:
            continue
        if is_git and du.get("commit_id"):
            # PEP 610 stores the bare repository URL in `url` and the scheme
            # separately in vcs_info.vcs. A pip-installable requirement needs
            # them recombined as `<vcs>+<url>@<commit>`; emitting the bare url
            # would make pip treat it as an archive download.
            body.append("%s @ %s" % (name, pip_vcs_url(du)))
            git_count += 1
        else:
            body.append("%s==%s" % (name, version))
        pin_count += 1

    # ---- requirements-dd-lock.txt -----------------------------------------
    header = [
        "# " + "=" * 74,
        "# DD SOAP - CANONICAL FINAL LOCK  (layer 4 of the lock set)",
        "#",
        "# Generated from the candidate image built by workflow run %s."
        % metrics.get("GITHUB_RUN_ID", "unknown"),
        "# Every version here is measured_from_candidate_image (2026-09-03).",
        "#",
        "# These are NOT the 2026-09-02 RunPod versions. The pod's Tier-2",
        "# versions were never recorded and are unrecoverable. This lock",
        "# establishes a new canonical deterministic environment going",
        "# forward; it does not assert equality with the pod environment.",
        "#",
        "# THIS FILE IS NOT THE WHOLE LOCK. See lockset.json for the ordered",
        "# layers and requirements-dd-lock.provenance.json for per-package",
        "# provenance. Distributions absent here are installed by a dedicated",
        "# layer and are still exactly locked:",
        "#   pip/setuptools/wheel/ninja  layer 1  build tools",
        "#   torch/torchvision/torchaudio layer 2  cu121 index",
        "#   dlib                        layer 3  isolated build",
        "#   smplx                       layer 5  --no-deps",
        "#",
        "# SOAP source revision: %s" % (soap_sha or "unknown"),
        "# " + "=" * 74,
        "",
    ]
    lock_path = os.path.join(out, "requirements-dd-lock.txt")
    with open(lock_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(header + sorted(body)) + "\n")

    # ---- lockset.json — ordered, machine-verifiable ------------------------
    smplx_du = direct.get("smplx") or {}
    layers = [
        {
            "step": 1,
            "layer": "build_tools",
            "method": "pip install --upgrade pip==<v>; pip install setuptools==<v> wheel==<v> ninja==<v>",
            "note": (
                "The pod upgraded pip only; setuptools stayed at the "
                "ensurepip-bundled 59.6.0. Pinned explicitly AND asserted so a "
                "change to Ubuntu's bundled wheel fails the build loudly."
            ),
            "packages": {k: ver(k) for k in BUILD_TOOLS if ver(k)},
        },
        {
            "step": 2,
            "layer": "torch_tier",
            "method": "pip install -r requirements-dd-torch.txt",
            "index": "https://download.pytorch.org/whl/cu121",
            "note": (
                "Separate invocation: --no-build-isolation builds import torch "
                "at build time and pip guarantees no ordering within one pass."
            ),
            "packages": {k: ver(k) for k in TORCH_STACK if ver(k)},
        },
        {
            "step": 3,
            "layer": "dlib",
            "method": "pip install --no-build-isolation dlib==<v>",
            "note": DLIB_REASON,
            "packages": {k: ver(k) for k in DEDICATED if ver(k)},
        },
        {
            "step": 4,
            "layer": "main_lock",
            "method": "pip install --no-build-isolation -r requirements-dd-lock.txt",
            "note": "4 git packages with exact SHAs plus every remaining PyPI distribution.",
            "package_count": pin_count,
            "requirements_file": "requirements-dd-lock.txt",
        },
        {
            "step": 5,
            "layer": "smplx_no_deps",
            "method": "pip install --no-build-isolation --no-deps 'smplx @ %s'"
                      % (pip_vcs_url(smplx_du) if smplx_du else "?"),
            "pip_requirement": pip_vcs_url(smplx_du) if smplx_du else None,
            "install_mode": "--no-deps",
            "note": SMPLX_REASON,
            "dependency_closure_supplied_by": {
                "torch": "layer 2", "numpy": "layer 4", "kiui": "layer 4",
                "chumpy": "layer 4 (git SHA)", "nvdiffrast": "layer 4 (git SHA)",
                "matplotlib": "layer 4", "tqdm": "layer 4", "rich": "layer 4",
            },
            "packages": {k: ver(k) for k in NO_DEPS_PKGS if ver(k)},
        },
    ]
    covered = set()
    for lay in layers:
        covered |= set(lay.get("packages", {}))
    covered |= {k for k in pkgs if k not in EXCLUDE}   # layer 4 body

    lockset = {
        "schema": "dd-soap-lockset/1",
        "generated_from": {
            "workflow_run_id": metrics.get("GITHUB_RUN_ID"),
            "github_sha": metrics.get("GITHUB_SHA"),
            "candidate_image_id": metrics.get("CANDIDATE_IMAGE_ID"),
            "candidate_image_size": metrics.get("CANDIDATE_IMAGE_SIZE"),
            "candidate_build_elapsed_ms": metrics.get("CANDIDATE_BUILD_ELAPSED_MS"),
        },
        "frozen_runtime": {
            "soap_sha": soap_sha,
            # `docker run` on this base emits the NVIDIA container banner on
            # stdout ahead of the command output, so pick the version line out
            # rather than storing the whole blob.
            "python": next(
                (ln.strip() for ln in
                 read(os.path.join(man, "candidate-python-version.txt")).splitlines()
                 if ln.strip().startswith("Python ")),
                "unavailable",
            ),
            "cuda_arch_list": metrics.get("INPUT_TORCH_CUDA_ARCH_LIST"),
            "force_cuda": "1",
        },
        "install_order": layers,
        "git_packages": {
            k: {
                "url": (direct.get(k) or {}).get("url"),
                "commit_id": (direct.get(k) or {}).get("commit_id"),
                "requested_revision": (direct.get(k) or {}).get("requested_revision"),
                "version": ver(k),
                "installed_commit_provenance": "measured_from_candidate_image",
                "sha_selection_provenance": GIT_SHA_SELECTION[k][0],
            }
            for k in GIT_SHA_SELECTION if k in pkgs
        },
        "coverage": {
            "distributions_in_image": len(pkgs),
            "covered": len(covered & set(pkgs)),
            "uncovered": sorted(set(pkgs) - covered),
        },
    }
    lockset_path = os.path.join(out, "lockset.json")
    with open(lockset_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(lockset, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # ---- provenance --------------------------------------------------------
    prov_doc = {
        "schema": "dd-soap-lock-provenance/1",
        "generated_from": lockset["generated_from"],
        "provenance_rule": (
            "measured_from_candidate_image (2026-09-03) is never relabelled as "
            "measured_from_pod_2026_09_02. Distinct measurements of distinct "
            "environments. The four historically_derived git SHA selections "
            "are never promoted to measured."
        ),
        "counts": {
            "final_lock_pin_count": pin_count,
            "final_git_sha_count": git_count,
            "distributions_in_image": len(pkgs),
            "excluded_from_body": len([k for k in pkgs if k in EXCLUDE]),
        },
        "packages": prov,
    }
    prov_path = os.path.join(out, "requirements-dd-lock.provenance.json")
    with open(prov_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(prov_doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # ---- Tier-2 recovery report -------------------------------------------
    lines = ["TIER2_PREVIOUS_UNKNOWN = 29", ""]
    rec = notinst = 0
    for name in sorted(k for k in tier2.get("packages", {}) if not k.startswith("__")):
        e = tier2["packages"][name]
        cls = e["classification"]
        if cls == "MEASURED_FROM_CANDIDATE_IMAGE":
            rec += 1
        elif cls == "NOT_INSTALLED":
            notinst += 1
        lines.append("%-22s %-18s %s" % (name, e["installed_version"] or "-", cls))
    lines += [
        "",
        "TIER2_RECOVERED     = %d" % rec,
        "TIER2_NOT_INSTALLED = %d" % notinst,
        "TIER2_STILL_UNKNOWN = %d" % (29 - rec - notinst),
        "",
        "PROVENANCE = measured_from_candidate_image (2026-09-03).",
        "These are NOT the 2026-09-02 pod versions, which were never recorded.",
    ]
    rep_path = os.path.join(out, "tier2-recovery-report.txt")
    with open(rep_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print("FINAL_LOCK_PIN_COUNT             = %d" % pin_count)
    print("FINAL_GIT_SHA_COUNT              = %d" % git_count)
    print("FINAL_ENV_DISTRIBUTION_COUNT     = %d" % len(pkgs))
    print("FINAL_LOCK_COVERED_DISTRIBUTIONS = %d" % lockset["coverage"]["covered"])
    print("FINAL_LOCK_UNCOVERED             = %d %s"
          % (len(lockset["coverage"]["uncovered"]), lockset["coverage"]["uncovered"] or ""))
    print("TIER2_RECOVERED                  = %d" % rec)
    print("TIER2_NOT_INSTALLED              = %d" % notinst)
    print("TIER2_STILL_UNKNOWN              = %d" % (29 - rec - notinst))
    for p in (lock_path, lockset_path, prov_path, rep_path):
        print("wrote %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
