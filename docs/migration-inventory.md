# Migration Inventory — Baseline v0

무엇을 어디서 어디로 옮겼는지, 무엇을 왜 제외했는지의 기록이다.

```
canonical source commit   b295c1cc20f117b18c7ef2d916ded6aec549f565
source access             git show <commit>:<path>   (tracked contents only)
```

원본 저장소의 working tree · untracked 파일은 사용하지 않았다. 원본에는 아무것도 쓰지 않았다.

closure는 두 entry point에서 import graph를 실제로 walk해 산출했다
(`@/` alias · 상대경로 · dynamic import 포함): **내부 20 files**, external specifier 10개 중
`node:fs` · `node:path`는 builtin이므로 npm package는 **8개**로 관측됐다.

---

## A. 무변경 이관 — byte-identical

원본 blob과 sha256이 일치한다. import 경로도 `@/` alias를 유지해 손대지 않았다.

| target | source |
|---|---|
| `src/types/docent.ts` | 동일 경로 |
| `src/lib/docent/visemes.ts` | 동일 경로 |
| `src/lib/docent/rateLimit.ts` | 동일 경로 |
| `src/lib/docent/fallback.ts` | 동일 경로 |
| `src/data/docent.ts` | 동일 경로 |
| `src/data/docentFallback.ts` | 동일 경로 |
| `src/features/docent/AvatarCanvas.tsx` | 동일 경로 |
| `src/features/docent/AvatarFallback.tsx` | 동일 경로 |
| `src/features/docent/ChatPanel.tsx` | 동일 경로 |
| `src/features/docent/DocentExperience.tsx` | 동일 경로 |
| `src/features/docent/DocentHead.tsx` | 동일 경로 |
| `src/features/docent/useDocentChat.ts` | 동일 경로 |
| `src/features/docent/useVoice.ts` | 동일 경로 |
| `public/models/docent.glb` | 동일 경로 |
| `scripts/gnm/**` (9 files) | 동일 경로 |

`@/` alias를 상대경로로 바꾸지 않은 이유: 바꾸면 모든 파일이 원본과 달라져 이관 충실도를
diff로 증명할 수 없게 된다. 대신 `tests/alias-hook.mjs`로 `node --test`에서 alias를 해석한다.

## B. 경로/타입 축소만 — 로직 변경 없음

| target | 변경 내용 |
|---|---|
| `src/types/portfolio.ts` | Docent closure가 쓰는 `KnowledgeNote`만 남겼다. 포트폴리오 전용 타입(NavItem · TimelineItem · Project · ProjectTheme · FloatingProjectCard 등) 미이관. `KnowledgeNote`에서 retrieval이 읽지 않는 `category` · `difficulty` · `readingTime`을 제외하고, 배열 순서 재구성에 필요한 `lastUpdated`는 유지했다. 이 축소로 `lucide-react` 타입 의존이 사라졌다. |

## C. Behavior-preserving data-source / framework adapter — Contract 허용 3종

### A-1 `src/lib/docent/chat.ts` ← `src/app/api/docent/chat/route.ts`

원본 route 파일에서 **런타임 선언 2줄을 얇은 라우트로 옮기고 `POST` → `handleDocentChat`
로 이름만 바꿨다.** 나머지는 전부 원본 그대로다 — 요청 validate 규칙, rate limit 분기,
fallback 분기 조건(`ANTHROPIC_API_KEY` 부재), NDJSON 이벤트 형태·순서, emotion 태그 파싱과
64자 폴백, 에러 문면, 응답 헤더.

`src/app/api/docent/chat/route.ts`는 `runtime` · `dynamic` 선언과 위임 호출만 갖는다.

### A-2 `src/lib/docent/retrieval.ts`

`getKnowledgeNotes()` 호출을 corpus 스냅샷 읽기로 교체했다. 원본 대비 diff는
**데이터 소스 3곳뿐**이며 `tokenize` · `scoreNote` · `retrieveNotesContext`는 무변경이다.

```
keyword hit +3 · title hit +2 · summary hit +1 · score > 0 ·
stable descending sort · Top-3 · body 1200자 truncate + ellipsis · 출력 formatting
```

배열 순서는 재계산하지 않는다 — 스냅샷 순서가 곧 원본 반환 순서다.

### A-3 `src/lib/docent/persona.ts`

