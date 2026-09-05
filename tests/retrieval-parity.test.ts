// T3 retrieval parity (AC 14 · 17) + T4 boundary coverage.
//
// 비교 대상은 slug 추정이 아니라 retrieveNotesContext(question) 의 반환 문자열
// EXACT MATCH 다. ranking · Top-3 · 동점 순서 · title · summary · body ·
// 1200자 truncate · ellipsis · 구분자 · 헤더 문면이 한 번에 검증된다.
//
// fixture 는 migration 구현 전에 canonical source commit 의 원본 코드를
// scratch 에서 실행해 동결했다. 원본 저장소에는 아무것도 쓰지 않았다.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { retrieveNotesContext } from "../src/lib/docent/retrieval.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

type Fixture = {
  canonicalSourceCommit: string;
  corpusNoteCount: number;
  corpusOrder: string[];
  cases: {
    id: string;
    question: string;
    branches: string[];
    observed: { empty: boolean; noteCount: number; ellipsis: boolean; length: number };
    expected: string;
  }[];
};

const fixture = JSON.parse(
  readFileSync(path.join(root, "tests", "fixtures", "retrieval-parity.json"), "utf8"),
) as Fixture;

test("fixture is pinned to the canonical source commit", () => {
  assert.equal(fixture.canonicalSourceCommit, "b295c1cc20f117b18c7ef2d916ded6aec549f565");
  assert.ok(fixture.cases.length >= 5, "at least five fixed questions are required");
});

for (const item of fixture.cases) {
  test(`retrieval parity ${item.id} — ${JSON.stringify(item.question)}`, () => {
    const actual = retrieveNotesContext(item.question);
    assert.equal(actual, item.expected);
  });
}

// T4 — 네 개 경계 분기가 실제로 fixture 에 덮여 있는지 단언한다.
// 커버리지를 주장만 하지 않고 fixture 관측값으로 증명한다.
test("boundary B1 — tokens.length === 0 yields an empty string", () => {
  const b1 = fixture.cases.filter((c) => c.branches.includes("B1"));
  assert.ok(b1.length > 0, "B1 must be covered");
  for (const c of b1) {
    assert.equal(retrieveNotesContext(c.question), "");
  }
});

test("boundary B2 — every note scores zero yields an empty string", () => {
  const b2 = fixture.cases.filter((c) => c.branches.includes("B2"));
  assert.ok(b2.length > 0, "B2 must be covered");
  for (const c of b2) {
    assert.equal(retrieveNotesContext(c.question), "");
  }
});

test("boundary B3 — fewer than three scoring notes returns that many", () => {
  const b3 = fixture.cases.filter((c) => c.branches.includes("B3"));
  assert.ok(b3.length > 0, "B3 must be covered");
  for (const c of b3) {
    const noteCount = (retrieveNotesContext(c.question).match(/^요약: /gm) ?? []).length;
    assert.ok(noteCount > 0 && noteCount < 3, `${c.id} expected 1..2 notes, got ${noteCount}`);
  }
});

test("boundary B4 — a body over 1200 characters is truncated with an ellipsis", () => {
  const b4 = fixture.cases.filter((c) => c.branches.includes("B4"));
  assert.ok(b4.length > 0, "B4 must be covered");
  for (const c of b4) {
    assert.ok(retrieveNotesContext(c.question).includes("…"), `${c.id} expected an ellipsis`);
  }
});

test("Top-3 is never exceeded", () => {
  for (const item of fixture.cases) {
    const noteCount = (item.expected.match(/^요약: /gm) ?? []).length;
    assert.ok(noteCount <= 3, `${item.id} returned ${noteCount} notes`);
  }
});
