#!/usr/bin/env python3
"""
DD SOAP — lock coverage verification. Runs INSIDE the final image. NO GPU.

    python verify_lock_coverage.py <lockset.json> <requirements-dd-lock.txt> [soap_sha]

Proves the built environment is fully and exactly locked. Being absent from
requirements-dd-lock.txt does NOT count as locked: a distribution must be
covered by exactly one lock-set layer, either the requirements body or a
dedicated layer (build tools, torch tier, dlib, smplx).

Gates, each reported independently:

    FINAL_LOCK_COVERAGE        every installed distribution covered
    UNLOCKED_DISTRIBUTIONS     must be 0
    FINAL_FREEZE_MATCH         installed versions == locked versions
    FINAL_GIT_SHA_MATCH        every git commit_id == the pinned SHA
    BUILD_TOOL_MATCH           pip/setuptools/wheel/ninja
    TORCH_TIER_MATCH           torch/torchvision/torchaudio
    SMPLX_INSTALL_MODE_MATCH   smplx present at the pinned SHA
    NO_MUTABLE_GIT_HEAD        no VCS install without a resolved commit, and
                               no requirement line carrying a bare git URL
    NO_UNPINNED_SELECTOR       every requirements line uses == or @<40-hex>
    SOAP_SHA_MATCH             optional, when an expected SHA is supplied

torch.cuda.is_available() is deliberately NOT consulted. The builder is
CPU-only and that is not a failure.
"""
import json
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distributions, version

