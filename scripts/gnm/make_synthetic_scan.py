"""알려진 identity로 얼굴을 만들어 '가짜 스캔' OBJ로 저장 (파이프라인 검증용)."""
import os; os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import numpy as np, trimesh
from gnm.shape import gnm_numpy

g = gnm_numpy.GNM.from_local(version=gnm_numpy.GNMMajorVersion.V3, variant=gnm_numpy.GNMVariant.HEAD)
rng = np.random.default_rng(123)
names = list(g.identity_names)
truth = np.zeros(len(names))
head = np.flatnonzero([n.startswith('head_') for n in names])
truth[head[:40]] = rng.normal(0, 0.8, 40)   # 상위 40개 성분만 흔들기
np.savez('out/truth_identity.npz', identity=truth.astype(np.float32))

v = np.asarray(g(truth, np.zeros(g.expression_dim), np.zeros((g.num_joints,3)), np.zeros(3)))
tris = np.asarray(g.triangles)
# 실제 스캔처럼 얼굴 앞면만 남긴다
mask = np.asarray(g.vertex_group_mask('hockey_mask'))
keep_face = mask[tris].all(axis=1)
sub = trimesh.Trimesh(vertices=v, faces=tris[keep_face], process=False)
sub.remove_unreferenced_vertices()
# 임의 자세/스케일 + 노이즈 (스캔 오차 모사)
ang = 0.7
R = np.array([[np.cos(ang),0,np.sin(ang)],[0,1,0],[-np.sin(ang),0,np.cos(ang)]])
sub.vertices = (13.7 * (R @ sub.vertices.T).T) + np.array([5.0,-2.0,8.0])
sub.vertices += rng.normal(0, 0.004, sub.vertices.shape)   # 스캔 노이즈 ~0.3mm 상당
sub.export('out/synthetic_scan.obj')
print('saved out/synthetic_scan.obj', sub.vertices.shape, sub.faces.shape)
print('truth 계수 활성:', int((abs(truth)>0.05).sum()), '평균절대', abs(truth[abs(truth)>0.05]).mean().round(3))
