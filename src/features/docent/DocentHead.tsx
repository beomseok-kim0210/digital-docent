"use client";

import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import { Group, MathUtils, Mesh } from "three";
import type { VisemeKey } from "@/lib/docent/visemes";
import type { DocentEmotion } from "@/types/docent";

const MODEL_URL = "/models/docent-qka2.glb";

// 감정 → 모프타겟 가중치. GLB 계약: smile/thinking/surprised/sad/blink
const EMOTION_WEIGHTS: Record<DocentEmotion, Record<string, number>> = {
  neutral: {},
  smile: { smile: 0.8 },
  thinking: { thinking: 0.9 },
  surprised: { surprised: 1 },
  sad: { sad: 0.9 },
};

const VISEME_MORPH: Record<VisemeKey, string> = {
  a: "viseme_a",
  i: "viseme_i",
  u: "viseme_u",
  e: "viseme_e",
  o: "viseme_o",
  m: "viseme_m",
};
const VISEME_MORPH_NAMES = Object.values(VISEME_MORPH);

// 입모양별 강도. 'ㅁ/ㅂ/ㅍ'(m)은 원본 변위가 커서 낮게 잡는다.
const VISEME_INTENSITY: Record<VisemeKey, number> = {
  a: 0.85,
  i: 0.7,
  u: 0.8,
  e: 0.7,
  o: 0.8,
  m: 0.45,
};

interface DocentHeadProps {
  emotion: DocentEmotion;
  /** 현재 발음 중인 입모양. null이면 입을 다문다. */
  viseme: VisemeKey | null;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const listener = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);
  return reduced;
}

export function DocentHead({ emotion, viseme }: DocentHeadProps) {
  const group = useRef<Group>(null);
  const { scene } = useGLTF(MODEL_URL);
  const reduced = usePrefersReducedMotion();
  const blink = useRef({ nextAt: 2.5, closing: false });

  // GLB가 부위별 재질(피부·흰자·홍채·치아…)로 나뉘어 있어 메쉬가 여러 개다.
  // 모프타겟을 가진 서브메쉬를 모두 모아 같은 가중치로 함께 구동한다.
  const meshes = useMemo(() => {
    const found: Mesh[] = [];
    scene.traverse((object) => {
      if (
        object instanceof Mesh &&
        object.morphTargetInfluences &&
        object.morphTargetDictionary
      ) {
        found.push(object);
      }
    });
    return found;
  }, [scene]);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;

    // 눈 깜빡임 타이밍은 메쉬마다 따로 굴리면 어긋나므로 프레임당 한 번만 계산
    let blinkTarget: number | null = null;
    if (!reduced && meshes.length > 0) {
      const b = blink.current;
      const first = meshes[0];
      const blinkIndex = first.morphTargetDictionary?.["blink"];
      if (blinkIndex !== undefined) {
        const currentBlink = first.morphTargetInfluences?.[blinkIndex] ?? 0;
        if (!b.closing && t >= b.nextAt) b.closing = true;
        if (b.closing && currentBlink > 0.85) {
          b.closing = false;
          b.nextAt = t + 2.5 + Math.random() * 3.5;
        }
        blinkTarget = b.closing ? 1 : 0;
      }
    }

    const targets = EMOTION_WEIGHTS[emotion] ?? {};
    // 말하는 중에는 감정 모프와 비짐이 같은 입술 정점을 두고 겹쳐 이를 드러낸
    // 기괴한 표정이 되므로, 발화 중에는 감정 강도를 낮춘다.
    const emotionScale = viseme ? 0.45 : 1;
    const damp = reduced ? 40 : 6;
    const activeMorph = viseme ? VISEME_MORPH[viseme] : null;
    const activeTarget = viseme ? VISEME_INTENSITY[viseme] : 0;

    for (const mesh of meshes) {
      const influences = mesh.morphTargetInfluences;
      const dictionary = mesh.morphTargetDictionary;
      if (!influences || !dictionary) continue;

      for (const [name, index] of Object.entries(dictionary)) {
        if (name === "blink") {
          // 3) 눈 깜빡임
          if (blinkTarget !== null) {
            influences[index] = MathUtils.damp(
              influences[index],
              blinkTarget,
              blinkTarget > 0 ? 30 : 18,
              delta
            );
          }
        } else if (VISEME_MORPH_NAMES.includes(name)) {
          // 2) 립싱크: 활성 비짐만 올리고 나머지는 내린다
          const target = name === activeMorph ? activeTarget : 0;
          influences[index] = MathUtils.damp(influences[index], target, 18, delta);
        } else {
          // 1) 감정 표정
          const target = (targets[name] ?? 0) * emotionScale;
          influences[index] = MathUtils.damp(influences[index], target, damp, delta);
        }
      }
    }

    // 4) 아이들 모션: 미세 스웨이 + 포인터 시선 추적
    if (group.current && !reduced) {
      const gazeX = MathUtils.clamp(state.pointer.x, -1, 1) * 0.22;
      const gazeY = MathUtils.clamp(state.pointer.y, -1, 1) * 0.12;
      group.current.rotation.y = MathUtils.damp(
        group.current.rotation.y,
        gazeX + Math.sin(t * 0.4) * 0.04,
        4,
        delta
      );
      group.current.rotation.x = MathUtils.damp(
        group.current.rotation.x,
        -gazeY + Math.sin(t * 0.7) * 0.02,
        4,
        delta
      );
      group.current.position.y = Math.sin(t * 0.8) * 0.008;
    }
  });

  return (
    <group ref={group}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload(MODEL_URL);
