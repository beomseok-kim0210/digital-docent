#!/usr/bin/env python3
"""
DD SOAP — fold the CI run's KEY=VALUE evidence files into one JSON metrics
document. Runs on the GitHub runner, not inside the image.

    python3 collect_metrics.py <manifest_dir> [key=value ...]

Reads every `KEY=VALUE` line from the text evidence files the workflow wrote
(runner metrics, disk cleanup accounting, build timing) and emits
candidate-build-metrics.json. Extra key=value pairs may be appended on the
command line. Missing files are skipped, never invented.
"""
import json
import os
import re
import sys

SOURCES = (
    "runner-metrics.txt",
    "disk-cleanup.txt",
    "build-timing.txt",
)

KV = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


def main() -> int:
    outdir = sys.argv[1] if len(sys.argv) > 1 else "manifest"
    os.makedirs(outdir, exist_ok=True)

    metrics = {}
    seen_files = []
    for fname in SOURCES:
        path = os.path.join(outdir, fname)
        if not os.path.exists(path):
            continue
        seen_files.append(fname)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = KV.match(line.strip())
                if m:
                    metrics[m.group(1)] = m.group(2)

    for extra in sys.argv[2:]:
        if "=" in extra:
            k, v = extra.split("=", 1)
            metrics[k] = v

    metrics["_sources"] = seen_files
    path = os.path.join(outdir, "candidate-build-metrics.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, sort_keys=True)

    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