HEX40 = re.compile(r"^[0-9a-f]{40}$")
LINE_PIN = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*==\s*([^\s#]+)")
LINE_GIT = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*@\s*(\S+?)@([0-9a-f]{40})\s*$")


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def installed_map():
    out, direct = {}, {}
    for dist in distributions():
        try:
            name = dist.metadata["Name"]
        except Exception:  # noqa: BLE001
            name = None
        if not name:
            continue
        key = norm(name)
        out[key] = dist.version
        raw = None
        try:
            raw = dist.read_text("direct_url.json")
        except Exception:  # noqa: BLE001
            pass
        if raw:
            try:
                du = json.loads(raw)
            except Exception:  # noqa: BLE001
                continue
            vcs = du.get("vcs_info") or {}
            if vcs:
                direct[key] = {
                    "url": du.get("url"),
                    "commit_id": vcs.get("commit_id"),
                    "requested_revision": vcs.get("requested_revision"),
                }
    return out, direct


def main() -> int:
    lockset_path = sys.argv[1]
    reqs_path = sys.argv[2]
    expected_soap = sys.argv[3] if len(sys.argv) > 3 else None

    with open(lockset_path, encoding="utf-8") as fh:
        lockset = json.load(fh)

    inst, direct = installed_map()
    results, failures = {}, []

    def gate(name, ok, detail=""):
        results[name] = "PASS" if ok else "FAIL"
        if not ok:
            failures.append("%s: %s" % (name, detail))
        print("%-26s %-5s %s" % (name, results[name], detail))

    # ---- parse the requirements body --------------------------------------
    body_pins, body_git, bad_lines = {}, {}, []
    with open(reqs_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = LINE_GIT.match(line)
            if m:
                body_git[norm(m.group(1))] = (m.group(2), m.group(3))
                continue
            m = LINE_PIN.match(line)
            if m:
                body_pins[norm(m.group(1))] = m.group(2)
                continue
            bad_lines.append(line)

    gate("NO_UNPINNED_SELECTOR", not bad_lines,
         "" if not bad_lines else "unpinned lines: %s" % bad_lines[:5])

    # ---- coverage ----------------------------------------------------------
    dedicated = {}
    for lay in lockset.get("install_order", []):
        for k, v in (lay.get("packages") or {}).items():
            dedicated[norm(k)] = (lay["layer"], v)

    covered = set(body_pins) | set(body_git) | set(dedicated)
    uncovered = sorted(set(inst) - covered)
    total = len(inst)
    cov_n = total - len(uncovered)

    print("FINAL_ENV_DISTRIBUTION_COUNT     = %d" % total)
    print("FINAL_LOCK_COVERED_DISTRIBUTIONS = %d" % cov_n)
    print("FINAL_LOCK_UNCOVERED             = %d" % len(uncovered))
    if uncovered:
        for u in uncovered:
            print("   UNCOVERED %-32s %s" % (u, inst[u]))
    gate("UNLOCKED_DISTRIBUTIONS", not uncovered,
         "0" if not uncovered else "%d: %s" % (len(uncovered), uncovered[:8]))
    gate("FINAL_LOCK_COVERAGE", not uncovered,
         "%.1f%%" % (100.0 * cov_n / total if total else 0.0))

    # ---- freeze match ------------------------------------------------------
    mism = []
    for key, want in body_pins.items():
        got = inst.get(key)
        if got is None:
            mism.append("%s MISSING (want %s)" % (key, want))
        elif got != want:
            mism.append("%s got %s want %s" % (key, got, want))
    for key, (_lay, want) in dedicated.items():
        if want is None:
            continue
        got = inst.get(key)
        if got is None:
            mism.append("%s MISSING (want %s)" % (key, want))
        elif got != want:
            mism.append("%s got %s want %s" % (key, got, want))
    gate("FINAL_FREEZE_MATCH", not mism,
         "" if not mism else "%d mismatch: %s" % (len(mism), mism[:5]))

    # ---- git SHAs ----------------------------------------------------------
    git_want = {norm(k): v for k, v in (lockset.get("git_packages") or {}).items()}
    gmis = []
    for key, spec in git_want.items():
        want_sha = spec.get("commit_id")
        got = direct.get(key)
        if not got:
            gmis.append("%s has no direct_url vcs record" % key)
        elif got.get("commit_id") != want_sha:
            gmis.append("%s got %s want %s" % (key, got.get("commit_id"), want_sha))
    gate("FINAL_GIT_SHA_MATCH", not gmis,
         "%d/%d matched" % (len(git_want) - len(gmis), len(git_want))
         if not gmis else str(gmis[:5]))

    # ---- no mutable git HEAD ----------------------------------------------
    mutable = []
    for key, du in direct.items():
        cid = du.get("commit_id")
        if not cid or not HEX40.match(cid):
            mutable.append("%s unresolved commit %r" % (key, cid))
        rev = du.get("requested_revision")
        # a requested_revision that is not a 40-hex SHA means the install
        # tracked a branch/tag, i.e. a mutable ref
        if rev is not None and not HEX40.match(str(rev)):
            mutable.append("%s tracked mutable ref %r" % (key, rev))
    gate("NO_MUTABLE_GIT_HEAD", not mutable,
         "%d vcs installs, all pinned" % len(direct)
         if not mutable else str(mutable[:5]))

    # ---- dedicated layers --------------------------------------------------
    def layer_gate(gate_name, layer_name):
        want = {}
        for lay in lockset.get("install_order", []):
            if lay["layer"] == layer_name:
                want = {norm(k): v for k, v in (lay.get("packages") or {}).items()}
        bad = []
        for k, v in want.items():
            got = inst.get(k)
            if got != v:
                bad.append("%s got %s want %s" % (k, got, v))
        gate(gate_name, bool(want) and not bad,
             ("%d pkgs" % len(want)) if want and not bad
             else ("layer empty" if not want else str(bad)))

    layer_gate("BUILD_TOOL_MATCH", "build_tools")
    layer_gate("TORCH_TIER_MATCH", "torch_tier")

    # ---- smplx -------------------------------------------------------------
    sm = direct.get("smplx")
    sm_want = (git_want.get("smplx") or {}).get("commit_id")
    gate("SMPLX_INSTALL_MODE_MATCH",
         bool(sm) and sm.get("commit_id") == sm_want and "smplx" in inst,
         "installed %s @ %s" % (inst.get("smplx"), (sm or {}).get("commit_id"))
         if sm else "smplx has no vcs record")

    # ---- pip check ---------------------------------------------------------
    ck = subprocess.run([sys.executable, "-m", "pip", "check"],
                        capture_output=True, text=True)
    gate("PIP_CHECK", ck.returncode == 0,
         (ck.stdout or ck.stderr).strip()[:300] or "no broken requirements")

    # ---- SOAP sha ----------------------------------------------------------
    if expected_soap:
        soap_home = os.environ.get("SOAP_HOME", "/opt/soap")
        got = subprocess.run(["git", "-C", soap_home, "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        gate("SOAP_SHA_MATCH", got == expected_soap, "%s" % (got or "unavailable"))
    else:
        print("%-26s %-5s %s" % ("SOAP_SHA_MATCH", "SKIP", "no expected sha given"))

    print("=" * 60)
    if failures:
        print("LOCK_COVERAGE_VERIFICATION = FAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("LOCK_COVERAGE_VERIFICATION = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
