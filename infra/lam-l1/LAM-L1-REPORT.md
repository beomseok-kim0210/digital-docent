# LAM-A2E L1 — isolated clean build

2026-09-04. Environment reconstruction gate. No inference was run.

`LAM_L1_ISOLATED_CLEAN_BUILD = PASS` · `ATTEMPT_COUNT = 1`

---

## What was rebuilt from zero

```
L1_ROOT            D:\dd-lam-a2e-v1
VENV_PATH          D:\dd-lam-a2e-v1\venv
PYTHON_EXECUTABLE  D:\dd-lam-a2e-v1\venv\Scripts\python.exe
PYTHON_VERSION     3.10.21
LAM_SOURCE_PATH    D:\dd-lam-a2e-v1\src\LAM_Audio2Expression
```

L0 pinned Python 3.10 (README: "currently only supports Python 3.10") and this
machine had only 3.11. Rather than leave `PYTHON_PIN_MATCH` unmet, a standalone
CPython 3.10.21 was unpacked into the L1 root:

```
astral-sh/python-build-standalone 20260901
cpython-3.10.21+20260901-x86_64-pc-windows-msvc-install_only.tar.gz
sha256 b3edb1dacad300c7117ce4d6df97cd2e411afc0d173db43c224f904deb6253b5
```

No system Python was altered, no installer was run, no admin rights, no login,
no new licence. Everything lives on `D:` — outside every Git-tracked path.

---

## Gates

| gate | result |
|------|--------|
| `LAM_L0_DEPENDENCY_LOCK` | PASS (inherited, artifacts re-hashed before install) |
| `SOURCE_SHA_MATCH` | **PASS** |
| `PYTHON_PIN_MATCH` | **PASS** — 3.10.21 against a 3.10 pin |
| `TORCH_TIER_MATCH` | **PASS** |
| `LOCK_INSTALL` | **PASS** |
| `PIP_CHECK` | **PASS** |
| `UNPINNED_CORE_DISTRIBUTIONS` | **0** |
| `LOCK_VERSION_MISMATCH` | **0** |
| `MISSING_LOCK_DISTRIBUTIONS` | **0** |
| `CORE_IMPORT_GATE` | **PASS** — 41/41 |
| `CONFIG_LOAD_GATE` | **PASS** — 18/18 keys, zero differences |
| `OUTPUT_CHANNEL_COUNT` | **52** |
| `JAWOPEN_CHANNEL_IDENTIFIED` | **PASS** — index 24 |
| `MODEL_STRUCTURE_LOAD` | **PASS** |
| `SOAP_FILES_CHANGED` | 0 |
| `PAID_ACTIONS_EXECUTED` | 0 |

---

## Source

```
LAM_HEAD               02a703c3ea7d8e360eb43098eca85ee98a083529
tree                   a196252329c73289af86f3ac9eb7d2261faeefba
SOURCE_DIR_FILE_COUNT  52
SOURCE_DIR_BYTES       5,161,225
working tree dirty     0 files
```

Cloned and checked out by SHA, not by branch. Upstream source was not modified;
the validation harness (`l1_gate.py`) lives in the DD research directory and
imports upstream read-only.

---

## Build tools

Frozen to the values L0 resolved, and not upgraded afterwards. The standalone
interpreter shipped pip 23.0.1 / setuptools 79.0.1; both were pinned down.

```
PIP_VERSION         26.2.1
SETUPTOOLS_VERSION  65.5.0
WHEEL_VERSION       absent — deliberately
```

`wheel` is absent because L0 measured zero sdists in the closure. Every
distribution installed from a prebuilt wheel, so nothing needed to build.

---

## Torch tier

```
TORCH             2.1.2+cu121
TORCHAUDIO        2.1.2+cu121
TORCHVISION       not installed
TORCH_CUDA_BUILD  12.1
```

Installed with the upstream command, plus the L0 constraints file:

```bash
pip install torch==2.1.2 torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu121 \
    -c constraints-lam-torch.txt
```

The requirement stays `torch==2.1.2`, exactly as `install_cu121.sh` writes it.
The `+cu121` comes from index selection; PEP 440 lets the `==2.1.2` specifier
match the `2.1.2+cu121` the index serves. Nothing was invented.

`torchvision` is absent on purpose. `install_cu121.sh` installs 0.16.2, and L0
traced that no file in the inference closure imports it.

---

## Distributions

```
TOTAL_DISTRIBUTION_COUNT        51
APPLICATION_DISTRIBUTION_COUNT  49
BUILD_TOOL_COUNT                 2   (pip, setuptools)

LOCKED_DISTRIBUTIONS            49
LOCK_VERSION_MISMATCH            0
MISSING_LOCK_DISTRIBUTIONS       0
UNEXPECTED_DISTRIBUTIONS         0
UNPINNED_CORE_DISTRIBUTIONS      0
```

**All 49 match exactly, local version tags included.** No package appeared that
the lock did not name, so nothing had to be explained after the fact.

The lock was resolved for `cp310/manylinux` and installed on `cp310/win_amd64`
with zero drift. That is real evidence the pin set is portable at the version
level — and it is not evidence that the Linux image builds. That is a separate
run.

Contrast with L0's throwaway validation environment, which was CPython 3.11 and
did drift (`networkx` 3.4.2 → 3.6.1). Matching the pinned interpreter removed
the drift entirely.

---

## Import gate

```
CORE_IMPORT_TOTAL  41
CORE_IMPORT_PASS   41
CORE_IMPORT_FAIL    0
```

