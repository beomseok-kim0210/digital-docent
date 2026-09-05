export type DocentEmotion =
  | "neutral"
  | "smile"
  | "thinking"
  | "surprised"
  | "sad";

// "talking"은 모델이 고르는 감정이 아니라 스트리밍 중 클라이언트가 구동하는 모프.
export const DOCENT_EMOTIONS: readonly DocentEmotion[] = [
  "neutral",
  "smile",
  "thinking",
  "surprised",
  "sad",
] as const;

export type DocentChatRole = "user" | "assistant";

export interface DocentChatMessage {
  role: DocentChatRole;
  content: string;
}

export type DocentMode = "live" | "fallback";

// NDJSON 와이어 프로토콜 — 한 줄에 JSON 하나
export type DocentStreamEvent =
  | { type: "meta"; emotion: DocentEmotion; mode: DocentMode }
  | { type: "delta"; text: string }
  | { type: "done" }
  | { type: "error"; message: string };

export function isDocentEmotion(value: unknown): value is DocentEmotion {
  return (
    typeof value === "string" &&
    (DOCENT_EMOTIONS as readonly string[]).includes(value)
  );
}
