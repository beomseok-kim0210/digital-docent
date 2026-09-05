export const docentStarterQuestions = [
  "어떤 프로젝트를 만들었나요?",
  "ARMI가 뭔가요?",
  "어떤 기술을 다루나요?",
  "Tell me about yourself",
] as const;

export const docentCopy = {
  label: "AI Docent",
  heading: "포트폴리오에게\n직접 물어보세요",
  subheading:
    "Google GNM 파라메트릭 헤드 모델과 Claude API로 만든 3D 도슨트입니다. 김범석의 프로젝트, 기술, 여정에 대해 무엇이든 물어보세요.",
  inputPlaceholder: "궁금한 것을 물어보세요…",
  listeningPlaceholder: "듣고 있어요… 말씀해 주세요",
  demoBadge: "데모 모드",
  demoNotice: "지금은 사전 준비된 답변으로 동작하는 데모 모드입니다.",
  errorBubble: "죄송해요, 답변 중에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
} as const;

export const docentConfig = {
  maxInputLength: 500,
  maxHistoryMessages: 8,
  model: process.env.DOCENT_MODEL ?? "claude-haiku-4-5",
  maxTokens: 1024,
  rateLimit: { windowMs: 60_000, maxRequests: 10 },
} as const;
