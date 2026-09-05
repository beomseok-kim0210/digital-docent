import type { DocentEmotion } from "@/types/docent";

export interface DocentFallbackEntry {
  keywords: string[];
  emotion: DocentEmotion;
  answer: string;
  answerEn?: string;
}

export const docentFallbackEntries: DocentFallbackEntry[] = [
  {
    keywords: ["누구", "소개", "자기소개", "who", "yourself", "introduce", "about you", "범석"],
    emotion: "smile",
    answer:
      "안녕하세요! 저는 김범석의 포트폴리오를 안내하는 AI 도슨트예요. 범석 님은 국제통상 전공에서 출발해 프롬프트 엔지니어링 부트캠프와 SSAFY를 거쳐 AI 프로덕트 엔지니어가 됐어요. Wedding AI, ARMI, 행가래, Claw Dev 네 개의 프로젝트를 만들며 AI 모델을 실제 제품과 사용자 경험으로 연결하는 일에 집중하고 있습니다.",
    answerEn:
      "Hi! I'm the AI docent for Beomseok Kim's portfolio. Beomseok started in International Trade, then moved into AI through a Prompt Engineering Bootcamp and SSAFY. Across Wedding AI, ARMI, Hangarae, and Claw Dev, he focuses on turning AI models into real products and user experiences.",
  },
  {
    keywords: ["프로젝트", "만들었", "작품", "projects", "built", "portfolio", "works"],
    emotion: "smile",
    answer:
      "네 가지 주요 프로젝트가 있어요. 병실 음성 AI 에이전트 ARMI(SSAFY 공통 프로젝트 1위), 재활 운동을 게임처럼 만든 컴퓨터 비전 프로젝트 행가래, 생성형 AI로 웨딩드레스 선택을 돕는 Wedding AI(생성형 AI 대상), 그리고 MCP 기반 멀티에이전트 개발 도구 Claw Dev입니다. 어떤 프로젝트가 궁금하세요?",
    answerEn:
      "There are four major projects: ARMI, a voice AI agent for hospital rooms (1st place, SSAFY common project); Hangarae, a computer-vision rehab game; Wedding AI, a generative-AI dress recommendation project (Grand Prize); and Claw Dev, an MCP-based multi-agent dev tool. Which one would you like to hear about?",
  },
  {
    keywords: ["armi", "아르미", "병실", "간호", "음성", "voice", "healthcare", "hospital"],
    emotion: "smile",
    answer:
      "ARMI는 병실에서 환자의 음성 요청을 AI 에이전트가 해석해 로봇 미션, 간호사 호출, 의료진 알림까지 하나의 흐름으로 연결한 헬스케어 AI예요. STT·웨이크워드·화자 검증·TTS가 마이크 상태를 공유하는 음성 파이프라인을 설계했고, gRPC와 WebSocket으로 로봇 상태를 실시간 전달했어요. SSAFY 공통 프로젝트 1위를 수상했습니다.",
    answerEn:
      "ARMI is a healthcare AI where a voice agent interprets patient requests in hospital rooms and connects robot missions, nurse calls, and staff notifications into one flow. It won 1st place in the SSAFY common project.",
  },
  {
    keywords: ["행가래", "hangarae", "재활", "운동", "요로", "비전", "yolo", "rehab", "pose"],
    emotion: "smile",
    answer:
      "행가래는 재활 운동을 게임처럼 바꾼 프로젝트예요. YOLO 포즈 추정으로 18개 키포인트를 실시간 추적하고, 200회 이상의 임계값 튜닝으로 Precision을 0.447에서 0.982까지 끌어올렸어요. 프론트엔드 리드로서 Three.js 3D 씬과 노년층 UX까지 함께 설계했습니다.",
    answerEn:
      "Hangarae turns rehab exercises into a game. It tracks 18 keypoints in real time with YOLO pose estimation; over 200 threshold-tuning runs raised precision from 0.447 to 0.982. Beomseok led the frontend, including the Three.js 3D scene and elderly-friendly UX.",
  },
  {
    keywords: ["wedding", "웨딩", "드레스", "dress", "생성형", "stable diffusion"],
    emotion: "smile",
    answer:
      "Wedding AI는 생성형 AI로 웨딩드레스 선택을 돕는 프로젝트예요. Stable Diffusion과 RAG, 프롬프트 엔지니어링을 활용했고, 모델을 단순히 쓰는 것을 넘어 검증과 평가 중심으로 접근한 점이 특징이에요. 프롬프트 엔지니어링 부트캠프에서 최우수 프로젝트로 선정됐고 생성형 AI 대상을 받았습니다.",
    answerEn:
      "Wedding AI helps brides choose dresses using generative AI — Stable Diffusion, RAG, and prompt engineering, with a focus on validation and evaluation. It won the bootcamp's best project award and a Generative AI Grand Prize.",
  },
  {
    keywords: ["claw", "클로", "mcp", "멀티에이전트", "multi-agent", "agent", "에이전트"],
    emotion: "smile",
    answer:
      "Claw Dev는 MCP와 Claude Code 기반의 멀티에이전트 개발 도구 프로젝트예요. 역할이 나뉜 5개의 에이전트가 협업하는 구조를 설계했고, 툴 콜링과 에이전트 오케스트레이션을 실험하고 있어요. 지금도 진행 중인 프로젝트입니다.",
    answerEn:
      "Claw Dev is an ongoing multi-agent dev tool project built on MCP and Claude Code, with five role-based agents collaborating through tool calling and orchestration.",
  },
  {
    keywords: ["기술", "스택", "스킬", "skills", "tech", "stack", "다루"],
    emotion: "neutral",
    answer:
      "핵심 스택은 이렇습니다 — AI: GPT·Claude·Qwen, 에이전트: MCP·RAG·툴 콜링, 컴퓨터 비전: YOLO·OpenCV·뎁스 카메라, 프론트엔드: React·Flutter·Three.js, 백엔드: Spring·Django·Redis. 특히 음성 AI와 실시간 시스템, AI 에이전트 설계에 강점이 있어요.",
    answerEn:
      "Core stack — AI: GPT, Claude, Qwen; Agents: MCP, RAG, tool calling; Computer vision: YOLO, OpenCV, depth cameras; Frontend: React, Flutter, Three.js; Backend: Spring, Django, Redis. Strengths in voice AI, realtime systems, and agent design.",
  },
  {
    keywords: ["수상", "상", "award", "prize", "우승", "1위", "1등"],
    emotion: "smile",
    answer:
      "두 개의 수상 경력이 있어요. 프롬프트 엔지니어링 부트캠프의 Wedding AI로 생성형 AI 대상을 받았고, 음성 AI 프로젝트 ARMI로 SSAFY 공통 프로젝트 1위를 차지했습니다.",
    answerEn:
      "Two awards: the Generative AI Grand Prize for Wedding AI, and 1st place in the SSAFY common project for ARMI.",
  },
  {
    keywords: ["ssafy", "싸피", "교육", "부트캠프", "bootcamp", "전공", "배경", "background", "여정"],
    emotion: "neutral",
    answer:
      "범석 님은 국제통상 전공 출신이에요. 2023년 프롬프트 엔지니어링 부트캠프에서 Python, Stable Diffusion, RAG를 익히며 Wedding AI를 만들었고, 이후 SSAFY 14기에서 알고리즘, Django, Vue를 다지며 ARMI와 행가래를 만들었어요. 비전공자에서 출발해 AI 프로덕트 엔지니어로 성장한 여정 자체가 강점입니다.",
    answerEn:
      "Beomseok majored in International Trade, learned Python, Stable Diffusion, and RAG at a Prompt Engineering Bootcamp in 2023 (building Wedding AI), then sharpened algorithms, Django, and Vue at SSAFY, where he built ARMI and Hangarae.",
  },
  {
    keywords: ["연락", "이메일", "컨택", "contact", "email", "채용", "hire", "협업"],
    emotion: "smile",
    answer:
      "협업이나 채용 관련 연락은 이 사이트의 Contact 섹션을 통해 남겨 주세요. 포트폴리오 하단에서 연락처와 링크를 확인할 수 있습니다.",
    answerEn:
      "For collaboration or hiring inquiries, please use the Contact section at the bottom of this site.",
  },
  {
    keywords: ["아바타", "avatar", "얼굴", "3d", "도슨트", "docent", "gnm", "이 사이트", "어떻게 만들"],
    emotion: "surprised",
    answer:
      "저는 Google이 오픈소스로 공개한 파라메트릭 3D 헤드 모델 GNM으로 만들어졌어요! Python으로 identity와 표정 파라미터를 조절해 얼굴과 6가지 표정 모프타겟을 생성했고, React Three Fiber로 렌더링됩니다. 답변은 Claude API가 만들고, 감정 태그에 따라 제 표정이 바뀌어요. AI 뉴스를 읽고 실제로 만들어본 프로젝트랍니다.",
    answerEn:
      "I'm built with GNM, Google's open-source parametric 3D head model! Python scripts generated my face and six expression morph targets, rendered with React Three Fiber. My answers come from the Claude API, and emotion tags drive my facial expressions.",
  },
  {
    keywords: ["관심", "요즘", "최근", "interest", "focus", "공부", "learning"],
    emotion: "thinking",
    answer:
      "요즘은 MCP, 음성 AI, AI 프로덕트 엔지니어링에 집중하고 있어요. 멀티에이전트 시스템을 만들면서 매일 AI 뉴스를 지식 베이스로 정리하는 자동화 파이프라인도 운영 중입니다. 이 사이트의 Knowledge 섹션에서 확인할 수 있어요.",
    answerEn:
      "Currently focused on MCP, voice AI, and AI product engineering. He also runs a daily automated pipeline that curates AI news into the Knowledge section of this site.",
  },
  {
    keywords: ["지식", "뉴스", "knowledge", "노트", "블로그", "정리"],
    emotion: "neutral",
    answer:
      "이 사이트의 Knowledge 섹션에는 RAG, MCP, 멀티에이전트, 음성 AI 같은 주제 노트와 함께, 매일 자동으로 수집·교차검증해 정리하는 AI 뉴스 노트가 쌓이고 있어요. Claude 기반 자동화 파이프라인이 매일 실행됩니다.",
    answerEn:
      "The Knowledge section holds topic notes (RAG, MCP, multi-agent, voice AI) plus daily AI news notes collected and cross-checked automatically by a Claude-based pipeline.",
  },
];

export const docentFallbackDefault = {
  emotion: "thinking" as DocentEmotion,
  answer:
    "음, 그 질문에 딱 맞는 준비된 답이 없네요. 김범석의 프로젝트(ARMI, 행가래, Wedding AI, Claw Dev), 기술 스택, 수상 경력, 성장 여정에 대해 물어봐 주시면 자세히 알려드릴 수 있어요!",
  answerEn:
    "Hmm, I don't have a prepared answer for that. Try asking about Beomseok's projects (ARMI, Hangarae, Wedding AI, Claw Dev), tech stack, awards, or journey!",
};
