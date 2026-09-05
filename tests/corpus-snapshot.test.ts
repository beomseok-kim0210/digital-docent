// T5 corpus snapshot (AC 15 · 16).
//
// 스냅샷은 canonical source commit 의 getKnowledgeNotes() 결과 전체이고,
// 배열 순서가 원본 반환 순서와 원소 단위로 같아야 한다. retrieval 의 정렬은
// stable sort 이므로 동점 노트의 상대 순서가 곧 corpus 배열 순서이고,
// 그것이 Top-3 구성을 바꾼다.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

type Note = {
  slug: string;
  title: string;
  summary: string;
  keywords: string[];
  body: string;
  lastUpdated: string;
};

const corpus = JSON.parse(
  readFileSync(path.join(root, "knowledge", "docent-corpus.json"), "utf8"),
) as Note[];

const fixture = JSON.parse(
  readFileSync(path.join(root, "tests", "fixtures", "retrieval-parity.json"), "utf8"),
) as { corpusNoteCount: number; corpusOrder: string[] };

test("snapshot holds the complete corpus — nothing was selected out", () => {
  assert.equal(corpus.length, fixture.corpusNoteCount);
  assert.equal(corpus.length, 57);
});

test("snapshot array order matches the source return order element by element", () => {
  assert.deepEqual(corpus.map((n) => n.slug), fixture.corpusOrder);
});

test("every note carries the fields retrieval and ordering depend on", () => {
  for (const note of corpus) {
    assert.equal(typeof note.slug, "string");
    assert.equal(typeof note.title, "string");
    assert.equal(typeof note.summary, "string");
    assert.ok(Array.isArray(note.keywords));
    assert.equal(typeof note.body, "string");
    assert.equal(typeof note.lastUpdated, "string", `${note.slug} needs lastUpdated for ordering`);
  }
});

test("slugs are unique", () => {
  assert.equal(new Set(corpus.map((n) => n.slug)).size, corpus.length);
});
