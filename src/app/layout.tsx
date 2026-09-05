// Standalone entry shell (T-001 Scope 6).
//
// 원본의 src/app/playground/page.tsx 는 포트폴리오 전용 shell(SiteHeader · navigation ·
// ReflexGame · DocentDevlog · 히어로 카피)이라 이관하지 않았다. 여기에는 Docent 를
// 마운트하는 데 필요한 최소 구조만 둔다. 포트폴리오 레이아웃을 재현하지 않는다.
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Digital Docent",
  description:
    "Google GNM 파라메트릭 헤드 모델과 Claude API로 만든 3D 도슨트 — Baseline v0.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
