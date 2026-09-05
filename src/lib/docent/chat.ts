import Anthropic from "@anthropic-ai/sdk";
import { docentConfig } from "@/data/docent";
import { matchFallback } from "@/lib/docent/fallback";
import { buildSystemPrompt } from "@/lib/docent/persona";
import { checkRateLimit, clientIpFrom } from "@/lib/docent/rateLimit";
import {
  isDocentEmotion,
  type DocentChatMessage,
  type DocentEmotion,
  type DocentStreamEvent,
} from "@/types/docent";

// A-1 framework adapter (T-001). 원본은 Next.js route 파일이었다. 핸들러 로직을
// 여기(framework-agnostic)로 옮기고 Next 어댑터는 src/app/api/docent/chat/route.ts 에
// 얇게 남겼다. 아래 검증 규칙 · 이벤트 형태와 순서 · 감정 태그 파싱 · 폴백 분기 ·
// 에러 문면 · 응답 헤더는 원본과 동일하다.

const NDJSON_HEADERS = {
  "Content-Type": "application/x-ndjson; charset=utf-8",
  "Cache-Control": "no-store",
} as const;

function line(event: DocentStreamEvent): string {
  return `${JSON.stringify(event)}\n`;
}

function validate(body: unknown): { messages: DocentChatMessage[] } | { error: string } {
  if (!body || typeof body !== "object" || !Array.isArray((body as { messages?: unknown }).messages)) {
    return { error: "messages 배열이 필요합니다." };
  }
  const raw = (body as { messages: unknown[] }).messages;
  if (raw.length === 0 || raw.length > 12) {
    return { error: "메시지는 1~12개여야 합니다." };
  }
  const messages: DocentChatMessage[] = [];
  for (const m of raw) {
    const msg = m as Partial<DocentChatMessage>;
    if (
      (msg.role !== "user" && msg.role !== "assistant") ||
      typeof msg.content !== "string" ||
      msg.content.length === 0 ||
      msg.content.length > 1000
    ) {
      return { error: "메시지 형식이 올바르지 않습니다." };
    }
    messages.push({ role: msg.role, content: msg.content });
  }
  if (messages[messages.length - 1].role !== "user") {
    return { error: "마지막 메시지는 user여야 합니다." };
  }
  return { messages: messages.slice(-docentConfig.maxHistoryMessages) };
}

/** 폴백 모드: 캔드 답변을 동일한 NDJSON 형태로 반환. */
function fallbackResponse(question: string): Response {
  const { emotion, answer } = matchFallback(question);
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(line({ type: "meta", emotion, mode: "fallback" })));
      // 단어 단위로 몇 조각 내보내 라이브와 같은 스트림 소비 경로를 태운다.
      const words = answer.split(" ");
      const chunkSize = Math.max(1, Math.ceil(words.length / 6));
      for (let i = 0; i < words.length; i += chunkSize) {
        const text = (i === 0 ? "" : " ") + words.slice(i, i + chunkSize).join(" ");
        controller.enqueue(encoder.encode(line({ type: "delta", text })));
      }
      controller.enqueue(encoder.encode(line({ type: "done" })));
      controller.close();
    },
  });
  return new Response(stream, { headers: NDJSON_HEADERS });
}

/** 라이브 모드: Claude 스트리밍 + 감정 태그 파싱. */
function liveResponse(messages: DocentChatMessage[]): Response {
  const client = new Anthropic();
  const question = messages[messages.length - 1].content;
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: DocentStreamEvent) =>
        controller.enqueue(encoder.encode(line(event)));

      try {
        const anthropicStream = client.messages.stream({
          model: docentConfig.model,
          max_tokens: docentConfig.maxTokens,
          system: buildSystemPrompt(question),
          messages,
        });

        // 답변 앞의 <emotion>...</emotion> 태그를 버퍼링해 파싱·제거한다.
        // 64자까지 태그가 안 닫히면 neutral로 간주하고 버퍼를 그대로 방출.
        let buffer = "";
        let metaSent = false;

        const flushMeta = (emotion: DocentEmotion, rest: string) => {
          send({ type: "meta", emotion, mode: "live" });
          metaSent = true;
          if (rest) send({ type: "delta", text: rest });
        };

        for await (const event of anthropicStream) {
          if (event.type !== "content_block_delta" || event.delta.type !== "text_delta") {
            continue;
          }
          if (metaSent) {
            send({ type: "delta", text: event.delta.text });
            continue;
          }
          buffer += event.delta.text;
          const match = buffer.match(/^\s*<emotion>\s*(\w+)\s*<\/emotion>\s*/);
          if (match) {
            const emotion = isDocentEmotion(match[1]) ? match[1] : "neutral";
            flushMeta(emotion, buffer.slice(match[0].length));
          } else if (buffer.length > 64) {
            flushMeta("neutral", buffer);
          }
        }

        // 태그도 64자도 못 채우고 끝난 짧은 응답 처리.
        if (!metaSent) flushMeta("neutral", buffer);
        send({ type: "done" });
      } catch (err) {
        // 스트리밍 시작 후에는 상태코드를 바꿀 수 없으므로 error 이벤트로 전달.
        const message =
          err instanceof Anthropic.RateLimitError
            ? "지금 질문이 많아요. 잠시 후 다시 시도해 주세요."
            : "답변 생성 중 문제가 생겼어요.";
        send({ type: "error", message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, { headers: NDJSON_HEADERS });
}

export async function handleDocentChat(request: Request): Promise<Response> {
  const rate = checkRateLimit(clientIpFrom(request.headers));
  if (!rate.ok) {
    return Response.json(
      { error: "요청이 너무 잦아요. 잠시 후 다시 시도해 주세요." },
      { status: 429, headers: { "Retry-After": String(rate.retryAfterSec ?? 30) } }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "잘못된 JSON입니다." }, { status: 400 });
  }

  const parsed = validate(body);
  if ("error" in parsed) {
    return Response.json({ error: parsed.error }, { status: 400 });
  }

  // 키가 없으면 폴백 모드 — 요청마다 체크하므로 키 추가만으로 라이브 전환.
  if (!process.env.ANTHROPIC_API_KEY) {
    return fallbackResponse(parsed.messages[parsed.messages.length - 1].content);
  }

  return liveResponse(parsed.messages);
}
