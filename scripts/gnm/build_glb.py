"""docent_head.npz → public/models/docent.glb (감정 5 + 비짐 6 모프타겟).

GLB 계약 (src/features/docent/DocentHead.tsx와의 인터페이스):
  - 루트 노드/메쉬 이름 "Head" (three.js에서 scene.getObjectByName("Head")가 Mesh)
  - morphTargetDictionary 키:
      감정: smile, thinking, surprised, sad, blink
      비짐: viseme_a, viseme_i, viseme_u, viseme_e, viseme_o, viseme_m
  - 원점 = 목 피벗 근사(메쉬 바닥에서 35% 높이), +Z 응시, 머리 높이 ~0.25 유닛

비짐은 입 주변 정점만 움직이므로 glTF sparse accessor로 저장한다. 움직이지
않는 정점은 파일에 아예 담기지 않아 모프 하나당 용량이 크게 줄어든다.

사용법:
  cd C:/Users/kbs02/Desktop/gnm-pipeline
  ./venv/Scripts/python <repo>/scripts/gnm/build_glb.py \
      --npz ./out/docent_head.npz --out <repo>/public/models/docent.glb
"""

from __future__ import annotations

import argparse
import os
import pathlib

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np
import pygltflib

from gnm.shape import gnm_numpy

MORPH_ORDER = [
    "smile",
    "thinking",
    "surprised",
    "sad",
    "blink",
    "viseme_a",
    "viseme_i",
    "viseme_u",
    "viseme_e",
    "viseme_o",
    "viseme_m",
]
# 부위별 재질. 우선순위 순서대로 정점에 배정한다(앞쪽이 더 구체적).
# GNM은 skin/eyes/teeth/tongue가 전체 정점을 정확히 분할하므로 누락이 없다.
# eye_exteriors(각막 껍질)는 불투명하게 그리면 홍채를 가려서 제외한다.
MATERIALS: list[tuple[str, str, list[float], float]] = [
    # (재질 이름, GNM 정점 그룹, baseColor RGBA, roughness)
    ("Pupil", "pupils", [0.02, 0.02, 0.03, 1.0], 0.25),
    ("Iris", "irises", [0.20, 0.12, 0.07, 1.0], 0.30),
    ("Sclera", "scleras", [0.93, 0.92, 0.90, 1.0], 0.35),
    ("Teeth", "teeth", [0.93, 0.91, 0.86, 1.0], 0.40),
    ("Gums", "gums", [0.72, 0.42, 0.42, 1.0], 0.60),
    ("Tongue", "tongue", [0.70, 0.36, 0.36, 1.0], 0.65),
    ("Skin", "skin", [0.86, 0.66, 0.55, 1.0], 0.62),
]
EXCLUDED_GROUP = "eye_exteriors"  # 투명해야 할 각막 껍질 — 렌더에서 뺀다

# GNM은 텍스처를 제공하지 않으므로 눈썹·입술은 정점 색상으로 그린다.
# 이 값은 피부 baseColor에 곱해지므로 1.0이 '원래 피부색'이다.
BROW_TINT = [0.52, 0.42, 0.38]  # 눈썹 — 너무 진하면 아이섀도처럼 보인다
BROW_Y_MIN = 0.309  # 눈썹 능선 높이 아래(눈두덩)는 칠하지 않는다
LIP_TINT = [1.05, 0.66, 0.62]  # 입술 — 살짝 붉게
CHEEK_TINT = [1.04, 0.90, 0.88]  # 볼 홍조 — 창백함을 덜어준다
NOSE_TINT = [1.03, 0.93, 0.92]  # 코끝도 살짝 혈색