11 distributions, 13 exact symbols the source reaches for, 17 LAM modules in the
closure. Nothing was excused as "CUDA unavailable" — there was nothing to
excuse.

The demo stack is absent as designed: `gradio`, `omegaconf`, `spaces`, `patool`,
`opencv-python-headless`, `mmcv` and the bundled
`gradio_gaussian_render-0.0.3` wheel are all uninstalled, and the configuration
still parses. `mmcv_installed: false` is the direct evidence for L0's
DEAD_FOR_INFERENCE classification, now confirmed in a clean environment rather
than inferred from a code path.

---

## Configuration gate

18 keys compared against `lam-inference-config.json`. **Zero differences.**

```
audio_sr 16000 · fps 30.0 · id_idx 0 · num_identity_classes 12
expression_dim 52 · identity_feat_dim 64 · hidden_dim 512 · norm_type ln
use_transformer false · movement_smooth false · brow_movement false
num_attention_heads 8 · num_transformer_layers 6
pretrained_encoder_type wav2vec
pretrained_encoder_path facebook/wav2vec2-base-960h
wav2vec2_config_path configs/wav2vec2_config.json
weight pretrained_models/lam_audio2exp_streaming.tar
infer.type Audio2ExpressionInfer
```

`encoder_path_exists_on_disk: false` — L0's finding reproduces in the clean
environment. The configured encoder path is a HuggingFace repo id, not a
filesystem path, so `models/network.py:40` takes the `else` branch and no
encoder is downloaded.

`seed_in_config: null`, so **`DETERMINISTIC = false`** still holds. Fix at L2 by
passing `--options seed=<int>`. Only the eye-blink channels (8, 9) are affected;
`jawOpen` (24) is untouched by any random path.

---

## Output contract

```
INPUT_SAMPLE_RATE      16000
OUTPUT_FPS             30.0
OUTPUT_CHANNEL_COUNT   52
JAWOPEN_INDEX          24
JAWOPEN_CHANNEL_NAME   jawOpen
```

Read out of the rebuilt environment, and identical to the L0 lock. Full ordered
channel list in `lam-environment-manifest.json`.

No DD mapping was implemented. The MVP edge remains exactly one:
ARKit channel 24 `jawOpen` → DD morph target `jawOpen`.

---

## Model structure

`MODEL_STRUCTURE_LOAD = PASS`

```
DefaultEstimator
  backbone  Audio2Expression
  encoder   Wav2Vec2Model
  parameters   102,113,044
  device       cpu
  weights_loaded  false
```

The architecture builds on CPU from the in-repo `configs/wav2vec2_config.json`.
No checkpoint was downloaded — the two `.tar` weight files (406,176,139 B) stay
untouched at their pinned revision. This is a structural pass, not a weights
pass, and it is not being reported as one.

---

## Local GPU — recorded, not used

An assumption going in was that this machine had no CUDA device. That was wrong.

```
LOCAL_GPU_AVAILABLE     true
device                  NVIDIA GeForce GTX 1060 3GB
compute capability      6.1 (sm_61)
memory                  3.00 GiB
driver                  582.66
torch cuda build        12.1
```

`torch 2.1.2+cu121` ships sm_61 kernels, so this device is usable in principle.
The model is ~102 M parameters, roughly 408 MB at fp32, which would plausibly
fit in 3 GiB.

**Nothing was run on it.** This is a capability query — no kernel was launched,
no inference performed. It is recorded because it changes what L2 might cost,
and that is the Human's decision to make, not mine.

---

## Reproducibility claims

```
PYTHON_REPRODUCIBILITY     EXACT_LOCK
OS_PACKAGE_REPRODUCIBILITY MEASURED_NOT_FULLY_PINNED
```

49 of 49 Python distributions at the locked version. No OS package or base image
layer is pinned, so no bit-for-bit image reproducibility is claimed. L1 is an
environment reconstruction gate, not deployment-image certification.

---

## Docker

`Dockerfile.lam-a2e-v1` is written and **not built**. Local Docker is
unavailable and no cloud build is authorised. It is a reviewed draft: base
`nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04` (runtime, not devel — nothing
compiles), the same two-step install with the same constraints file, source
pinned by SHA with an assertion, weights left on a mount rather than baked in.

The SOAP image (`torch 2.3.1+cu121`) is untouched and stays separate.

---

## Isolation

```
SOAP_FILES_CHANGED       0
SOAP_DOCKER_CHANGED      0
SOAP_PYTHON_ENV_CHANGED  0
PAID_ACTIONS_EXECUTED    0
NEW_GPU_SPEND            $0
PRODUCTION_ASSET         public/models/docent-qka2.glb untouched
```

Nothing was installed into the product or SOAP environment. Nothing was staged
or committed.

---

## Carried into L2

1. Confirm the fine-tuned encoder weights really are inside
   `LAM_audio2exp_streaming.tar`. L0 derived this from the `os.path.exists`
   guard; it has still not been measured.
2. Pin a seed before claiming any reproducible output artifact.
3. `engines/infer.py:200-203` calls `.cuda(non_blocking=True)` unconditionally,
   so the streaming path cannot run on CPU without a source change.
4. `engines/infer.py:206` is a bare `except:` that returns `None` where the
   caller unpacks a tuple — a model failure will surface as a confusing
   `TypeError`.
5. `libgomp` in the Linux torch wheel is still unverified.

`NEXT_GATE = HUMAN_APPROVAL_FOR_LAM_L2_GPU_INFERENCE`
