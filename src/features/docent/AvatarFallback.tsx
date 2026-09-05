import type { DocentEmotion } from "@/types/docent";

const EMOTION_FACES: Record<DocentEmotion, string> = {
  neutral: "🙂",
  smile: "😄",
  thinking: "🤔",
  surprised: "😮",
  sad: "🙁",
};

/** WebGL 불가/렌더 오류 시에도 감정 피드백을 유지하는 정적 폴백. */
export function AvatarFallback({ emotion }: { emotion: DocentEmotion }) {
  return (
    <div className="relative flex h-[42vh] min-h-[300px] w-full items-center justify-center overflow-hidden rounded-[32px] bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.15),rgba(11,17,32,0.6))] lg:h-[560px]">
      <span role="img" aria-label={`도슨트 표정: ${emotion}`} className="text-8xl">
        {EMOTION_FACES[emotion]}
      </span>
      <p className="absolute bottom-6 text-xs text-slate-500">
        3D를 사용할 수 없는 환경이라 간단 모드로 표시 중입니다
      </p>
    </div>
  );
}
