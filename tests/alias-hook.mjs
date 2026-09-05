// tsconfig 의 "@/*" -> "./src/*" 별칭을 node:test 런타임에서도 해석한다.
//
// 이관한 소스는 canonical source commit 과 동일한 "@/" import 를 그대로 유지한다.
// Next.js 는 tsconfig paths 로 이를 해석하지만 node --test 는 해석하지 못한다.
// 소스를 고쳐 상대경로로 바꾸는 대신 로더 훅을 둔다 — 이관 파일을 건드리지 않는 쪽이
// baseline 충실도에 유리하다.
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { register } from "node:module";

const SRC = path.resolve(import.meta.dirname, "..", "src");
const EXTENSIONS = [".ts", ".tsx", ".mts", ".js", ".jsx"];

function firstExisting(base) {
  const candidates = [
    ...EXTENSIONS.map((e) => base + e),
    ...EXTENSIONS.map((e) => path.join(base, `index${e}`)),
  ];
  return candidates.find((candidate) => existsSync(candidate));
}

export function resolve(specifier, context, nextResolve) {
  // "@/..." -> tsconfig paths
  if (specifier.startsWith("@/")) {
    const hit = firstExisting(path.join(SRC, specifier.slice(2)));
    if (hit) return nextResolve(pathToFileURL(hit).href, context);
  }

  // 확장자 없는 상대 import. 이관 소스는 원본 그대로라 "./retrieval" 처럼 쓰는데,
  // 번들러는 해석하지만 Node ESM 은 완전한 specifier 를 요구한다.
  if ((specifier.startsWith("./") || specifier.startsWith("../")) && !path.extname(specifier)) {
    const parentPath = context.parentURL?.startsWith("file:")
      ? path.dirname(fileURLToPath(context.parentURL))
      : undefined;
    if (parentPath) {
      const hit = firstExisting(path.resolve(parentPath, specifier));
      if (hit) return nextResolve(pathToFileURL(hit).href, context);
    }
  }

  return nextResolve(specifier, context);
}

register(import.meta.url, import.meta.url);