`@/data/about` · `@/data/projects` import를 `@/data/personaProfile` 하나로 교체했다.
**system prompt 문자열은 원본과 동일**하다 — 섹션 순서·라벨·구분자·줄바꿈·행동 규칙 문면·
emotion join 결과·`staticPersona + retrieveNotesContext(question)` 결합 순서 전부 그대로다.

## D. 신규 — 저장소 경계상 필요한 최소 산출물

| path | 근거 |
|---|---|
| `knowledge/docent-corpus.json` | Contract Scope 4. canonical commit `getKnowledgeNotes()` 전체 스냅샷 **57건**, 반환 배열 순서 그대로 |
| `src/data/personaProfile.ts` | Contract Scope 5. persona가 읽는 필드만 스냅샷. 원본 모듈을 실행해 추출했고 손으로 옮기지 않았다 |
| `src/app/layout.tsx` · `src/app/page.tsx` | Contract Scope 6. Docent만 마운트하는 최소 shell |
| `tests/alias-hook.mjs` | `node --test`에서 `@/` alias 해석. 이관 파일을 고치지 않기 위한 장치 |
| `tests/fixtures/retrieval-parity.json` | 원본 코드를 scratch에서 실행해 동결한 oracle |
| `tests/fixtures/viseme-parity.json` | 동일 |

## E. 의도적 제외

| path | 근거 |
|---|---|
| `src/data/docentDevlog.ts` | closure에 없다. 유일 소비자 `src/features/playground/DocentDevlog.tsx`가 범위 밖 |
| `src/app/playground/page.tsx` | portfolio 전용 shell (SiteHeader · navigation · ReflexGame · DocentDevlog · 히어로 카피) |
| `src/app/docent/page.tsx` | `/playground` redirect stub. standalone에서 의미 없다 |
| `src/lib/knowledge.ts` | Scope 4 — corpus 스냅샷 생성에만 쓰고 파이프라인은 이관하지 않는다 |
| `src/data/about.ts` · `src/data/projects.ts` | Scope 5 — 전체 복사 대신 persona가 읽는 필드만 스냅샷 |
| `public/images/profile/*` | 실제 인물 사진. AC 24 |
| portfolio `globals.css` / Tailwind 설정 | portfolio shell scope. §Known Limitations 참조 |

---

## Dependency 근거 (AC 7)

| package | consumer | 이관에 필요한 이유 |
|---|---|---|
| `react` | AvatarCanvas · ChatPanel · DocentExperience · DocentHead · useDocentChat · useVoice | 모든 Docent UI가 React 훅·컴포넌트다 |
| `react-dom` | `next` / `react` 런타임 | React DOM 렌더러. closure walker는 direct import가 없어 못 잡았으나 canonical commit `package.json`에 선언돼 있고 Next 앱 구동에 필수다 — **Contract가 명시한 8개와의 차이이며 은폐하지 않는다** |
| `next` | DocentExperience(`next/dynamic`) · app shell | `ssr: false` dynamic import와 API route가 Next에 의존한다 |
| `three` | AvatarCanvas · DocentHead | 3D 씬·`ACESFilmicToneMapping`·`Group`/`Mesh`/`MathUtils` |
| `@react-three/fiber` | AvatarCanvas · DocentHead | `Canvas` · `useFrame` |
| `@react-three/drei` | DocentHead | `useGLTF`로 docent.glb 로드 |
| `framer-motion` | ChatPanel | 메시지 애니메이션 · `useReducedMotion` |
| `lucide-react` | ChatPanel | Mic · SendHorizontal · Volume2 · VolumeX 아이콘 |
| `@anthropic-ai/sdk` | `src/lib/docent/chat.ts` | Claude live 스트리밍 경로와 `RateLimitError` 분기 |

버전은 canonical commit의 **`package-lock.json`에 resolved 된 정확한 버전**으로 선언했다
(`latest` 미사용, 기회적 upgrade 없음). 설치 후 14/14가 source-lock과 일치함을 대조 확인했다.

```
react 19.2.6 · react-dom 19.2.6 · next 15.5.18 · three 0.185.1
@react-three/fiber 9.6.1 · @react-three/drei 10.7.7
framer-motion 12.40.0 · lucide-react 0.468.0 · @anthropic-ai/sdk 0.111.0
dev: @types/react 19.2.15 · @types/react-dom 19.2.3 · @types/three 0.185.1
     @types/node 22.19.19 · typescript 5.9.3
```

