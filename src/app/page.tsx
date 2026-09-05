// Standalone entry point (T-001 Scope 6).
//
// Docent 체험만 렌더한다. 원본 playground 페이지의 히어로 · Devlog · 미니게임 ·
// SiteHeader 는 포트폴리오 전용이라 이관 대상이 아니다.
import { DocentExperience } from "@/features/docent/DocentExperience";

export default function Page() {
  return (
    <main>
      <DocentExperience />
    </main>
  );
}
