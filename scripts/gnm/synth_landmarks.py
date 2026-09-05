"""합성 스캔의 정답 identity로 GNM 68 랜드마크를 만들어 points_68로 저장."""
import os; os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import numpy as np
from gnm.shape import gnm_numpy, gnm_landmarks
g = gnm_numpy.GNM.from_local(version=gnm_numpy.GNMMajorVersion.V3, variant=gnm_numpy.GNMVariant.HEAD)
truth = np.load('out/truth_identity.npz')['identity'].astype(float)
cfg = gnm_landmarks.load_landmarks(gnm_landmarks.GNMLandmarksType.HEAD_SPARSE_68)
idx=np.asarray(cfg.indices); w=np.asarray(cfg.weights,dtype=float)
v = np.asarray(g(truth, np.zeros(g.expression_dim), np.zeros((g.num_joints,3)), np.zeros(3)))
lm = np.einsum('kj,kjd->kd', w, v[idx])
# 임의 자세/스케일 부여(피팅이 정렬로 흡수해야 함)
rng=np.random.default_rng(7); ang=0.5
R=np.array([[np.cos(ang),0,np.sin(ang)],[0,1,0],[-np.sin(ang),0,np.cos(ang)]])
lm = (11.3*(R@lm.T).T)+np.array([3.,1.,-2.])
lm += rng.normal(0,0.02,lm.shape)  # 랜드마크 검출 노이즈
np.savez('out/synth_landmarks.npz', points_68=lm.astype(np.float32))
print('saved out/synth_landmarks.npz', lm.shape)
