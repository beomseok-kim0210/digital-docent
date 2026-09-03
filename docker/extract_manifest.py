#!/usr/bin/env python3
"""
DD SOAP — candidate/final image manifest extraction.

Runs INSIDE the built image. Emits the evidence needed to (a) recover the
Tier-2 versions that no local execution log preserved, and (b) prove the built
image matches the lock.

    python extract_manifest.py /out

Writes into <outdir>:
    candidate-pip-freeze.txt        unfiltered `pip freeze --all`
    candidate-pip-check.txt         `pip check` output + exit code
    candidate-direct-urls.json      every *.dist-info/direct_url.json, parsed
    candidate-python-packages.json  every installed distribution
    candidate-soap-sha.txt          SOAP source revision baked into the image
    candidate-buildtools.txt        python / pip / setuptools / wheel / ninja
    candidate-apt-packages.txt      dpkg -l (closes reproducibility gap G-1)
    candidate-tier2-resolution.json the 29 previously-unavailable versions,
                                    classified MEASURED_FROM_CANDIDATE_IMAGE /
                                    NOT_INSTALLED

Nothing here is filtered, summarised or inferred. Values absent from the image
are reported absent, never guessed.
"""
import json
import os
import re
import subprocess
import sys
from importlib.metadata import distributions

LOCK_DIR = os.environ.get("DD_LOCK_DIR", "/opt/dd-lock")
SOAP_HOME = os.environ.get("SOAP_HOME", "/opt/soap")


def norm(name: str) -> str:
    """PEP 503 normalisation: lowercase, runs of -_. collapse to a single -."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "/out"
    os.makedirs(out, exist_ok=True)

    def w(fname, text):
        path = os.path.join(out, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %-38s %8d bytes" % (fname, len(text.encode("utf-8"))))

    # ---- pip freeze --all (UNFILTERED) -------------------------------------
    fr = run([sys.executable, "-m", "pip", "freeze", "--all"])
    w("candidate-pip-freeze.txt", fr.stdout)

    # ---- pip check ---------------------------------------------------------
    ck = run([sys.executable, "-m", "pip", "check"])
    w(
        "candidate-pip-check.txt",
        "exit_code=%d\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
        % (ck.returncode, ck.stdout, ck.stderr),
    )

    # ---- every installed distribution --------------------------------------
    pkgs = {}
    direct = {}
    for dist in distributions():
        try:
            name = dist.metadata["Name"]
        except Exception:  # noqa: BLE001
            name = None
        if not name:
            continue
        key = norm(name)
        entry = {
            "name": name,
            "normalized_name": key,
            "version": dist.version,
            "location": str(getattr(dist, "_path", "")) or None,
        }
        pkgs[key] = entry

        # direct_url.json marks anything pip installed from a URL or VCS.
        raw = None
        try:
            raw = dist.read_text("direct_url.json")
        except Exception:  # noqa: BLE001
            raw = None
        if raw:
            try:
                du = json.loads(raw)
            except Exception as exc:  # noqa: BLE001
                direct[key] = {"name": name, "parse_error": str(exc), "raw": raw}
                continue
            vcs = du.get("vcs_info") or {}
            direct[key] = {
                "package": name,
                "version": dist.version,
                "url": du.get("url"),
                "vcs": vcs.get("vcs"),
                "commit_id": vcs.get("commit_id"),
                "requested_revision": vcs.get("requested_revision"),
                "dir_info": du.get("dir_info"),
                "archive_info": du.get("archive_info"),
            }

    w("candidate-python-packages.json", json.dumps(pkgs, indent=2, sort_keys=True))
    w("candidate-direct-urls.json", json.dumps(direct, indent=2, sort_keys=True))

    # ---- SOAP revision -----------------------------------------------------
    sha = run(["git", "-C", SOAP_HOME, "rev-parse", "HEAD"])
    w("candidate-soap-sha.txt", (sha.stdout or sha.stderr).strip() + "\n")

    # ---- build tooling -----------------------------------------------------
    lines = ["python=%s" % sys.version.replace("\n", " ")]
    for tool in ("pip", "setuptools", "wheel", "ninja"):
        lines.append("%s=%s" % (tool, pkgs.get(tool, {}).get("version", "ABSENT")))
    lines.append("pip_cli=%s" % run([sys.executable, "-m", "pip", "--version"]).stdout.strip())
    w("candidate-buildtools.txt", "\n".join(lines) + "\n")

    # ---- apt inventory (reproducibility gap G-1) ---------------------------
    dp = run(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"])
    w("candidate-apt-packages.txt", dp.stdout or dp.stderr)

    # ---- Tier-2 resolution -------------------------------------------------
    # tier2.txt is the residual of SOAP requirements.txt that the lock could not
    # pin, because no local execution log preserved those versions. This is the
    # step that turns them into measured values.
    tier2_path = os.path.join(LOCK_DIR, "tier2.txt")
    resolution = {}
    if os.path.exists(tier2_path):
        with open(tier2_path, encoding="utf-8") as fh:
            for raw_line in fh:
                req = raw_line.strip()
                if not req or req.startswith("#"):
                    continue
                # tier2 entries are bare names; strip any specifier defensively
                base = re.split(r"[<>=!~\[; ]", req, 1)[0].strip()
                key = norm(base)
                hit = pkgs.get(key)
                resolution[base] = {
                    "requirement_line": req,
                    "normalized_name": key,
                    "installed_version": hit["version"] if hit else None,
                    "classification": (
                        "MEASURED_FROM_CANDIDATE_IMAGE" if hit else "NOT_INSTALLED"
                    ),
                }
    else:
        resolution["__error__"] = {"missing": tier2_path}

    measured = sum(
        1 for v in resolution.values()
        if v.get("classification") == "MEASURED_FROM_CANDIDATE_IMAGE"
    )
    not_installed = sum(
        1 for v in resolution.values() if v.get("classification") == "NOT_INSTALLED"
    )
    payload = {
        "tier2_total": len([k for k in resolution if not k.startswith("__")]),
        "measured_from_candidate_image": measured,
        "not_installed": not_installed,
        "packages": resolution,
    }
    w("candidate-tier2-resolution.json", json.dumps(payload, indent=2, sort_keys=True))

    print("---- SUMMARY ----")
    print("distributions_total          %d" % len(pkgs))
    print("direct_url_entries           %d" % len(direct))
    print("tier2_total                  %d" % payload["tier2_total"])
    print("tier2_measured               %d" % measured)
    print("tier2_not_installed          %d" % not_installed)
    print("pip_check_exit               %d" % ck.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
