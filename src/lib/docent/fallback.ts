import {
  docentFallbackDefault,
  docentFallbackEntries,
} from "@/data/docentFallback";
import type { DocentEmotion } from "@/types/docent";

export interface FallbackMatch {
  emotion: DocentEmotion;
  answer: string;
}

/** 알파벳 비율이 높고 한글이 없으면 영어 질문으로 판단. */
export function isEnglishQuestion(question: string): boolean {
  if (/[가-힣]/.test(question)) return false;
  const letters = question.replace(/[^a-zA-Z]/g, "").length;
  const meaningful = question.replace(/[\s\d\p{P}]/gu, "").length;
  return meaningful > 0 && letters / meaningful > 0.6;
}

/** 키워드 히트 수가 가장 많은 캔드 답변을 고른다. 히트 0이면 기본 응답. */
export function matchFallback(question: string): FallbackMatch {
  const q = question.toLowerCase();
  const english = isEnglishQuestion(question);

  let best: { hits: number; entry: (typeof docentFallbackEntries)[number] } | null =
    null;
  for (const entry of docentFallbackEntries) {
    const hits = entry.keywords.reduce(
      (acc, kw) => acc + (q.includes(kw.toLowerCase()) ? 1 : 0),
      0
    );
    if (hits > 0 && (!best || hits > best.hits)) {
      best = { hits, entry };
    }
  }

  if (!best) {
    return {
      emotion: docentFallbackDefault.emotion,
      answer:
        english && docentFallbackDefault.answerEn
          ? docentFallbackDefault.answerEn
          : docentFallbackDefault.answer,
    };
  }

  const { entry } = best;
  return {
    emotion: entry.emotion,
    answer: english && entry.answerEn ? entry.answerEn : entry.answer,
  };
}
