import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// 이 스위트는 scaffold 가 살아 있다는 것만 확인한다.
// 실제 제품 테스트는 Baseline 이관과 함께 들어온다.

test("package declares the authoritative check command", () => {
  const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")) as {
    scripts?: Record<string, string>;
  };
  assert.equal(pkg.scripts?.test, "node --test");
});

test("node runs typescript sources directly", () => {
  const major = Number(process.versions.node.split(".")[0]);
  assert.ok(major >= 24, `expected Node 24 or newer, got ${process.versions.node}`);
});
