# LAM-A2E L0 — dependency and model lock

2026-09-04. Research artifact. Nothing here is installed into, or imported by,
the Digital Docent runtime.

`LAM_L0_DEPENDENCY_LOCK = PASS`

---

## 1. Frozen revisions

All three verified against the public APIs, unauthenticated, no token.

| what | id | evidence |
|------|----|----------|
| code | `aigc3d/LAM_Audio2Expression` @ `02a703c3ea7d8e360eb43098eca85ee98a083529` | committed 2025-10-24T05:53:58Z, Apache-2.0, **is** the current `main` head |
| model | `3DAIGC/LAM_audio2exp` @ `0fe5f4dbb283ec7d9c01688681e6e4b6ac314858` | gated false, private false, apache-2.0 |
| encoder | `facebook/wav2vec2-base-960h` @ `22aad52d435eb6dbaf354bdad9b0da84ce7d6156` | gated false, apache-2.0, **is** the current `main` head; repo unchanged since 2022-11-14 |

---

## 2. Minimum raw-inference path

`MINIMUM_INFERENCE_CLOSURE_KNOWN = PASS`

Entrypoint: **`inference_streaming_audio.py`**. It is the shorter of the two —
`librosa.load` → 1-second chunks → `infer_streaming_audio` → `np.concatenate` →
`export_blendshape_animation`. `inference.py` reaches the same model but routes
through `engines/launch.py`, which pulls `torch.distributed` even for one
process.

Closure computed by AST walk, not by reading: **24 Python files**, 12 external
top-level modules.

| module | classification | evidence |
|--------|---------------|----------|
| `torch` | CORE_INFERENCE | 31 import sites, direct + lazy |
| `numpy` | CORE_INFERENCE | 9 sites, direct |
| `transformers` | MODEL_LOADING | 6 sites; `Wav2Vec2Model`, `Wav2Vec2Config`, `WavLMModel` |
| `torchaudio` | CORE_INFERENCE | `models/network.py:8`, direct |
| `librosa` | AUDIO_IO | `engines/infer.py:21`, `inference_streaming_audio.py`; load, resample, `feature.rms` |
| `scipy` | CORE_INFERENCE | `models/utils.py:6` savgol_filter, `:685` ndimage.label |
| `regex` | CORE_INFERENCE | `utils/config.py:25`, direct — the config parser |
| `addict` | CORE_INFERENCE | `utils/config.py:18` |
| `yapf` | CORE_INFERENCE | `utils/config.py:19` — pretty-prints the dumped config |
| `termcolor` | CORE_INFERENCE | `utils/logger.py:9` |
| `tqdm` | CORE_INFERENCE | `inference_streaming_audio.py:27` |
| `mmcv` | **DEAD_FOR_INFERENCE** | `utils/config.py:545`, lazy, inside the `else` of `if self.filename.endswith(".py")`. Both entrypoints use `.py` configs. Verified: the config parses with mmcv absent. |

Reached only from `app_lam_audio2exp.py`, therefore never core:

| module | classification |
|--------|---------------|
| `gradio` | OPTIONAL_DEMO |
| `gradio_gaussian_render` | OPTIONAL_RENDER — the bundled `wheels/*.whl`, `Requires-Dist: gradio<6.0,>=4.0` |
| `spaces` | OPTIONAL_DEMO |
| `omegaconf` | OPTIONAL_DEMO |
| `patoolib` (`patool`) | OPTIONAL_DEMO |

Two upstream entries are dead everywhere:

- **`opencv_python_headless==4.11.0.86`** is pinned in `requirements.txt`, and
  `cv2` is imported by **no file in the repository**. DEAD_FOR_INFERENCE.
- **`torchvision==0.16.2`** is installed by `scripts/install/install_cu121.sh`
  and imported by no file either. Kept in FULL_UPSTREAM_DELTA, excluded from
  CORE.

---

## 3. Python

`PYTHON_PIN = 3.10` · `PROVENANCE = official`

This **corrects the earlier audit**, which reported that no Python version was
pinned anywhere in the repository. It is pinned, in the README:

```
# Create conda environment (currently only supports Python 3.10)
conda create -n lam_a2e python=3.10
```

Corroborating: the bundled `gradio_gaussian_render` wheel declares
`Requires-Python: >=3.10`, and torch 2.1.2 publishes no cp312 wheels, so 3.10
sits inside the only workable band. The repository has no `setup.py`,
`pyproject.toml`, `setup.cfg`, `Dockerfile`, `environment.yml` or CI workflow —
the README is the only statement, and no patch version is given.

