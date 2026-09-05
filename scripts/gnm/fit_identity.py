"""사진 랜드마크 → GNM identity 계수 피팅.

extract_landmarks.py가 뽑은 68점을 GNM의 68 랜드마크 정의(무게중심 좌표)에
맞춰, identity 계수를 정규화 최소자승으로 추정한다.

랜드마크는 스케일·회전·평행이동이 사진마다 제각각이므로, 다음을 번갈아 반복한다:
  1) 현재 얼굴의 랜드마크에 목표 랜드마크를 닮음변환(Umeyama)으로 정렬
  2) 정렬된 목표에 맞도록 identity 계수를 최소자승으로 갱신

눈알·치아 성분은 사진 랜드마크로 관측되지 않으므로 평균값(0)에 고정한다.

사용법:
  cd C:/Users/kbs02/Desktop/gnm-pipeline
  ./venv/Scripts/python <repo>/scripts/gnm/fit_identity.py \
      --landmarks ./out/landmarks.npz --out ./out/identity.npz
"""

from __future__ import annotations

import argparse
import os
import pathlib

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np

from gnm.shape import gnm_landmarks, gnm_numpy


def umeyama_similarity(
    source: np.ndarray, target: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    """source를 target에 맞추는 닮음변환 (scale, R, t)을 구한다."""
    src_mean = source.mean(axis=0)
    dst_mean = target.mean(axis=0)
    src_c = source - src_mean
    dst_c = target - dst_mean

    covariance = dst_c.T @ src_c / len(source)
    u, singular, vt = np.linalg.svd(covariance)

    # 반사(거울상)를 방지한다
    correction = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        correction[2, 2] = -1.0

    rotation = u @ correction @ vt
    variance = (src_c**2).sum() / len(source)
    scale = float(np.trace(np.diag(singular) @ correction) / variance)
    translation = dst_mean - scale * rotation @ src_mean
    return scale, rotation, translation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--landmarks", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument(
        "--regularization",
        type=float,
        default=0.1,
        help=(
            "Gram 행렬 대각 평균에 대한 상대 강도. GNM은 미터 단위라 절대값으로 주면 "
            "정규화가 데이터를 압도한다. 클수록 평균 얼굴에 가까워진다."
        ),
    )
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument(
        "--jaw-weight",
        type=float,
        default=0.15,
        help=(
            "턱선(0-16) 랜드마크 가중치. MediaPipe의 얼굴 외곽선은 이미지상 실루엣이라 "
            "GNM의 해부학적 턱 정의와 대응이 어긋난다. 낮게 주고 눈·코·입에 맡긴다."
        ),
    )
    parser.add_argument(
        "--max-abs",
        type=float,
        default=2.5,
        help="계수 절대값 상한 (GNM 권장 범위 -3~3)",
    )
    args = parser.parse_args()

    target_68 = np.load(args.landmarks)["points_68"].astype(np.float64)
    if target_68.shape != (68, 3):
        raise SystemExit(f"랜드마크 형태가 (68,3)이 아닙니다: {target_68.shape}")

    print("Loading GNM head model...")
    gnm = gnm_numpy.GNM.from_local(
        version=gnm_numpy.GNMMajorVersion.V3,
        variant=gnm_numpy.GNMVariant.HEAD,
    )
    config = gnm_landmarks.load_landmarks(gnm_landmarks.GNMLandmarksType.HEAD_SPARSE_68)
    lm_indices = np.asarray(config.indices)  # (68, 3) 정점 인덱스
    lm_weights = np.asarray(config.weights, dtype=np.float64)  # (68, 3) 무게

    template = np.asarray(gnm.template_vertex_positions, dtype=np.float64)
    basis = np.asarray(gnm.vertex_identity_basis, dtype=np.float64)  # (253, V, 3)

    # 랜드마크 = 삼각형 세 정점의 무게중심 조합 → 평균/기저도 같은 조합으로 축약
    lm_mean = np.einsum("kj,kjd->kd", lm_weights, template[lm_indices])  # (68,3)
    lm_basis = np.einsum("kj,ckjd->ckd", lm_weights, basis[:, lm_indices])  # (253,68,3)

    # 사진 랜드마크로는 눈알·치아를 관측할 수 없으므로 head 성분만 푼다
    names = list(gnm.identity_names)
    fit_mask = np.array([n.startswith("head_") for n in names])
    fit_indices = np.flatnonzero(fit_mask)
    print(f"identity {len(names)}개 중 head 성분 {fit_indices.size}개만 피팅합니다.")

    # 설계행렬 A: (68*3, n_fit)
    # 랜드마크별 신뢰도 가중치 (턱선은 대응이 부정확해 낮춘다)
    point_weights = np.ones(68)
    point_weights[0:17] = args.jaw_weight
    # x,y,z 세 성분에 같은 가중치를 펼친다
    weight_vector = np.repeat(point_weights, 3)

    design = lm_basis[fit_indices].reshape(fit_indices.size, -1).T
    weighted_design = design * weight_vector[:, None]
    gram = design.T @ weighted_design
    # 정규화는 Gram 스케일에 맞춰 상대적으로 준다 (모델 단위가 미터라 매우 작음)
    gram_scale = float(np.trace(gram) / fit_indices.size)
    reg = args.regularization * gram_scale * np.eye(fit_indices.size)
    print(
        f"턱선 가중치 {args.jaw_weight} | Gram 대각 평균 {gram_scale:.3e} "
        f"→ 정규화 {args.regularization * gram_scale:.3e}"
    )

    coefficients = np.zeros(len(names))
    face_scale = np.linalg.norm(lm_mean - lm_mean.mean(axis=0), axis=1).mean()

    # 정렬 단계도 신뢰도 높은 점 위주로 맞춘다 (가중치를 반복 횟수로 근사)
    align_selection = np.repeat(
        np.arange(68), np.maximum(1, (point_weights * 10).astype(int))
    )

    for iteration in range(args.iterations):
        current = lm_mean + np.einsum("c,ckd->kd", coefficients, lm_basis)
        # 목표 랜드마크를 현재 얼굴의 좌표계로 가져온다
        scale, rotation, translation = umeyama_similarity(
            target_68[align_selection], current[align_selection]
        )
        aligned = (scale * (rotation @ target_68.T)).T + translation

        residual = ((aligned - lm_mean).reshape(-1)) * weight_vector
        solved = np.linalg.solve(gram + reg, design.T @ residual)
        solved = np.clip(solved, -args.max_abs, args.max_abs)

        coefficients = np.zeros(len(names))
        coefficients[fit_indices] = solved

        fitted = lm_mean + np.einsum("c,ckd->kd", coefficients, lm_basis)
        error = np.linalg.norm(fitted - aligned, axis=1)
        inner_rms = float(error[17:].mean())  # 턱선을 뺀 핵심 이목구비 오차
        print(
            f"  iter {iteration + 1:2d}: 이목구비 RMS {inner_rms:.5f} "
            f"(얼굴 크기 대비 {inner_rms / face_scale * 100:.2f}%)"
        )

    active = np.abs(coefficients) > 0.05
    print(f"\n0이 아닌 계수 {int(active.sum())}개")
    print(
        f"  계수 절대값: 평균 {np.abs(coefficients[active]).mean():.3f}, "
        f"최대 {np.abs(coefficients).max():.3f}"
    )
    strongest = np.argsort(-np.abs(coefficients))[:8]
    print("  영향 큰 성분:", ", ".join(f"{names[i]}={coefficients[i]:+.2f}" for i in strongest))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, identity=coefficients.astype(np.float32))
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
