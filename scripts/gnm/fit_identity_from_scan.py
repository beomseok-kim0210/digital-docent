"""3D 스캔 메쉬 → GNM identity 계수 피팅 (밀집 대응 방식). ⚠️ 미완성.

━━━ 검증 결과: 아직 쓸 수 없음 ━━━
make_synthetic_scan.py로 '정답 identity가 알려진 가짜 스캔'을 만들어 왕복
검증한 결과, 이 구현은 형상을 복원하지 못한다.

  · 점-표면 RMS는 얼굴 크기의 1% 수준으로 매우 낮게 나오지만,
    이는 표면을 따라 미끄러져도 낮아지는 지표라 형상 일치를 뜻하지 않는다.
  · 정답 대비 계수 상관은 정규화를 0.0001~2.0으로 훑어도 최대 0.63,
    복원된 얼굴은 정답이 아니라 '평균 얼굴'에 가깝다.
  · 스케일 고정(--freeze-scale)을 넣어도 상관 0.629로 개선 없음.

원인: 최근접점 대응은 접선 방향으로 자유롭게 미끄러지므로 대응이 해부학적으로
고정되지 않는다. GNM identity 기저가 얼굴 영역에서 서로 상관이 높아 최소자승이
불량조건이 되고, 정규화가 결국 평균에 가까운 해를 고른다.

필요한 것: 랜드마크로 대응을 앵커링한 nonrigid ICP.
  1) 68 랜드마크로 접선 위치를 고정(초반 가중치 크게)
  2) 밀집 표면은 잔차 정제에만 사용, 가중치를 점진적으로 이전
  3) 정규화를 강→약으로 annealing
━━━━━━━━━━━━━━━━━━━━━━━━━

사진 68점 피팅과 달리, 스캔은 볼·이마까지 표면 전체를 담고 있어 얼굴 살집까지
구속할 수 있다. 스캔의 정점 개수·토폴로지는 GNM과 다르므로, 최근접점(ICP)으로
대응을 매 반복마다 다시 찾는다.

  1) 다중 초기 회전에서 ICP를 돌려 가장 잘 맞는 정렬을 고른다
  2) 정렬 → 최근접 대응 → identity 계수 최소자승을 번갈아 반복한다

스캔 준비(갤럭시): KIRI Engine 또는 RealityScan으로 얼굴을 촬영해 OBJ/PLY로 내보낸다.

사용법:
  cd C:/Users/kbs02/Desktop/gnm-pipeline
  ./venv/Scripts/python <repo>/scripts/gnm/fit_identity_from_scan.py \
      --scan ./scan/face.obj --out ./out/identity_scan.npz
"""

from __future__ import annotations

import argparse
import os
import pathlib

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np
import trimesh

from gnm.shape import gnm_numpy

# 스캔이 실제로 담고 있는 영역(이마~턱, 귀~귀)만 쓴다. 뒤통수·목은 제외.
FACE_GROUP = "hockey_mask"


