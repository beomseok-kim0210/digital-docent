#!/bin/sh
# =============================================================================
# DD SOAP — derive the Tier 2 install set from SOAP's requirements.txt.
#
# SOAP's requirements.txt is READ ONLY. This script never edits it; it emits a
# filtered copy elsewhere.
#
# Removed: every line Tier 0 / Tier 1 already owns at an exact version or SHA,
# plus every `git+` line (all five git dependencies are pinned in Tier 1) and
# every comment. What remains is the genuinely unpinned residual, installed
# under constraints-dd.txt so it cannot move a locked pin.
#
#   usage: derive_tier2.sh <path/to/requirements.txt> <path/to/tier2.txt>
# =============================================================================
set -eu

SRC="$1"
OUT="$2"

# Two anchored alternatives, deliberately kept separate:
#
#   1. comments and git URLs        — matched on the prefix alone. They must NOT
#      carry the trailing-delimiter requirement: `git+https://...` is followed
#      by `h`, and `#git+...` by `g`, so folding them into the name list below
#      silently fails to filter them.
#
#   2. package names Tier 0/1 owns  — these DO need the trailing delimiter, to
#      stop prefix collisions: torch_sparse / torch_scatter must not swallow
#      torchfile or torchmetrics, and face_alignment must not swallow
#      facenet-pytorch.
OWNED='^[[:space:]]*(#|git\+)|^[[:space:]]*(numpy|torch_sparse|torch_scatter|dlib|kiui|mediapipe|face_alignment|trimesh|tensorboard|kornia|transformers|diffusers|imageio-ffmpeg|huggingface_hub|ninja)([[:space:]]|==|$)'

grep -viE "$OWNED" "$SRC" | grep -v '^[[:space:]]*$' > "$OUT"

echo '--- TIER 2 REMOVED (owned by Tier 0/1, pinned there) ---'
grep -iE "$OWNED" "$SRC" || true
echo '--- TIER 2 RETAINED (unpinned residual, see REPRODUCIBILITY_GAPS G-2) ---'
cat -n "$OUT"
echo "--- TIER 2 COUNT: $(grep -c . "$OUT") ---"
