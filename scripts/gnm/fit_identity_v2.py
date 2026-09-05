"""사진/스캔 → GNM identity 피팅 v2 (랜드마크 앵커링). ⚠️ 여전히 불충분.

━━━ 검증 결과 (make_synthetic_scan + synth_landmarks 왕복) ━━━
  · 랜드마크만: 계수 상관 0.39 (annealing으로 reg를 0.05까지 낮추면 과적합해
    v1의 0.45보다 오히려 나빠짐. 스윗스팟은 reg=2 근처의 0.45~0.50)
  · 랜드마크+밀집: 밀집 대응이 발산(상관 -0.13). 랜드마크와 스캔이 같은
    좌표계일 때만 결합이 유효한데, 실물 스캔이 있어야 그 조건이 성립한다.

결론: 68개 성긴 랜드마크로 head 170개 계수를 푸는 것은 근본적으로 정보가
부족하다(부정방정식 + GNM 기저의 얼굴 영역 높은 상관 → 불량조건). 상관
0.45~0.50이 이 방식의 천장이고, "대략 방향은 맞지만 닮지는 않는" 수준이다.

진짜로 닮게 하려면:
  - 실물 밀집 스캔(갤럭시 KIRI Engine 등, 랜드마크와 같은 좌표계)
  - 또는 여러 각도 사진 기반 광류/뉴럴 회귀(별도 프로젝트 규모)
검증 하네스(make_synthetic_scan.py, synth_landmarks.py)는 남겨두어, 실물
스캔을 확보하면 이 스크립트로 즉시 상관을 재측정할 수 있다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━



v1(fit_identity.py)은 68점만, fit_identity_from_scan.py는 밀집 표면만 썼고,
둘 다 형상 복원에 실패했다(합성 검증 상관 0.45~0.63). 원인은:
  - 68점: 볼·이마 구속이 없어 얼굴 살집이 미정
  - 밀집 ICP: 최근접 대응이 접선으로 미끄러져 대응이 해부학적으로 안 고정됨

v2는 두 신호를 결합한다:
  - 랜드마크(있으면): 접선 위치를 고정하는 앵커. 대응이 절대 미끄러지지 않음
  - 밀집 표면(스캔 있으면): 랜드마크가 없는 볼·이마를 채우는 잔차

핵심 개선:
  1) 대응은 랜드마크가 지배(초반 가중치 크게), 밀집은 보조
  2) 정규화 annealing: 강 → 약으로 낮춰가며 평균에서 점진 이탈
  3) 합성 검증(make_synthetic_scan.py)으로 계수 상관을 직접 측정

사용법(사진만, 68 랜드마크):
  ./venv/Scripts/python fit_identity_v2.py --landmarks out/landmarks.npz --out out/id_v2.npz
사용법(스캔, 68 랜드마크 + 밀집):
  ./venv/Scripts/python fit_identity_v2.py --landmarks out/landmarks.npz \
      --scan out/synthetic_scan.obj --out out/id_v2.npz
"""

from __future__ import annotations

import argparse
import os
import pathlib

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np

from gnm.shape import gnm_landmarks, gnm_numpy

try:
    import trimesh
except ImportError:
    trimesh = None


