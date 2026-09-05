// T6 fallback parity (AC 11 · 13).
//
// API 키가 없을 때 NDJSON 이벤트 시퀀스가 원본과 같은지 확인한다.
// handleDocentChat 은 A-1 어댑터로 추출한 framework-agnostic 핸들러이며,
// 검증 규칙 · 이벤트 형태와 순서 · 폴백 분기 조건은 원본과 동일하다.
// chat.ts 는 값 수준의 "@/" import 를 갖는다. npm test 명령을 AGENTS.md 가 정한
// `node --test` 그대로 두기 위해, 별칭 훅을 먼저 등록하고 동적 import 로 불러온다.
import assert from "node:assert/strict";
import { test } from "node:test";
import "./alias-hook.mjs";

const { handleDocentChat } = await import("../src/lib/docent/chat.ts");

type Event = { type: string; [key: string]: unknown };

async function ask(content: string): Promise<{ status: number; headers: Headers; events: Event[] }> {
  delete process.env.ANTHROPIC_API_KEY;
  const response = await handleDocentChat(
    new Request("http://localhost/api/docent/chat", {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-for": `10.0.0.${Math.floor(Math.random() * 200) + 1}` },
      body: JSON.stringify({ messages: [{ role: "user", content }] }),
    }),
  );
  const text = await response.text();
  const events = text.split("\n").filter(Boolean).map((line) => JSON.parse(line) as Event);
  return { status: response.status, headers: response.headers, events };
}

test("fallback emits meta -> delta... -> done as NDJSON", async () => {
  const { status, headers, events } = await ask("ARMI가 뭔가요?");
  assert.equal(status, 200);
  assert.equal(headers.get("content-type"), "application/x-ndjson; charset=utf-8");
  assert.equal(headers.get("cache-control"), "no-store");

  assert.equal(events[0]?.type, "meta");
  assert.equal(events[0]?.mode, "fallback");
  assert.equal(events.at(-1)?.type, "done");
  const middle = events.slice(1, -1);
  assert.ok(middle.length > 0, "at least one delta is expected");
  assert.ok(middle.every((e) => e.type === "delta" && typeof e.text === "string"));
});

test("fallback meta carries one of the five docent emotions", async () => {
  const { events } = await ask("어떤 프로젝트를 만들었나요?");
  assert.ok(["neutral", "smile", "thinking", "surprised", "sad"].includes(events[0]?.emotion as string));
});

test("concatenated deltas reconstruct the answer", async () => {
  const { events } = await ask("어떤 기술을 다루나요?");
  const answer = events.slice(1, -1).map((e) => e.text as string).join("");
  assert.ok(answer.length > 0);
});

test("an unmatched question still falls back to the default answer", async () => {
  const { events } = await ask("zzzzqqqq wwwwvvvv");
  assert.equal(events[0]?.type, "meta");
  assert.equal(events[0]?.mode, "fallback");
  assert.equal(events.at(-1)?.type, "done");
});

test("request validation rejects a malformed body", async () => {
  const response = await handleDocentChat(
    new Request("http://localhost/api/docent/chat", {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-for": "10.1.0.1" },
      body: JSON.stringify({ messages: [] }),
    }),
  );
  assert.equal(response.status, 400);
});
