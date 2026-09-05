// canonical source commit b295c1cc20f117b18c7ef2d916ded6aec549f565 의
// src/types/portfolio.ts 에서 Docent closure 가 실제로 쓰는 타입만 옮겼다.
// 나머지 포트폴리오 전용 타입(NavItem · TimelineItem · Project · ProjectTheme ·
// FloatingProjectCard 등)은 standalone Docent 와 무관하므로 이관하지 않았다.
//
// 원본 KnowledgeNote 는 category · difficulty · readingTime 을 함께 갖지만,
// corpus 스냅샷(knowledge/docent-corpus.json)은 retrieval 이 읽는 필드와
// 배열 순서 재구성에 필요한 lastUpdated 만 보존한다. retrieval 은 title ·
// summary · keywords · body 만 읽는다.

export type KnowledgeNote = {
  slug: string;
  title: string;
  summary: string;
  keywords: string[];
  body: string;
  lastUpdated: string;
};