**No CPython 3.10 interpreter was executed.** Only 3.11 is installed on this
machine and installing another is a Human decision. The resolution below was
produced with `pip --python-version 3.10 --platform linux_x86_64 --platform
manylinux*`, so it is *resolver-derived for* 3.10, not *measured on* it.

---

## 4. Torch tier

`TORCH_TIER_FROZEN = PASS`

```
torch       == 2.1.2
torchvision == 0.16.2   (upstream installs it; CORE does not)
torchaudio  == 2.1.2
```

`CUDA_INSTALL_SEMANTICS`: `+cu121` is a real local version identifier carried by
the wheel, not something pip synthesises. Measured from the index:

```
download.pytorch.org/whl/cu121  torch-2.1.2+cu121-cp310-cp310-linux_x86_64.whl
pypi.org                        torch-2.1.2-cp310-cp310-manylinux1_x86_64.whl
```

So the installed distribution version is `2.1.2+cu121` only when the PyTorch
index is selected. (Locally, PyPI's Windows wheel installs as `2.1.2+cpu` — the
suffix is index- and platform-dependent, never absent by default.)

Exact commands, matching `scripts/install/install_cu121.sh`:

```bash
pip install torch==2.1.2 torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu121 \
    -c constraints-lam-torch.txt
pip install -r requirements-lam-core.lock
```

The `-c` is not decoration. `pip install torch==2.1.2 torchaudio==2.1.2` pins
two distributions and lets the other eight in that tier float, so step 1 on its
own is not reproducible. `constraints-lam-torch.txt` pins the rest.

`--index-url` (not `--extra-index-url`) matters. The PyTorch index **mirrors**
unrelated PyPI packages: resolving both tiers together pulled `colorama`,
`Jinja2` and `MarkupSafe` from `download.pytorch.org` instead of PyPI. Two
separate invocations keep each tier's provenance unambiguous.

No `nvidia-*` packages appear in the torch tier — the CUDA runtime is inside the
wheel. Only a host driver is required.

---

## 5. The four previously unresolved items

| item | core? | parent | upstream range | resolved | provenance |
|------|-------|--------|----------------|----------|------------|
| `regex` | **yes** | direct (`utils/config.py:25`) + `transformers` | `!=2019.12.17` | `2026.9.3` | resolver-derived |
| `scipy` | **yes** | direct (`models/utils.py:6,685`) + `librosa>=1.6.0` | `>=1.6.0` | `1.15.3` | resolver-derived |
| `tqdm` | **yes** | direct (`inference_streaming_audio.py:27`) + `transformers>=4.27` | `>=4.27` | `4.70.0` | resolver-derived |
| `patool` | **no** | `app_lam_audio2exp.py` only | unpinned upstream | excluded | measured |

Resolver-derived means: the version pip selects when the whole frozen set is
solved together for cp310/linux with `--only-binary=:all:`, recorded and pinned
from then on. It is not "latest" in any free sense — `numpy==1.26.3` and
`transformers==4.36.2` do real work constraining it.

---

## 6. Closure

```
TOP_LEVEL_PINS                  11
TRANSITIVE_PINS                 38
TOTAL_DISTINCT                  49
TORCH_INDEX_PACKAGES            10
PYPI_PACKAGES                   42
UNPINNED_PYTHON_DISTRIBUTIONS    0
```

Every distribution resolves to a **prebuilt wheel**; there is not one sdist in
either pass, so no compiler is needed to build the environment.

One package resolves differently in the two passes:

| package | torch index | PyPI | effective |
|---------|------------|------|-----------|
| `filelock` | 3.32.3 | 3.32.5 | **3.32.5** — step 2 runs second and wins |

`fsspec` and `typing_extensions` are identical in both. Full table with a
`why_present` path for every entry: `lam-core-lock.json`.

The two pin files together cover all 49 distributions:
`constraints-lam-torch.txt` (10, step 1) and `requirements-lam-core.lock`
(42, step 2), overlapping on `fsspec` and `typing_extensions`.

---

## 7. System packages

`PYTHON_REPRODUCIBILITY` and `OS_PACKAGE_REPRODUCIBILITY` are separate claims.
Only the first is established here.

