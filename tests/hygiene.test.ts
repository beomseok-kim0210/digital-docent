// T2 잔여 참조 (AC 3) + T9 저장소 위생 · dependency 경계 (AC 5 · 6 · 7 · 23).
//
// 검사 대상은 product 저장소의 runtime/source tracked 파일이다.
// 계약 파일 · migration inventory · .bcos · provenance 문서는 출처 기록이 목적이므로
// 검사에서 제외한다 (Contract T2).
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const SCAN_DIRECTORIES = ["src", "tests", "scripts", "knowledge"];
const SCAN_FILES = ["package.json", "tsconfig.json", "AGENTS.md"];
// 스캔에서 제외하는 것과 그 근거:
//  - migration-inventory.md : 출처를 기록하는 것이 목적인 provenance 문서 (Contract T2)
//  - hygiene.test.ts        : 탐지기 자신이 검사 문자열을 포함한다
//  - docent-corpus.json     : canonical corpus 스냅샷. 노트 본문에 원본 저장소 이름이
//                             등장하지만 이는 AC 15 가 요구하는 원본 데이터이며 편집하면
//                             스냅샷 완전성이 깨진다
const EXCLUDED_FILES = new Set([
  "migration-inventory.md",
  "hygiene.test.ts",
  "docent-corpus.json",
]);
const TEXT_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".py", ".css"]);

function walk(directory: string): string[] {
  let found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const full = path.join(directory, entry);
    if (statSync(full).isDirectory()) {
      found = found.concat(walk(full));
    } else if (TEXT_EXTENSIONS.has(path.extname(entry)) && !EXCLUDED_FILES.has(entry)) {
      found.push(full);
    }
  }
  return found;
}

const scanned = [
  ...SCAN_DIRECTORIES.flatMap((d) => {
    try {
      return walk(path.join(root, d));
    } catch {
      return [];
    }
  }),
  ...SCAN_FILES.map((f) => path.join(root, f)),
];

test("scan actually covered the migrated sources", () => {
  assert.ok(scanned.length > 20, `expected a populated scan, got ${scanned.length}`);
});

// AC 3 은 원본 저장소를 가리키는 **import·경로** 참조가 0건일 것을 요구한다.
// provenance 문자열(예: GNM 파이프라인이 GLB 에 써 넣는 generator 이름)은 경로가 아니며,
// byte-identical 이관 파일이라 고칠 수 없다 — 고치면 커밋된 docent.glb 의
// asset.generator 와도 어긋난다. 그래서 경로/import 형태만 탐지한다.
const SOURCE_PATH_PATTERNS = [
  /beomseok-portfolio[/\\]/,
  /from\s+["'][^"']*beomseok-portfolio/,
  /import\s*\(\s*["'][^"']*beomseok-portfolio/,
  /require\s*\(\s*["'][^"']*beomseok-portfolio/,
];

test("no source file imports from or paths into the migration source repository", () => {
  const hits = scanned.filter((file) => {
    const content = readFileSync(file, "utf8");
    return SOURCE_PATH_PATTERNS.some((pattern) => pattern.test(content));
  });
  assert.deepEqual(hits.map((f) => path.relative(root, f)), []);
});

test("the only bare mention left is the GNM generator provenance string", () => {
  const bare = scanned
    .filter((file) => readFileSync(file, "utf8").includes("beomseok-portfolio"))
    .map((f) => path.relative(root, f).replaceAll("\\", "/"));
  assert.deepEqual(bare, ["scripts/gnm/build_glb.py"]);
});

test("AGENTS.md carries no orchestration vocabulary", () => {
  const agents = readFileSync(path.join(root, "AGENTS.md"), "utf8");
  for (const term of ["Task Contract", "Host Verification", "Independent Review", "actor_id", "bcos"]) {
    assert.equal(agents.includes(term), false, `AGENTS.md must not contain ${term}`);
  }
});

// AC 5 · 6 — 선언된 runtime dependency 는 canonical closure 집합 안에 있어야 한다.
// react-dom 은 closure walker 가 direct import 로 잡지 못했으나 react/next 가 요구하는
// 렌더러이며 canonical commit 의 package.json 에도 선언돼 있다. 근거는
// docs/migration-inventory.md 에 기록했다.
const CLOSURE_PACKAGES = new Set([
  "react",
  "react-dom",
  "next",
  "three",
  "@react-three/fiber",
  "@react-three/drei",
  "framer-motion",
  "lucide-react",
  "@anthropic-ai/sdk",
]);

const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")) as {
  dependencies?: Record<string, string>;
};

test("every declared runtime dependency belongs to the canonical closure", () => {
  const declared = Object.keys(pkg.dependencies ?? {});
  assert.ok(declared.length > 0, "the standalone runtime needs its closure declared");
  const outside = declared.filter((name) => !CLOSURE_PACKAGES.has(name));
  assert.deepEqual(outside, []);
});

test("every dependency is documented in the migration inventory", () => {
  const inventory = readFileSync(path.join(root, "docs", "migration-inventory.md"), "utf8");
  for (const name of Object.keys(pkg.dependencies ?? {})) {
    assert.ok(inventory.includes(name), `${name} is undocumented`);
  }
});

test("no API key or env file was committed into the sources", () => {
  for (const file of scanned) {
    const content = readFileSync(file, "utf8");
    assert.equal(/sk-ant-[A-Za-z0-9_-]{10,}/.test(content), false, `${file} looks like it holds a key`);
  }
});
