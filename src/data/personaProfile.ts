// Persona profile snapshot — T-001 baseline migration.
//
// canonical source commit: b295c1cc20f117b18c7ef2d916ded6aec549f565
// source modules: src/data/about.ts · src/data/projects.ts
//
// persona.ts 가 실제로 읽는 필드만 담는다. 값과 의미는 canonical commit 과 동일하며
// 새로운 개인정보를 추가하지 않았다. field mapping 은 docs/migration-inventory.md 참조.

export const aboutProfile = [
  {
    "label": "Name",
    "value": [
      "Kim Beomseok"
    ]
  },
  {
    "label": "Role",
    "value": [
      "AI Product Engineer"
    ]
  },
  {
    "label": "Location",
    "value": [
      "Seoul, Korea"
    ]
  },
  {
    "label": "Education",
    "value": [
      "International Trade Major"
    ]
  },
  {
    "label": "Training",
    "value": [
      "Prompt Engineering Bootcamp",
      "SSAFY 14th"
    ]
  },
  {
    "label": "Interests",
    "value": [
      "AI Agents",
      "Computer Vision",
      "Generative AI",
      "Multi-Agent Systems"
    ]
  },
  {
    "label": "Current Focus",
    "value": [
      "MCP",
      "Voice AI",
      "AI Product Engineering"
    ]
  },
  {
    "label": "Projects",
    "value": [
      "4 Major Projects"
    ]
  },
  {
    "label": "Awards",
    "value": [
      "2 Awards"
    ]
  }
] as const;

export const aboutIntroduction =
  "I started from an International Trade background, then moved into AI through Prompt Engineering Bootcamp and SSAFY. Across Wedding AI, ARMI, Hangarae, and Claw Dev, I have focused on turning AI models into product decisions, realtime interfaces, and user-facing systems.";

export const aboutJourney = [
  {
    "year": "2023",
    "title": "Prompt Engineering Bootcamp",
    "groups": [
      {
        "label": "Core Skills",
        "items": [
          "Python",
          "Stable Diffusion",
          "RAG",
          "Prompt Engineering"
        ]
      },
      {
        "label": "Project",
        "items": [
          "Wedding AI"
        ]
      },
      {
        "label": "Achievement",
        "items": [
          "Best Project Award"
        ]
      }
    ]
  },
  {
    "year": "2024",
    "title": "Generative AI Grand Prize",
    "groups": [
      {
        "label": "Achievement",
        "items": [
          "Best Project Award"
        ]
      },
      {
        "label": "Focus",
        "items": [
          "Generative AI",
          "Prompt-based Product Design"
        ]
      }
    ]
  },
  {
    "year": "2025",
    "title": "SSAFY",
    "groups": [
      {
        "label": "Core Skills",
        "items": [
          "Python",
          "Algorithms",
          "Django",
          "Vue"
        ]
      },
      {
        "label": "Projects",
        "items": [
          "ARMI",
          "Hangarae"
        ]
      }
    ]
  },
  {
    "year": "2026",
    "title": "ARMI",
    "groups": [
      {
        "label": "Core Skills",
        "items": [
          "Voice AI",
          "STT/TTS",
          "State Machine",
          "WebSocket",
          "Real-time Systems"
        ]
      },
      {
        "label": "Achievement",
        "items": [
          "SSAFY Common Project Winner"
        ]
      }
    ]
  },
  {
    "year": "2026",
    "title": "Hangarae",
    "groups": [
      {
        "label": "Core Skills",
        "items": [
          "YOLO",
          "Pose Estimation",
          "Redis",
          "Three.js",
          "AIoT"
        ]
      },
      {
        "label": "Metrics",
        "items": [
          "18 Keypoints",
          "54 Values / Frame",
          "200+ Threshold Tests"
        ]
      }
    ]
  },
  {
    "year": "Present",
    "title": "Claw Dev",
    "groups": [
      {
        "label": "Core Skills",
        "items": [
          "MCP",
          "Claude Code",
          "Multi-Agent",
          "Tool Calling"
        ]
      },
      {
        "label": "Metrics",
        "items": [
          "5 Role-Based Agents"
        ]
      }
    ]
  }
] as const;

export const projects = [
  {
    "name": "ARMI",
    "label": "Healthcare AI",
    "description": "환자의 음성 요청을 AI Agent가 해석하고, 로봇 미션과 간호사 호출, 의료진 알림까지 하나의 흐름으로 연결했습니다."
  },
  {
    "name": "행가래",
    "label": "Rehabilitation AI",
    "description": "기술은 사용자의 움직임 하나를 바꾸기 위해 존재합니다."
  },
  {
    "name": "Wedding Dress AI",
    "label": "Choice Intelligence",
    "description": "웨딩드레스 선택 문제는 취향 부족이 아니라 비용과 비교 기회의 구조적 제약이었습니다."
  }
] as const;

export const aboutFocusAreas = [
  {
    "title": "AI Agents",
    "description": "AI가 단순 응답을 넘어 행동을 수행하는 시스템 설계",
    "technologies": [
      "Qwen",
      "MCP",
      "WebSocket",
      "STT/TTS"
    ]
  },
  {
    "title": "Computer Vision",
    "description": "사용자의 움직임을 실시간 데이터로 변환",
    "technologies": [
      "YOLO",
      "Depth Camera",
      "Redis"
    ]
  },
  {
    "title": "Generative AI",
    "description": "모델 활용이 아닌 검증과 평가 중심 접근",
    "technologies": [
      "Stable Diffusion",
      "RAG",
      "Prompt Engineering"
    ]
  },
  {
    "title": "Product Engineering",
    "description": "사용자 경험 중심 AI 서비스 구현",
    "technologies": [
      "Flutter",
      "React",
      "Django"
    ]
  }
] as const;

export const aboutToolbox = [
  {
    "title": "AI",
    "items": [
      "GPT",
      "Claude",
      "Qwen"
    ]
  },
  {
    "title": "Agent",
    "items": [
      "MCP",
      "RAG",
      "Tool Calling"
    ]
  },
  {
    "title": "Frontend",
    "items": [
      "React",
      "Flutter",
      "Three.js"
    ]
  },
  {
    "title": "Backend",
    "items": [
      "Spring",
      "Django",
      "Redis"
    ]
  },
  {
    "title": "Computer Vision",
    "items": [
      "YOLO",
      "OpenCV",
      "Depth Camera"
    ]
  },
  {
    "title": "Infra",
    "items": [
      "GitHub",
      "Vercel",
      "Cloudinary"
    ]
  }
] as const;

export const aboutAwards = [
  {
    "title": "Generative AI Grand Prize",
    "description": "Prompt Engineering Bootcamp project recognition"
  },
  {
    "title": "SSAFY Common Project 1st",
    "description": "ARMI voice AI and realtime care workflow project"
  }
] as const;