| package | status | why |
|---------|--------|-----|
| `libsndfile1` | **not required** | measured: `soundfile-0.14.0-...manylinux_2_28_x86_64.whl` bundles `_soundfile_data/libsndfile_x86_64.so` |
| `ffmpeg` | conditional | `audioread` is pure Python with `ffdec`/`gstdec`/`maddec`/`macca`/`rawread` backends. A 16 kHz WAV goes through soundfile and never reaches it. Only compressed input (mp3/m4a) needs it. |
| NVIDIA driver | required at runtime | host-level, not an apt package. CUDA runtime ships inside the torch wheel. |
| `libgomp1` | **UNVERIFIED** | torch's linux wheels normally vendor `libgomp` under `torch.libs`; not confirmed, and confirming it means downloading a 2 GB wheel. Verify with `ldd` at L1. |

glibc floor: the soundfile wheel is `manylinux_2_28`, so glibc ≥ 2.28. Ubuntu
22.04 (glibc 2.35) satisfies it.

**No OS package versions are pinned, so no bit-for-bit OS reproducibility is
claimed.**

---

## 8. Model artifacts

`MODEL_FILES_FROZEN = PASS`. Sizes and LFS SHA-256 read from the HF blobs API at
the pinned revisions; neither tar was downloaded. `reported_by_source`, not
locally hashed.

```
LAM_audio2exp_assets.tar      32,798,496 B  f5759f080ec1352d454d88d5a32f09c0…
LAM_audio2exp_streaming.tar  373,377,643 B  0877f419b1b7b6856479b743b71625ad…
MODEL_FILE_COUNT   2
MODEL_TOTAL_BYTES  406,176,139
```

### The encoder is not downloaded

`models/network.py:40`:

```python
if os.path.exists(pretrained_encoder_path):          # 'facebook/wav2vec2-base-960h'
    self.audio_encoder = Wav2Vec2Model.from_pretrained(pretrained_encoder_path)
else:
    config = Wav2Vec2Config.from_pretrained(wav2vec2_config_path)
    self.audio_encoder = Wav2Vec2Model(config)
```

The configured value is a **HuggingFace repo id, not a filesystem path**, so
`os.path.exists` is false and the `else` branch runs: the encoder is built from
the in-repo `configs/wav2vec2_config.json` with random weights. Measured in the
validation environment — `encoder_path_exists_on_disk: false`.

```
ENCODER_FILE_COUNT   0
ENCODER_TOTAL_BYTES  0
```

**Derived, not measured:** the fine-tuned encoder weights must therefore be
inside `LAM_audio2exp_streaming.tar`. Confirming that means opening a 373 MB
archive, which L0 did not do. It is the first thing L1 should check.

The revision is still frozen, because the guard is path-dependent: if a
directory named `facebook/wav2vec2-base-960h` ever exists in the working
directory, the branch flips and 2 files (`config.json` + `model.safetensors`,
377,609,497 B) are loaded. `pytorch_model.bin` and `tf_model.h5` would remain
unnecessary — `safetensors` 0.8.0 is installed and transformers 4.36.2 prefers
it. No tokenizer, processor or feature extractor is ever constructed, so
`vocab.json`, `tokenizer_config.json`, `special_tokens_map.json`,
`preprocessor_config.json` and `feature_extractor_config.json` are all unused.

---

## 9. Output contract

Measured by importing the frozen source in the validation environment.

```
OUTPUT_CHANNEL_COUNT     52
OUTPUT_FPS               30.0
INPUT_SR                 16000
output shape             (num_frames, 52)
JAWOPEN_CHANNEL_INDEX    24
JAWOPEN_CHANNEL_NAME     jawOpen
```

`export_blendshape_animation` raises unless `shape[1] == 52`.

The MVP mapping stays exactly one edge:

```
LAM ARKit channel 24  jawOpen   ->   DD morph target  jawOpen
```

The other 51 are not mapped, and six visemes are not being reconstructed from
them. Full ordered list in `lam-inference-config.json`.

---

## 10. Inference config lock

`INFERENCE_CONFIG_FROZEN = PASS`, with one honest exception.

```
audio_sr 16000 · fps 30.0 · id_idx 0 · num_identity_classes 12
expression_dim 52 · identity_feat_dim 64 · hidden_dim 512 · norm_type ln
use_transformer false · movement_smooth false · brow_movement false
max_frame_length 64 (hard-coded, engines/infer.py:166)
```

**`DETERMINISTIC = false`.** The config sets `seed = None`, and
`engines/defaults.py:115` replaces that with
`os.getpid() + wall-clock microseconds + os.urandom(2)`. The forward pass is
deterministic under `torch.no_grad()`, but post-processing draws from numpy's
global RNG, so two runs over the same audio produce different eye-blink timing.
Affected channels are 8 and 9. **`jawOpen` (24) is untouched by any random
path**, so the DD MVP signal is reproducible even though the artifact as a whole
is not. Fix at L1 by passing `--options seed=<int>`; not changed here.

