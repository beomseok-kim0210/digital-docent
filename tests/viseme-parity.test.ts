// T7 viseme parity (AC 10).
//
// fixture 는 canonical source commit 의 src/lib/docent/visemes.ts 를 scratch 에서
// 그대로 실행해 동결했다. 이관본은 원본과 byte-identical 이다.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { textToVisemeTimeline } from "../src/lib/docent/visemes.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

type Fixture = {
  canonicalSourceCommit: string;
  cases: { text: string; timeline: { frames: { charIndex: number; viseme: string }[]; textLength: number } }[];
};

const fixture = JSON.parse(
  readFileSync(path.join(root, "tests", "fixtures", "viseme-parity.json"), "utf8"),
) as Fixture;

test("viseme fixture is pinned to the canonical source commit", () => {
  assert.equal(fixture.canonicalSourceCommit, "b295c1cc20f117b18c7ef2d916ded6aec549f565");
});

for (const item of fixture.cases) {
  test(`viseme timeline ${JSON.stringify(item.text)}`, () => {
    assert.deepEqual(textToVisemeTimeline(item.text), item.timeline);
  });
}

test("한글 자모 분해가 중성을 입모양으로 매핑한다", () => {
  // 아(ㅏ) 이(ㅣ) 우(ㅜ) 에(ㅔ) 오(ㅗ)
  assert.deepEqual(
    textToVisemeTimeline("아이우에오").frames.map((f) => f.viseme),
    ["a", "i", "u", "e", "o"],
  );
});

test("ㅁ/ㅂ/ㅍ 계열 초성은 다문 입으로 매핑된다", () => {
  assert.equal(textToVisemeTimeline("마").frames[0]?.viseme, "m");
  assert.equal(textToVisemeTimeline("바").frames[0]?.viseme, "m");
  assert.equal(textToVisemeTimeline("파").frames[0]?.viseme, "m");
});

test("연속으로 같은 입모양이면 프레임을 늘리지 않는다", () => {
  const frames = textToVisemeTimeline("아아아").frames;
  assert.equal(frames.length, 1);
});
