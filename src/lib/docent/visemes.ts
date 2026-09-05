/** 립싱크용 입모양 종류. GLB의 viseme_* 모프타겟 이름과 대응한다. */
export type VisemeKey = "a" | "i" | "u" | "e" | "o" | "m";

export interface VisemeFrame {
  /** 이 입모양이 시작되는 문자 위치 */
  charIndex: number;
  viseme: VisemeKey;
}

export interface VisemeTimeline {
  frames: VisemeFrame[];
  textLength: number;
}

const HANGUL_BASE = 0xac00;
const HANGUL_LAST = 0xd7a3;

// 중성(모음) 21개 → 입모양. 이중모음은 끝소리 기준으로 근사한다.
const JUNGSEONG_VISEME: VisemeKey[] = [
  "a", // ㅏ
  "e", // ㅐ
  "a", // ㅑ
  "e", // ㅒ
  "e", // ㅓ
  "e", // ㅔ
  "e", // ㅕ
  "e", // ㅖ
  "o", // ㅗ
  "a", // ㅘ
  "e", // ㅙ
  "e", // ㅚ
  "o", // ㅛ
  "u", // ㅜ
  "e", // ㅝ
  "e", // ㅞ
  "i", // ㅟ
  "u", // ㅠ
  "u", // ㅡ
  "i", // ㅢ
  "i", // ㅣ
];

// 초성 중 입을 다물어야 하는 자음 (ㅁ ㅂ ㅃ ㅍ)
const CLOSED_CHOSEONG = new Set([6, 7, 8, 17]);
// 종성 중 입을 다물고 끝나는 자음 (ㅁ ㅂ ㅄ ㅍ)
const CLOSED_JONGSEONG = new Set([16, 17, 18, 25]);

// 영어 모음 근사
const LATIN_VISEME: Record<string, VisemeKey> = {
  a: "a",
  e: "e",
  i: "i",
  o: "o",
  u: "u",
  y: "i",
};
const LATIN_CLOSED = new Set(["m", "b", "p"]);

/**
 * 텍스트를 입모양 시퀀스로 변환한다.
 * 한글은 자모를 분해해 중성(모음)을 입모양으로, ㅁ/ㅂ/ㅍ 계열은 다문 입으로
 * 매핑한다. 영어는 모음 글자를 대략적으로 매핑한다.
 */
export function textToVisemeTimeline(text: string): VisemeTimeline {
  const frames: VisemeFrame[] = [];
  let previous: VisemeKey | null = null;

  const push = (charIndex: number, viseme: VisemeKey) => {
    // 같은 입모양이 연달아 나오면 프레임을 늘리지 않는다
    if (viseme === previous) return;
    frames.push({ charIndex, viseme });
    previous = viseme;
  };

  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);

    if (code >= HANGUL_BASE && code <= HANGUL_LAST) {
      const offset = code - HANGUL_BASE;
      const choseong = Math.floor(offset / 588);
      const jungseong = Math.floor((offset % 588) / 28);
      const jongseong = offset % 28;

      if (CLOSED_CHOSEONG.has(choseong)) push(i, "m");
      push(i, JUNGSEONG_VISEME[jungseong] ?? "a");
      if (CLOSED_JONGSEONG.has(jongseong)) push(i, "m");
      continue;
    }

    const lower = text[i].toLowerCase();
    if (LATIN_CLOSED.has(lower)) {
      push(i, "m");
    } else if (LATIN_VISEME[lower]) {
      push(i, LATIN_VISEME[lower]);
    }
    // 그 외(자음·공백·문장부호)는 직전 입모양을 유지 — 과하게 펄럭이지 않게
  }

  return { frames, textLength: text.length };
}

/** 주어진 문자 위치에서 활성인 입모양을 찾는다 (이진 탐색). */
export function visemeAt(
  timeline: VisemeTimeline,
  charIndex: number
): VisemeKey | null {
  const { frames } = timeline;
  if (frames.length === 0) return null;
  if (charIndex < frames[0].charIndex) return null;

  let low = 0;
  let high = frames.length - 1;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    if (frames[mid].charIndex <= charIndex) low = mid;
    else high = mid - 1;
  }
  return frames[low].viseme;
}

/** 한국어는 음절당, 영어는 글자당 속도가 달라 대략적인 기본값을 나눠 둔다. */
export function estimateCharsPerSecond(text: string, rate: number): number {
  const hangulCount = (text.match(/[가-힣]/g) ?? []).length;
  const isKoreanDominant = hangulCount > text.length * 0.3;
  const base = isKoreanDominant ? 7 : 14;
  return base * rate;
}