Post-processing order (load-bearing, per its own comment):
`smooth_mouth_movements` → `apply_frame_blending` →
`apply_savitzky_golay_smoothing(window_length=5)` → `symmetrize_blendshapes` →
`apply_random_eye_blinks_context`.

Range: clipped to `[0, 1]` at step 3 of 5. Two steps run after the clip; neither
can exceed the range, but there is no final clamp.

Silence: `librosa.feature.rms`, threshold 0.001, ≥7 consecutive frames, the 29
`MOUTH_BLENDSHAPES` channels scaled by 0.1 with a 3-frame boundary blend.

Two defects recorded, not fixed: the bare `except:` at `engines/infer.py:206`
returns `None` where the caller unpacks a tuple, and `.cuda(non_blocking=True)`
at `:200-203` is unconditional, so this path cannot run on CPU without a source
change.

---

## 11. Build tools

Pinned separately from application dependencies, and not counted in the closure.

```
pip        26.2.1     (the resolver and installer actually used)
setuptools 65.5.0     (venv default; nothing built from source needs it)
wheel      absent     (not required — no sdists)
```

`gradio_gaussian_render-0.0.3-py3-none-any.whl`: **NOT REQUIRED**. One import
site, `app_lam_audio2exp.py:22`, and it declares `gradio<6.0,>=4.0`.

---

## 12. Validation

Free, local, no GPU, no weights downloaded.

```
PIP_CHECK            PASS   "No broken requirements found."
DISTRIBUTION_COUNT   51     (49 locked + pip + setuptools)
CORE_IMPORT_COUNT    41
CORE_IMPORT_PASS     41
UNPINNED_COUNT        0
```

41 = 11 distributions + 13 exact symbols the source reaches for + 17 LAM modules
in the closure.

The main risk going in was `transformers==4.36.2` (December 2023) against
`huggingface_hub==0.36.2` (2026) — transformers' own bound is only `<1.0`, which
is loose enough to be meaningless. It imports and resolves cleanly. Measured,
not assumed.

The config parses through the project's own parser with **mmcv absent**, which
is the direct evidence for classifying mmcv DEAD_FOR_INFERENCE.

### What this validation is not

The environment is **CPython 3.11 on Windows with `torch==2.1.2+cpu`**, because
3.10 is not installed here and cu121 wheels are Linux-only. It validates the
pure-Python compatibility surface — which is where the risk was — and not the
target platform. One package drifted: `networkx` 3.4.2 in the cp310 lock versus
3.6.1 installed, since 3.4.2 is the last release supporting 3.10. That drift is
itself evidence the lock is genuinely cp310-specific.

A cp310/linux/cu121 install is L1's job.

---

## 13. Isolation and spend

```
SOAP_FILES_CHANGED      0
SOAP_DOCKER_CHANGED     0     docker/ clean, files still dated 2026-09-03
LAM_A2E_INSTALLED       false (no LAM package installed; only its deps, in a scratch venv)
PAID_ACTIONS_EXECUTED   0
NEW_GPU_SPEND           $0
PRODUCTION_ASSET        public/models/docent-qka2.glb untouched
```

SOAP runs `torch 2.3.1+cu121`; LAM needs `torch 2.1.2+cu121`. They stay in
separate images. Nothing here brings them together.

---

## 14. L0 gate

| criterion | result |
|-----------|--------|
| `CODE_SHA_FROZEN` | PASS |
| `MODEL_REVISION_FROZEN` | PASS |
| `WAV2VEC_REVISION_FROZEN` | PASS |
| `PYTHON_PIN_RESOLVED` | PASS (official, README) |
| `TORCH_TIER_FROZEN` | PASS |
| `CORE_TOP_LEVEL_UNPINNED` | 0 |
| `CORE_TRANSITIVE_UNPINNED` | 0 |
| `MODEL_FILES_FROZEN` | PASS |
| `INFERENCE_CONFIG_FROZEN` | PASS (with `DETERMINISTIC = false` recorded) |
| `MINIMUM_INFERENCE_CLOSURE_KNOWN` | PASS |
| `PIP_CHECK` | PASS |

`NEXT_GATE = LAM_L1_ISOLATED_CLEAN_BUILD`

Carry into L1: verify the encoder weights really are in the streaming tar; pin a
seed; `ldd` the torch wheel for `libgomp`; decide whether `.cuda()` needs a CPU
escape hatch.