def similarity_transform(
    source: np.ndarray, target: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    """source를 target에 맞추는 (scale, R, t). Umeyama."""
    src_mean, dst_mean = source.mean(axis=0), target.mean(axis=0)
    src_c, dst_c = source - src_mean, target - dst_mean
    covariance = dst_c.T @ src_c / len(source)
    u, singular, vt = np.linalg.svd(covariance)
    correction = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        correction[2, 2] = -1.0
    rotation = u @ correction @ vt
    variance = (src_c**2).sum() / len(source)
    scale = float(np.trace(np.diag(singular) @ correction) / max(variance, 1e-12))
    return scale, rotation, dst_mean - scale * rotation @ src_mean


def rotation_y(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rotation_x(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


class Pose:
    """모델 좌표계 → 스캔 좌표계 닮음변환. y = scale * R @ x + t"""

    def __init__(self, scale: float, rotation: np.ndarray, translation: np.ndarray):
        self.scale = scale
        self.rotation = rotation
        self.translation = translation

    def apply(self, points: np.ndarray) -> np.ndarray:
        return (self.scale * (self.rotation @ points.T)).T + self.translation

    def invert(self, points: np.ndarray) -> np.ndarray:
        return ((self.rotation.T @ (points - self.translation).T).T) / self.scale

    def compose(self, scale: float, rotation: np.ndarray, translation: np.ndarray) -> None:
        """이 변환 뒤에 (scale, R, t)를 추가로 적용한 것과 같게 갱신한다."""
        self.translation = scale * (rotation @ self.translation) + translation
        self.rotation = rotation @ self.rotation
        self.scale = scale * self.scale


def icp_align(
    source: np.ndarray,
    scan: trimesh.Trimesh,
    initial_rotation: np.ndarray,
    iterations: int = 20,
) -> tuple[Pose, float]:
    """source를 스캔 표면에 강체+스케일 정합. (자세, 평균거리) 반환."""
    src_center = source.mean(axis=0)
    scan_center = scan.vertices.mean(axis=0)
    src_radius = np.linalg.norm(source - src_center, axis=1).mean()
    scan_radius = np.linalg.norm(scan.vertices - scan_center, axis=1).mean()

    initial_scale = scan_radius / max(src_radius, 1e-12)
    pose = Pose(
        initial_scale,
        initial_rotation,
        scan_center - initial_scale * initial_rotation @ src_center,
    )

    mean_distance = np.inf
    for _ in range(iterations):
        current = pose.apply(source)
        closest, distances, _ = trimesh.proximity.closest_point(scan, current)
        # 멀리 떨어진 대응은 이상치로 보고 버린다 (상위 20% 절단)
        cutoff = np.percentile(distances, 80)
        keep = distances <= max(cutoff, 1e-9)
        if keep.sum() < 10:
            break
        pose.compose(*similarity_transform(current[keep], closest[keep]))
        mean_distance = float(distances[keep].mean())
    return pose, mean_distance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--regularization", type=float, default=2.0)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--max-abs", type=float, default=2.5)
    parser.add_argument(
        "--samples",
        type=int,
        default=1500,
        help="ICP에 쓸 GNM 얼굴 정점 표본 수 (많을수록 정확·느림)",
    )
    parser.add_argument(
        "--freeze-scale",
        action="store_true",
        default=True,
        help="초기 정렬 후 스케일 고정 (형상이 스케일에 흡수되는 것을 막음)",
    )
    parser.add_argument(
        "--free-scale",
        dest="freeze_scale",
        action="store_false",
        help="매 반복 스케일도 자유롭게 갱신 (비교·디버깅용)",
    )
    args = parser.parse_args()

    print(f"Loading scan: {args.scan}")
    loaded = trimesh.load(args.scan, force="mesh", process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise SystemExit("삼각형 메쉬를 읽지 못했습니다.")
    scan = loaded
    print(f"  스캔 정점 {len(scan.vertices)}, 면 {len(scan.faces)}")

    print("Loading GNM head model...")
    gnm = gnm_numpy.GNM.from_local(
        version=gnm_numpy.GNMMajorVersion.V3,
        variant=gnm_numpy.GNMVariant.HEAD,
    )
    template = np.asarray(gnm.template_vertex_positions, dtype=np.float64)
    basis = np.asarray(gnm.vertex_identity_basis, dtype=np.float64)

    face_mask = np.asarray(gnm.vertex_group_mask(FACE_GROUP))
    face_indices = np.flatnonzero(face_mask)
    rng = np.random.default_rng(0)
    if face_indices.size > args.samples:
        face_indices = rng.choice(face_indices, args.samples, replace=False)
    face_indices.sort()
    print(f"  피팅 대상 GNM 정점 {face_indices.size}개 ({FACE_GROUP})")

    names = list(gnm.identity_names)
    fit_indices = np.flatnonzero([n.startswith("head_") for n in names])
    sub_template = template[face_indices]
    sub_basis = basis[np.ix_(fit_indices, face_indices)]  # (n_fit, S, 3)

    # ── 1) 다중 초기 회전으로 ICP, 최적 정렬 선택 ──
    print("초기 정렬 탐색 중...")
    best = None
    for yaw in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        for pitch in (-0.4, 0.0, 0.4):
            initial = rotation_x(pitch) @ rotation_y(yaw)
            pose, distance = icp_align(sub_template, scan, initial, iterations=12)
            if best is None or distance < best[1]:
                best = (pose, distance, yaw, pitch)
    pose, distance, yaw, pitch = best
    print(
        f"  최적 초기자세 yaw={np.degrees(yaw):.0f}° pitch={np.degrees(pitch):.0f}°, "
        f"평균거리 {distance:.4f}"
    )

    design_full = sub_basis.reshape(fit_indices.size, -1).T
    gram = design_full.T @ design_full
    gram_scale = float(np.trace(gram) / fit_indices.size)
    reg = args.regularization * gram_scale * np.eye(fit_indices.size)

    coefficients = np.zeros(len(names))
    face_scale = np.linalg.norm(
        sub_template - sub_template.mean(axis=0), axis=1
    ).mean()

    # ── 2) 자세 갱신 ↔ 형상(계수) 갱신 반복 ──
    # 자세와 형상을 분리하는 것이 핵심이다. 섞이면 강체 정렬이 형상 변화를
    # 흡수해 계수가 과소추정된다.
    for iteration in range(args.iterations):
        model = sub_template + np.einsum(
            "c,csd->sd", coefficients[fit_indices], sub_basis
        )
        model_in_scan = pose.apply(model)
        closest, distances, _ = trimesh.proximity.closest_point(scan, model_in_scan)
        cutoff = np.percentile(distances, 85)
        keep = distances <= max(cutoff, 1e-9)

        # (a) 자세만 갱신 — 현재 형상을 스캔에 정렬.
        #     스케일을 매번 자유롭게 두면 "평균 얼굴을 확대·축소"하는 것이
        #     "형상을 바꾸는 것"보다 비용이 싸서 계수가 자라지 못한다.
        #     초기 정렬에서 얻은 스케일을 고정하고 회전·이동만 갱신한다.
        delta_scale, delta_rotation, delta_translation = similarity_transform(
            model_in_scan[keep], closest[keep]
        )
        if args.freeze_scale:
            delta_scale = 1.0
            # 스케일을 1로 되돌리면 평행이동을 다시 맞춰야 한다
            delta_translation = closest[keep].mean(axis=0) - (
                delta_rotation @ model_in_scan[keep].mean(axis=0)
            )
        pose.compose(delta_scale, delta_rotation, delta_translation)

        # (b) 대응점을 모델 좌표계로 되돌려 형상만 갱신
        target = pose.invert(closest)
        weights = np.repeat(keep.astype(np.float64), 3)
        residual = ((target - sub_template).reshape(-1)) * weights
        weighted = design_full * weights[:, None]
        solved = np.linalg.solve(
            design_full.T @ weighted + reg, design_full.T @ residual
        )
        solved = np.clip(solved, -args.max_abs, args.max_abs)
        coefficients = np.zeros(len(names))
        coefficients[fit_indices] = solved

        fitted = sub_template + np.einsum(
            "c,csd->sd", coefficients[fit_indices], sub_basis
        )
        rms = float(np.linalg.norm(fitted - target, axis=1)[keep].mean())
        print(
            f"  iter {iteration + 1}: RMS {rms:.5f} "
            f"(얼굴 크기 대비 {rms / face_scale * 100:.2f}%), 유효대응 {int(keep.sum())}"
        )

    active = np.abs(coefficients) > 0.05
    print(f"\n0이 아닌 계수 {int(active.sum())}개")
    if active.any():
        print(
            f"  절대값 평균 {np.abs(coefficients[active]).mean():.3f}, "
            f"최대 {np.abs(coefficients).max():.3f}, "
            f"한계도달 {int((np.abs(coefficients) > args.max_abs - 0.01).sum())}개"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, identity=coefficients.astype(np.float32))
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
