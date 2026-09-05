"""사진에서 얼굴 랜드마크를 뽑아 npz로 저장한다 (MediaPipe FaceLandmarker).

MediaPipe는 protobuf 버전이 tensorflow와 충돌하므로 별도 venv에서 실행한다.

사용법:
  cd C:/Users/kbs02/Desktop/gnm-pipeline
  ./venv-mp/Scripts/python <repo>/scripts/gnm/extract_landmarks.py \
      --image <repo>/public/images/profile/beomseok-main.jpg \
      --model ./face_landmarker.task \
      --out ./out/landmarks.npz

출력 npz:
  points_478 : (478, 3) MediaPipe 원시 랜드마크 (x,y는 0~1 정규화, z는 상대 깊이)
  points_68  : (68, 3)  iBUG-68 순서로 재배열한 랜드마크
  image_size : (2,)     원본 이미지 (width, height)
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
from PIL import Image

import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options as base_options_module

# MediaPipe FaceMesh(468/478) → iBUG-68 랜드마크 인덱스 매핑.
# 널리 쓰이는 대응표이며, 68점 순서는 dlib/iBUG 표준을 따른다.
MP_TO_IBUG68 = [
    # 턱선 17점 (0-16), 오른쪽 귀 → 턱 → 왼쪽 귀
    234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 454,
    # 오른쪽 눈썹 5점 (17-21)
    70, 63, 105, 66, 107,
    # 왼쪽 눈썹 5점 (22-26)
    336, 296, 334, 293, 300,
    # 콧대 4점 (27-30)
    168, 197, 5, 4,
    # 콧방울 5점 (31-35)
    75, 97, 2, 326, 305,
    # 오른쪽 눈 6점 (36-41)
    33, 160, 158, 133, 153, 144,
    # 왼쪽 눈 6점 (42-47)
    362, 385, 387, 263, 373, 380,
    # 바깥 입술 12점 (48-59)
    61, 39, 37, 0, 267, 269, 291, 405, 314, 17, 84, 181,
    # 안쪽 입술 8점 (60-67)
    78, 82, 13, 312, 308, 317, 14, 87,
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=pathlib.Path, required=True)
    parser.add_argument("--model", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    assert len(MP_TO_IBUG68) == 68, f"매핑이 68개가 아님: {len(MP_TO_IBUG68)}"

    pil = Image.open(args.image).convert("RGB")
    width, height = pil.size
    rgb = np.ascontiguousarray(np.array(pil), dtype=np.uint8)

    options = vision.FaceLandmarkerOptions(
        base_options=base_options_module.BaseOptions(
            model_asset_path=str(args.model)
        ),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=1,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
    )

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)

    if not result.face_landmarks:
        raise SystemExit(f"얼굴을 찾지 못했습니다: {args.image}")

    landmarks = result.face_landmarks[0]
    points = np.array([[p.x, p.y, p.z] for p in landmarks], dtype=np.float32)
    print(f"검출된 랜드마크: {points.shape[0]}개 (이미지 {width}x{height})")

    max_index = max(MP_TO_IBUG68)
    if max_index >= points.shape[0]:
        raise SystemExit(
            f"매핑 인덱스 {max_index}가 검출 결과({points.shape[0]})를 벗어납니다."
        )

    points_68 = points[MP_TO_IBUG68]

    # 정규화 좌표를 픽셀 종횡비에 맞춘 등방 좌표로 되돌린다.
    # x,y는 이미지 크기로 스케일하고, z는 MediaPipe 관례상 x와 같은 스케일이다.
    scaled = points_68.copy()
    scaled[:, 0] *= width
    scaled[:, 1] *= height
    scaled[:, 2] *= width
    # 이미지 좌표계(y 아래로 증가, z 카메라 쪽이 음수)를 3D 관례로 뒤집는다
    scaled[:, 1] *= -1.0
    scaled[:, 2] *= -1.0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.out,
        points_478=points,
        points_68=scaled,
        image_size=np.array([width, height], dtype=np.int32),
    )
    print(f"Saved {args.out}")

    # 간단한 sanity check: 코끝(30)이 가장 튀어나오고, 턱(8)이 가장 아래여야 한다
    nose_tip_z = scaled[30, 2]
    print(f"  코끝(30) z={nose_tip_z:.1f}  (68점 중 z최대={scaled[:,2].max():.1f})")
    chin_y = scaled[8, 1]
    print(f"  턱(8)  y={chin_y:.1f}  (68점 중 y최소={scaled[:,1].min():.1f})")


if __name__ == "__main__":
    main()