### 스타일 폐포 — 미해결 (FROZEN CONTRACT BLOCKER)

이관한 UI의 className은 전부 Tailwind 유틸리티다. 원본은 `tailwindcss` · `postcss` ·
`autoprefixer`와 루트의 `postcss.config.mjs` · `tailwind.config.ts`에 의존한다.
그 두 파일은 동결 Contract의 Expected Files 상한 밖이라 **작성하지 않았고 toolchain도
설치하지 않았다.** 현재 dev 서버 HTML에 stylesheet link가 0건이며, 캔버스 컨테이너의
`h-[42vh] min-h-[300px]`가 적용되지 않는다. Human 결정 대기 항목이다.

### 제외한 포트폴리오 의존성

`gsap` · `@gsap/react` · `lenis` · `recharts` · `@mdx-js/loader` · `@mdx-js/react` ·
`@next/mdx` · `eslint` · `eslint-config-next` — Docent closure와 무관하다.

---

## Persona field mapping (AC 20)

`src/data/about.ts` · `src/data/projects.ts` → `src/data/personaProfile.ts`

| source export | source field | standalone field | 건수 |
|---|---|---|---|
| `aboutProfile` | `label` · `value[]` | 동일 | 9 |
| `aboutIntroduction` | (문자열 전체) | 동일 | 270 chars |
| `aboutJourney` | `year` · `title` · `groups[].label` · `groups[].items[]` | 동일 | 6 |
| `projects` | `name` · `label` · `description` | 동일 | 3 |
| `aboutFocusAreas` | `title` · `description` · `technologies[]` | 동일 | 4 |
| `aboutToolbox` | `title` · `items[]` | 동일 | 6 |
| `aboutAwards` | `title` · `description` | 동일 | 2 |

**미이관 필드** — persona가 읽지 않는다: `aboutSnapshot` · `aboutExploration` ·
`aboutJourney.step` · `aboutFocusAreas.projects` · `projects`의 `key` · `headline` ·
`background` · `foreground` · `muted` · `core` · `sections` · `points` · `technologies`.

새로운 개인정보를 만들지 않았다. 값은 공개 포트폴리오에 이미 게시된 범위다.

---

## Retrieval boundary coverage matrix (T4)

fixture: `tests/fixtures/retrieval-parity.json` — 11 cases, 정상 질문 7 + 경계 4.

| branch | 조건 | 검증 fixture |
|---|---|---|
| B1 | `tokens.length === 0` → 빈 문자열 | `B1a` `"?"` · `B1b` `"a b c"` |
| B2 | 모든 note score `=== 0` → 빈 문자열 | `B2a` `"zzzzqqqq wwwwvvvv"` · `B2b` `"멀티에이전트"` |
| B3 | score > 0 인 note < 3 | `N1` `"RAG"`(1) · `N7` `"임베딩"`(1) · `N6` `"컴퓨터 비전"`(2) |
| B4 | `body.length > 1200` → truncate + ellipsis | `N2` `"MCP"` · `N3` `"voice AI"` · `N4` `"프롬프트 엔지니어링"` · `N5` `"agent architecture"` · `N6` `"컴퓨터 비전"` |

정상 질문 7건: `N1`~`N7`. oracle은 canonical commit의 원본 `retrieval.ts` + `knowledge.ts`를
scratch에서 그대로 실행해 만들었고, 대상 구현은 oracle 생성에 관여하지 않았다.

---

## Known limitations preserved (Baseline 증거)

고치지 않고 그대로 옮긴 것들이다. 개선은 Baseline 이후 별도 Task다.

- **`aboutProfile`은 "4 Major Projects"라고 하지만 `projects` 배열은 3건이다.** canonical
  commit의 stale fact. 그대로 보존했다.
- **retrieval은 lexical substring 매칭이다.** `"멀티에이전트"`가 `Multi-Agent` 노트를
  찾지 못한다(B2b가 그 증거). 한국어/영어 키워드 불일치는 알려진 한계다.
- **rate limiter는 in-memory Map이다.** 서버리스 인스턴스별로 분리되고 콜드스타트에 리셋된다.
- **corpus의 49/57이 `ai-news-*` 데일리 노트다.** 스코어링이 뉴스 노트에 쏠린다.
- **`docentCopy.subheading` 등 포트폴리오 문맥 문구를 그대로 유지했다.** standalone 제품
  문구로 다듬지 않았다 — 다듬으면 baseline이 오염된다.
