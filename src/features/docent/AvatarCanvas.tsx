"use client";

import { Canvas } from "@react-three/fiber";
import { Component, Suspense, useEffect, useState, type ReactNode } from "react";
import { ACESFilmicToneMapping } from "three";
import type { VisemeKey } from "@/lib/docent/visemes";
import type { DocentEmotion } from "@/types/docent";
import { AvatarFallback } from "./AvatarFallback";
import { DocentHead } from "./DocentHead";

interface AvatarCanvasProps {
  emotion: DocentEmotion;
  viseme: VisemeKey | null;
}

// GLB 파싱 실패 등 Suspense 내부 throw를 흡수한다.
class AvatarErrorBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      canvas.getContext("webgl2") ?? canvas.getContext("webgl")
    );
  } catch {
    return false;
  }
}

export default function AvatarCanvas({ emotion, viseme }: AvatarCanvasProps) {
  const [webglOk, setWebglOk] = useState<boolean | null>(null);

  useEffect(() => {
    setWebglOk(webglAvailable());
  }, []);

  if (webglOk === false) return <AvatarFallback emotion={emotion} />;

  return (
    <div className="relative h-[42vh] min-h-[300px] w-full overflow-hidden rounded-[32px] bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.15),rgba(11,17,32,0.6))] lg:h-[560px]">
      <AvatarErrorBoundary fallback={<AvatarFallback emotion={emotion} />}>
        <Canvas
          camera={{ position: [0, 0.05, 0.62], fov: 30 }}
          dpr={[1, 1.75]}
          gl={{
            antialias: true,
            powerPreference: "high-performance",
            alpha: true,
            toneMapping: ACESFilmicToneMapping,
            toneMappingExposure: 1.05,
          }}
          onCreated={({ gl }) =>
            gl.domElement.addEventListener("webglcontextlost", () =>
              setWebglOk(false)
            )
          }
        >
          {/* 얼굴 정면 키라이트(따뜻)·필라이트(차가움)·림라이트로 입체감 */}
          <ambientLight intensity={0.55} />
          <directionalLight position={[1.5, 2.2, 4]} intensity={1.5} color="#fff2e6" />
          <directionalLight position={[-3, 0.5, 2]} intensity={0.45} color="#9fb8e0" />
          <directionalLight position={[0, 1.5, -3]} intensity={0.35} color="#ffffff" />
          <Suspense fallback={null}>
            <DocentHead emotion={emotion} viseme={viseme} />
          </Suspense>
        </Canvas>
      </AvatarErrorBoundary>
    </div>
  );
}
