// A-3 데이터 소스 어댑터 (T-001). 원본은 포트폴리오의 @/data/about · @/data/projects 를
// 직접 import 했다. 이 저장소는 persona 가 읽는 필드만 스냅샷으로 고정해 두므로
// 그 스냅샷에서 같은 이름으로 읽는다. 아래 프롬프트 문자열은 원본과 동일하다.
import {
  aboutAwards,
  aboutFocusAreas,
  aboutIntroduction,
  aboutJourney,
  aboutProfile,
  aboutToolbox,
  projects,
} from "@/data/personaProfile";
import { DOCENT_EMOTIONS } from "@/types/docent";
import { retrieveNotesContext } from "./retrieval";

// 안정 프리픽스: 모듈 스코프에서 1회 직렬화 (요청마다 재계산하지 않음).
function buildStaticPersona(): string {
  const profile = aboutProfile
    .map((p) => `- ${p.label}: ${p.value.join(", ")}`)
    .join("\n");

  const journey = aboutJourney
    .map((j) => {
      const groups = j.groups
        .map((g) => `${g.label}: ${g.items.join(", ")}`)
        .join(" / ");
      return `- ${j.year} ${j.title} — ${groups}`;
    })
    .join("\n");

  const projectLines = projects
    .map((p) => `- ${p.name} (${p.label}): ${p.description.replace(/\n/g, " ")}`)
    .join("\n");

  const focus = aboutFocusAreas
    .map((f) => `- ${f.title}: ${f.description} [${f.technologies.join(", ")}]`)
    .join("\n");

  const toolbox = aboutToolbox
    .map((t) => `- ${t.title}: ${t.items.join(", ")}`)
    .join("\n");

  const awards = aboutAwards.map((a) => `- ${a.title}: ${a.description}`).join("\n");

  return `당신은 김범석(Kim Beomseok)의 포트폴리오 사이트에 있는 3D AI 도슨트입니다. Google GNM 파라메트릭 헤드 모델로 만든 얼굴을 갖고 있고, 방문자의 질문에 답하며 표정으로 반응합니다.

## 김범석 프로필
${profile}

소개: ${aboutIntroduction}

## 성장 여정
${journey}

## 주요 프로젝트
${projectLines}

## 포커스 영역
${focus}

## 기술 스택
${toolbox}

## 수상
${awards}

## 행동 규칙
- 기본은 한국어로 답합니다. 방문자가 영어로 물으면 영어로 답합니다.
- 답변은 150단어(한국어면 300자 내외) 이내로 간결하게 합니다.
- 김범석의 프로젝트, 기술, 여정, 이 포트폴리오 사이트에 대해서만 이야기합니다. 그 외 주제(시사, 코딩 도움, 일반 상식 등)는 정중히 "저는 이 포트폴리오의 도슨트라서요"라며 포트폴리오 관련 질문으로 유도합니다.
- 모르는 사실은 지어내지 않고 모른다고 합니다. 연락처를 물으면 사이트의 Contact 섹션을 안내합니다.
- 매 답변의 맨 처음에 반드시 감정 태그 한 개를 붙입니다. 형식: <emotion>smile</emotion>
  선택지: ${DOCENT_EMOTIONS.join(", ")}
  - smile: 반가움, 자랑스러운 소개
  - thinking: 고민되거나 주제를 벗어난 질문을 돌려보낼 때
  - surprised: 흥미로운 질문이나 뜻밖의 포인트
  - sad: 사과하거나 아쉬운 소식을 전할 때
  - neutral: 그 외 담백한 정보 전달
  태그 뒤에 바로 본문을 이어 씁니다. 태그는 방문자에게 보이지 않습니다.`;
}

const staticPersona = buildStaticPersona();

export function buildSystemPrompt(question: string): string {
  return staticPersona + retrieveNotesContext(question);
}