def umeyama(source: np.ndarray, target: np.ndarray, weights: np.ndarray | None = None):
    """source→target 닮음변환 (scale, R, t). 가중 지원."""
    if weights is None:
        weights = np.ones(len(source))
    w = weights / weights.sum()
    src_mean = (source * w[:, None]).sum(axis=0)
    dst_mean = (target * w[:, None]).sum(axis=0)
    src_c, dst_c = source - src_mean, target - dst_mean
    cov = (dst_c * w[:, None]).T @ src_c
    u, s, vt = np.linalg.svd(cov)
    d = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[2, 2] = -1.0
    rotation = u @ d @ vt
    var = (w[:, None] * src_c**2).sum()
    scale = float(np.trace(np.diag(s) @ d) / max(var, 1e-12))
    return scale, rotation, dst_mean - scale * rotation @ src_mean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--landmarks", type=pathlib.Path, required=True)
    parser.add_argument("--scan", type=pathlib.Path, default=None)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--reg-start", type=float, default=3.0, help="정규화 시작(강)")
    parser.add_argument("--reg-end", type=float, default=0.05, help="정규화 끝(약)")
    parser.add_argument("--max-abs", type=float, default=2.5)
    parser.add_argument(
        "--jaw-weight", type=float, default=0.2, help="턱선 랜드마크 신뢰도"
    )
    parser.add_argument(
        "--dense-weight",
        type=float,
        default=0.15,
        help="밀집 표면 대응의 랜드마크 대비 상대 가중치",
    )
    args = parser.parse_args()

    target_68 = np.load(args.landmarks)["points_68"].astype(np.float64)

    print("Loading GNM head model...")
    gnm = gnm_numpy.GNM.from_local(
        version=gnm_numpy.GNMMajorVersion.V3, variant=gnm_numpy.GNMVariant.HEAD
    )
    template = np.asarray(gnm.template_vertex_positions, dtype=np.float64)
    basis = np.asarray(gnm.vertex_identity_basis, dtype=np.float64)  # (253,V,3)
    names = list(gnm.identity_names)
    fit = np.flatnonzero([n.startswith("head_") for n in names])

    # 랜드마크 = 삼각형 무게중심 조합
    cfg = gnm_landmarks.load_landmarks(gnm_landmarks.GNMLandmarksType.HEAD_SPARSE_68)
    lm_idx = np.asarray(cfg.indices)
    lm_w = np.asarray(cfg.weights, dtype=np.float64)
    lm_mean = np.einsum("kj,kjd->kd", lm_w, template[lm_idx])  # (68,3)
    lm_basis_full = np.einsum("kj,ckjd->ckd", lm_w, basis[:, lm_idx])  # (253,68,3)
    lm_basis = lm_basis_full[fit]  # (n_fit,68,3)

    # 랜드마크 신뢰도 (턱선 낮춤)
    lm_conf = np.ones(68)
    lm_conf[0:17] = args.jaw_weight

    # 밀집 표면(선택): 얼굴 앞면 정점 표본
    scan_mesh = None
    dense_indices = np.array([], dtype=int)
    dense_template = np.zeros((0, 3))
    dense_basis = np.zeros((fit.size, 0, 3))
    if args.scan is not None:
        if trimesh is None:
            raise SystemExit("trimesh가 필요합니다: pip install trimesh rtree")
        scan_mesh = trimesh.load(args.scan, force="mesh", process=False)
        face_mask = np.asarray(gnm.vertex_group_mask("hockey_mask"))
        dense_indices = np.flatnonzero(face_mask)
        rng = np.random.default_rng(0)
        if dense_indices.size > 1200:
            dense_indices = np.sort(rng.choice(dense_indices, 1200, replace=False))
        dense_template = template[dense_indices]
        dense_basis = basis[np.ix_(fit, dense_indices)]  # (n_fit,S,3)
        print(f"  밀집 표면 정점 {dense_indices.size}개 사용")

    # 설계행렬은 랜드마크+밀집을 세로로 쌓는다
    A_lm = lm_basis.reshape(fit.size, -1).T  # (68*3, n_fit)
    A_dense = dense_basis.reshape(fit.size, -1).T  # (S*3, n_fit)

    coefficients = np.zeros(len(names))
    face_scale = np.linalg.norm(lm_mean - lm_mean.mean(axis=0), axis=1).mean()
    gram_scale = float(np.trace(A_lm.T @ A_lm) / fit.size)

    # 정렬은 랜드마크로만 (신뢰도 가중)
    align_sel = np.repeat(np.arange(68), np.maximum(1, (lm_conf * 10).astype(int)))

    for it in range(args.iterations):
        frac = it / max(args.iterations - 1, 1)
        reg = (
            args.reg_start * (1 - frac) + args.reg_end * frac
        ) * gram_scale  # annealing

        cur_lm = lm_mean + np.einsum("c,ckd->kd", coefficients[fit], lm_basis)
        scale, rot, trans = umeyama(target_68[align_sel], cur_lm[align_sel])
        aligned_lm = (scale * (rot @ target_68.T)).T + trans

        # 랜드마크 잔차 (신뢰도 가중)
        lm_weight_vec = np.repeat(lm_conf, 3)
        res_lm = ((aligned_lm - lm_mean).reshape(-1)) * lm_weight_vec
        AtA = (A_lm * lm_weight_vec[:, None]).T @ A_lm
        Atb = A_lm.T @ res_lm

        # 밀집 잔차 (스캔 있을 때만)
        dense_rms = 0.0
        if scan_mesh is not None:
            cur_dense = dense_template + np.einsum(
                "c,ckd->kd", coefficients[fit], dense_basis
            )
            in_scan = ((1.0 / scale) * (rot.T @ (cur_dense - trans).T)).T
            closest, dist, _ = trimesh.proximity.closest_point(scan_mesh, in_scan)
            keep = dist <= max(np.percentile(dist, 85), 1e-9)
            target_dense = (scale * (rot @ closest.T)).T + trans
            dw = np.repeat((keep * args.dense_weight).astype(float), 3)
            res_d = ((target_dense - dense_template).reshape(-1)) * dw
            AtA = AtA + (A_dense * dw[:, None]).T @ A_dense
            Atb = Atb + A_dense.T @ res_d
            dense_rms = float(np.linalg.norm(cur_dense - target_dense, axis=1)[keep].mean())

        solved = np.clip(
            np.linalg.solve(AtA + reg * np.eye(fit.size), Atb),
            -args.max_abs,
            args.max_abs,
        )
        coefficients = np.zeros(len(names))
        coefficients[fit] = solved

        fitted_lm = lm_mean + np.einsum("c,ckd->kd", coefficients[fit], lm_basis)
        inner_rms = float(np.linalg.norm(fitted_lm - aligned_lm, axis=1)[17:].mean())
        if it % 5 == 0 or it == args.iterations - 1:
            extra = f", 밀집RMS {dense_rms / face_scale * 100:.1f}%" if scan_mesh else ""
            print(
                f"  iter {it + 1:2d}: 이목구비 {inner_rms / face_scale * 100:.2f}%"
                f"{extra}  reg {reg / gram_scale:.2f}"
            )

    active = np.abs(coefficients) > 0.05
    print(f"\n0이 아닌 계수 {int(active.sum())}개, 절대값 평균 {np.abs(coefficients[active]).mean():.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, identity=coefficients.astype(np.float32))
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