# 머리카락: 두피 정점을 법선 방향으로 밀어낸 셸 메쉬로 만든다.
HAIR_COLOR = [0.055, 0.045, 0.05, 1.0]
HAIR_THICKNESS = 0.013  # 머리 높이 0.25 기준 (약 5.2%)
HAIR_FRONT_HAIRLINE = 0.312  # 앞머리가 내려오는 높이 (이마 두피 밴드 제거)
HAIR_BACK_HAIRLINE = 0.262  # 뒤통수는 더 아래까지 덮는다
HAIR_FALLOFF = 0.018  # 헤어라인 경계를 부드럽게 하는 폭
# sparse 제외 임계값. CVAE 샘플러가 얼굴 전체에 미세 노이즈를 남기므로
# 절대값만으로는 걸러지지 않는다. 모프 자신의 최대 변위 대비 상대 임계를 함께 쓴다.
SPARSE_EPSILON_ABS = 2e-5
SPARSE_EPSILON_REL = 0.01  # 최대 변위의 1% 미만 이동은 눈에 보이지 않음


def smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    t = np.clip((value - edge0) / max(edge1 - edge0, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def assign_triangle_materials(
    triangles: np.ndarray, base_vertices: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """GNM 정점 그룹으로 재질·정점색·머리카락 가중치를 배정한다.

    Args:
      triangles: (F, 3) 삼각형 정점 인덱스
      base_vertices: (V, 3) 변환 전 GNM 좌표계의 중립 정점

    Returns:
      (삼각형별 재질 인덱스, 제외 삼각형 마스크,
       정점 틴트 색상 (V,3), 머리카락 가중치 (V,))
    """
    gnm = gnm_numpy.GNM.from_local(
        version=gnm_numpy.GNMMajorVersion.V3,
        variant=gnm_numpy.GNMVariant.HEAD,
    )
    vertex_count = gnm.num_vertices
    # 뒤에서부터 덮어써서 앞쪽(구체적) 재질이 최종 승자가 되게 한다
    vertex_material = np.full(vertex_count, len(MATERIALS) - 1, dtype=np.int32)
    for material_index in range(len(MATERIALS) - 1, -1, -1):
        _, group, _, _ = MATERIALS[material_index]
        vertex_material[np.asarray(gnm.vertex_group_mask(group))] = material_index

    excluded_vertices = np.asarray(gnm.vertex_group_mask(EXCLUDED_GROUP))

    # 삼각형은 세 정점 중 가장 구체적인(작은 인덱스) 재질을 따른다
    triangle_material = vertex_material[triangles].min(axis=1)
    triangle_excluded = excluded_vertices[triangles].any(axis=1)

    # ── 정점 틴트: 눈썹·입술 (GNM은 텍스처가 없어 정점 색상으로 그린다) ──
    tint = np.ones((vertex_count, 3), dtype=np.float32)
    brow = (
        np.asarray(gnm.vertex_group_mask("left_brow_region"))
        | np.asarray(gnm.vertex_group_mask("middle_brow_region"))
        | np.asarray(gnm.vertex_group_mask("right_brow_region"))
    )
    # 눈썹 근육 영역 전체를 칠하면 눈두덩까지 갈색이 되므로 능선 위쪽만
    brow &= base_vertices[:, 1] >= BROW_Y_MIN
    tint[brow] = BROW_TINT
    # 볼·코는 부드럽게 섞어 경계가 티나지 않게 한다 (0~1 페이드)
    def blend_tint(group: str, color: list[float], strength: float) -> None:
        mask = np.asarray(gnm.vertex_group_mask(group)).astype(np.float32)
        blend = (mask * strength)[:, None]
        tint[:] = tint * (1.0 - blend) + np.array(color, dtype=np.float32) * blend

    blend_tint("left_cheek_region", CHEEK_TINT, 0.7)
    blend_tint("right_cheek_region", CHEEK_TINT, 0.7)
    blend_tint("nose_region", NOSE_TINT, 0.5)

    lips = np.asarray(gnm.vertex_group_mask("upper_lip")) | np.asarray(
        gnm.vertex_group_mask("lower_lip")
    )
    tint[lips] = LIP_TINT

    # ── 머리카락 가중치: 두피(얼굴 앞면·귀 제외)에서 헤어라인 위쪽 ──
    # 이마(forehead)는 hockey_mask에 속해 기본 두피에서 빠지므로, 이마 상단만
    # 따로 포함해 헤어라인이 이마로 자연스럽게 내려오게 한다.
    skin = np.asarray(gnm.vertex_group_mask("skin"))
    face = np.asarray(gnm.vertex_group_mask("hockey_mask"))
    ears = np.asarray(gnm.vertex_group_mask("ears"))
    forehead = np.asarray(gnm.vertex_group_mask("forehead_region"))
    scalp_area = (skin & ~face & ~ears) | (forehead & (base_vertices[:, 1] > 0.315))

    y = base_vertices[:, 1]
    z = base_vertices[:, 2]
    # 앞머리는 이마 위(높게), 뒤통수는 더 아래까지: z로 헤어라인을 보간
    front_ratio = smoothstep(-0.03, 0.05, z)
    hairline = HAIR_BACK_HAIRLINE + (HAIR_FRONT_HAIRLINE - HAIR_BACK_HAIRLINE) * front_ratio
    hair_weight = smoothstep(0.0, HAIR_FALLOFF, y - hairline)
    hair_weight[~scalp_area] = 0.0
    return triangle_material, triangle_excluded, tint, hair_weight


def compute_vertex_normals(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    normals = np.zeros_like(vertices)
    tri_verts = vertices[triangles]
    face_n = np.cross(
        tri_verts[:, 1] - tri_verts[:, 0], tri_verts[:, 2] - tri_verts[:, 0]
    )
    for i in range(3):
        np.add.at(normals, triangles[:, i], face_n)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths[lengths == 0] = 1.0
    return (normals / lengths).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--head-height", type=float, default=0.25)
    args = parser.parse_args()

    data = np.load(args.npz)
    triangles = np.asarray(data["triangles"], dtype=np.uint32)
    base = np.asarray(data["vertices_neutral"], dtype=np.float32)

    # --- 좌표 정규화: 원점=목 피벗 근사, 높이 스케일 ---
    mins, maxs = base.min(axis=0), base.max(axis=0)
    height = maxs[1] - mins[1]
    scale = args.head_height / height
    pivot = np.array(
        [
            (mins[0] + maxs[0]) / 2.0,
            mins[1] + 0.35 * height,
            (mins[2] + maxs[2]) / 2.0,
        ],
        dtype=np.float32,
    )
    transform = lambda v: ((v - pivot) * scale).astype(np.float32)  # noqa: E731

    base_t = transform(base)
    normals = compute_vertex_normals(base_t, triangles)

    # 얼굴이 +Z를 보는지 검증
    face_center_band = np.abs(base_t[:, 0]) < 0.01
    nose_z = base_t[face_center_band, 2]
    if abs(nose_z.min()) > abs(nose_z.max()):
        raise SystemExit(
            "얼굴이 -Z를 보고 있습니다. 180도 회전 로직이 필요합니다. "
            f"(z range: {nose_z.min():.3f}..{nose_z.max():.3f})"
        )

    missing = [n for n in MORPH_ORDER if f"vertices_{n}" not in data]
    if missing:
        raise SystemExit(
            f"npz에 없는 모프: {missing}\n"
            "generate_docent_head.py를 먼저 다시 실행하세요."
        )

    deltas = {
        name: transform(np.asarray(data[f"vertices_{name}"], dtype=np.float32)) - base_t
        for name in MORPH_ORDER
    }

    # --- 바이너리 버퍼 조립 ---
    blob = bytearray()

    def push(arr: np.ndarray) -> int:
        """blob에 4바이트 정렬로 추가하고 bufferView 인덱스를 반환."""
        while len(blob) % 4:
            blob.extend(b"\x00")
        offset = len(blob)
        raw = arr.tobytes()
        blob.extend(raw)
        buffer_views.append(
            pygltflib.BufferView(buffer=0, byteOffset=offset, byteLength=len(raw))
        )
        return len(buffer_views) - 1

    accessors: list[pygltflib.Accessor] = []
    buffer_views: list[pygltflib.BufferView] = []

    def add_dense(
        arr: np.ndarray, component_type: int, type_: str, target: int, minmax: bool
    ) -> int:
        view = push(arr)
        buffer_views[view].target = target
        acc = pygltflib.Accessor(
            bufferView=view,
            componentType=component_type,
            count=len(arr),
            type=type_,
        )
        if minmax:
            acc.min = arr.min(axis=0).tolist()
            acc.max = arr.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    def add_sparse_morph(delta: np.ndarray) -> tuple[int, int]:
        """움직인 정점만 담는 sparse accessor. (accessor 인덱스, 저장 정점 수)."""
        magnitude = np.abs(delta).max(axis=1)
        threshold = max(SPARSE_EPSILON_ABS, SPARSE_EPSILON_REL * magnitude.max())
        moved = np.flatnonzero(magnitude > threshold)
        # 전혀 안 움직이면 spec상 sparse.count>=1이라 첫 정점을 0 델타로 넣는다
        if moved.size == 0:
            moved = np.array([0], dtype=np.uint32)

        idx_view = push(moved.astype(np.uint32))
        val_view = push(delta[moved].astype(np.float32))

        acc = pygltflib.Accessor(
            # bufferView 없음 = 기본값 전부 0, sparse가 움직인 곳만 덮어씀
            componentType=pygltflib.FLOAT,
            count=len(delta),
            type="VEC3",
            min=delta.min(axis=0).tolist(),
            max=delta.max(axis=0).tolist(),
            sparse=pygltflib.Sparse(
                count=int(moved.size),
                indices=pygltflib.AccessorSparseIndices(
                    bufferView=idx_view,
                    byteOffset=0,
                    componentType=pygltflib.UNSIGNED_INT,
                ),
                values=pygltflib.AccessorSparseValues(
                    bufferView=val_view, byteOffset=0
                ),
            ),
        )
        accessors.append(acc)
        return len(accessors) - 1, int(moved.size)

    # --- 부위별 재질 배정 후 프리미티브 분리 ---
    triangle_material, triangle_excluded, vertex_tint, hair_weight = (
        assign_triangle_materials(triangles, base)
    )
    print(f"각막 껍질({EXCLUDED_GROUP}) 삼각형 {int(triangle_excluded.sum())}개 제외")

    primitives: list[pygltflib.Primitive] = []
    materials: list[pygltflib.Material] = []
    print("\n재질별 프리미티브:")
    for material_index, (name, group, color, roughness) in enumerate(MATERIALS):
        selected = (triangle_material == material_index) & ~triangle_excluded
        if not selected.any():
            continue

        sub_triangles = triangles[selected]
        # 이 프리미티브가 쓰는 정점만 골라 인덱스를 다시 매긴다
        used = np.unique(sub_triangles)
        remap = np.full(len(base_t), -1, dtype=np.int64)
        remap[used] = np.arange(used.size)
        local_triangles = remap[sub_triangles].astype(np.uint32)

        idx_indices = add_dense(
            local_triangles.reshape(-1, 1),
            pygltflib.UNSIGNED_INT,
            "SCALAR",
            pygltflib.ELEMENT_ARRAY_BUFFER,
            minmax=False,
        )
        # SCALAR는 (N,1)로 넣었으므로 count를 정점 인덱스 개수로 되돌린다
        accessors[idx_indices].count = local_triangles.size

        idx_position = add_dense(
            base_t[used], pygltflib.FLOAT, "VEC3", pygltflib.ARRAY_BUFFER, minmax=True
        )
        idx_normal = add_dense(
            normals[used], pygltflib.FLOAT, "VEC3", pygltflib.ARRAY_BUFFER, minmax=False
        )

        target_accessors = [
            add_sparse_morph(deltas[morph][used])[0] for morph in MORPH_ORDER
        ]

        attributes = pygltflib.Attributes(POSITION=idx_position, NORMAL=idx_normal)
        # 피부에만 정점 틴트(눈썹·입술)를 얹는다 — glTF 스펙상 COLOR_0은
        # baseColorFactor에 곱해진다.
        if name == "Skin":
            idx_color = add_dense(
                vertex_tint[used],
                pygltflib.FLOAT,
                "VEC3",
                pygltflib.ARRAY_BUFFER,
                minmax=False,
            )
            attributes.COLOR_0 = idx_color

        primitives.append(
            pygltflib.Primitive(
                attributes=attributes,
                indices=idx_indices,
                material=len(materials),
                targets=[pygltflib.Attributes(POSITION=i) for i in target_accessors],
            )
        )
        materials.append(
            pygltflib.Material(
                name=name,
                pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                    baseColorFactor=color,
                    metallicFactor=0.0,
                    roughnessFactor=roughness,
                ),
                doubleSided=False,
            )
        )
        print(
            f"  {name:8s} 정점 {used.size:6d}, 삼각형 {int(selected.sum()):6d}  ({group})"
        )

    # ── 머리카락 셸: 두피 정점을 법선 방향으로 밀어낸 복제 메쉬 ──
    # GNM은 머리카락이 없으므로, 두피를 덮는 짧은 머리를 지오메트리로 만든다.
    # 헤어라인에서 가중치가 0으로 줄어 두께가 자연스럽게 사라진다.
    hair_triangle_mask = (hair_weight[triangles] > 0.02).any(axis=1)
    if hair_triangle_mask.any():
        sub_triangles = triangles[hair_triangle_mask]
        used = np.unique(sub_triangles)
        remap = np.full(len(base_t), -1, dtype=np.int64)
        remap[used] = np.arange(used.size)
        local_triangles = remap[sub_triangles].astype(np.uint32)

        shell_positions = (
            base_t[used]
            + normals[used] * (HAIR_THICKNESS * hair_weight[used])[:, None]
        ).astype(np.float32)

        idx_indices = add_dense(
            local_triangles.reshape(-1, 1),
            pygltflib.UNSIGNED_INT,
            "SCALAR",
            pygltflib.ELEMENT_ARRAY_BUFFER,
            minmax=False,
        )
        accessors[idx_indices].count = local_triangles.size
        idx_position = add_dense(
            shell_positions, pygltflib.FLOAT, "VEC3", pygltflib.ARRAY_BUFFER, minmax=True
        )
        idx_normal = add_dense(
            normals[used], pygltflib.FLOAT, "VEC3", pygltflib.ARRAY_BUFFER, minmax=False
        )
        # 표정이 관자놀이·이마를 살짝 움직이므로 셸도 같은 모프를 따라간다
        target_accessors = [
            add_sparse_morph(deltas[morph][used])[0] for morph in MORPH_ORDER
        ]
        primitives.append(
            pygltflib.Primitive(
                attributes=pygltflib.Attributes(
                    POSITION=idx_position, NORMAL=idx_normal
                ),
                indices=idx_indices,
                material=len(materials),
                targets=[pygltflib.Attributes(POSITION=i) for i in target_accessors],
            )
        )
        materials.append(
            pygltflib.Material(
                name="Hair",
                pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                    baseColorFactor=HAIR_COLOR,
                    metallicFactor=0.0,
                    roughnessFactor=0.55,
                ),
                doubleSided=True,
            )
        )
        print(
            f"  {'Hair':8s} 정점 {used.size:6d}, 삼각형 {int(hair_triangle_mask.sum()):6d}  (scalp shell)"
        )

    gltf = pygltflib.GLTF2()
    gltf.asset = pygltflib.Asset(
        version="2.0", generator="beomseok-portfolio gnm pipeline"
    )
    gltf.materials = materials
    gltf.meshes = [
        pygltflib.Mesh(
            name="Head",
            primitives=primitives,
            weights=[0.0] * len(MORPH_ORDER),
            extras={"targetNames": MORPH_ORDER},
        )
    ]
    gltf.nodes = [pygltflib.Node(name="Head", mesh=0)]
    gltf.scenes = [pygltflib.Scene(name="DocentHead", nodes=[0])]
    gltf.scene = 0
    gltf.accessors = accessors
    gltf.bufferViews = buffer_views
    gltf.buffers = [pygltflib.Buffer(byteLength=len(blob))]

    gltf.set_binary_blob(bytes(blob))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    gltf.save_binary(str(args.out))

    size_mb = args.out.stat().st_size / 1e6
    print(f"\nSaved {args.out} ({size_mb:.2f} MB)")
    print(f"  프리미티브 {len(primitives)}개, 재질 {len(materials)}개")
    print(f"  morphs({len(MORPH_ORDER)})={MORPH_ORDER}")
    if size_mb > 3:
        print("  WARNING: >3MB — gltf-transform draco 압축 검토")


if __name__ == "__main__":
    main()
