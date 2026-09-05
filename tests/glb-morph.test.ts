// T8 렌더·morph (AC 8 · 9) — 자산 수준 단언만 한다.
//
// WebGL 은 node:test 로 검증할 수 없다. 실제 렌더와 표정 전환은 Host 육안 확인이며
// 이 스위트는 그것을 대신하지 않는다. 여기서는 GLB 가 런타임이 요구하는 morph target
// 이름을 갖고 있는지만 자산 수준에서 확인한다.
//
// neutral 은 morph target 이 아니다 — emotion weight 가 전부 0 인 runtime state 다.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

interface GlbDocument {
  accessors?: { min?: number[]; max?: number[] }[];
  images?: { bufferView?: number; mimeType?: string }[];
  textures?: { source?: number }[];
  materials?: {
    pbrMetallicRoughness?: { baseColorTexture?: { index?: number } };
  }[];
  meshes?: {
    extras?: { targetNames?: string[] };
    primitives?: {
      attributes?: Record<string, number>;
      material?: number;
    }[];
  }[];
  nodes?: {
    mesh?: number;
    scale?: number[];
    translation?: number[];
  }[];
}

function readGlbDocument(file: string): GlbDocument {
  const buffer = readFileSync(file);
  const jsonLength = buffer.readUInt32LE(12);
  return JSON.parse(buffer.subarray(20, 20 + jsonLength).toString("utf8")) as GlbDocument;
}

function glbTargetNames(document: GlbDocument): string[] {
  return document.meshes?.flatMap((mesh) => mesh.extras?.targetNames ?? []) ?? [];
}

interface Bounds {
  min: number[];
  max: number[];
}

function worldPositionBounds(document: GlbDocument): Bounds {
  const bounds: Bounds = {
    min: [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY],
    max: [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY],
  };
  for (const node of document.nodes ?? []) {
    if (typeof node.mesh !== "number") continue;
    const mesh = document.meshes?.[node.mesh];
    assert.ok(mesh, `node references missing mesh ${node.mesh}`);
    const scale = node.scale ?? [1, 1, 1];
    const translation = node.translation ?? [0, 0, 0];
    assert.equal(scale.length, 3, "mesh node scale must be three-dimensional");
    assert.equal(translation.length, 3, "mesh node translation must be three-dimensional");

    for (const primitive of mesh.primitives ?? []) {
      const positionIndex = primitive.attributes?.POSITION;
      if (typeof positionIndex !== "number") assert.fail("missing POSITION accessor");
      const accessor = document.accessors?.[positionIndex];
      assert.ok(accessor?.min && accessor.max, "POSITION accessor is missing bounds");
      for (let axis = 0; axis < 3; axis += 1) {
        const transformed = [
          accessor.min[axis] * scale[axis] + translation[axis],
          accessor.max[axis] * scale[axis] + translation[axis],
        ];
        bounds.min[axis] = Math.min(bounds.min[axis], ...transformed);
        bounds.max[axis] = Math.max(bounds.max[axis], ...transformed);
      }
    }
  }
  assert.ok(bounds.min.every(Number.isFinite), "GLB has no bounded mesh nodes");
  return bounds;
}

const baseline = readGlbDocument(path.join(root, "public", "models", "docent.glb"));
const names = glbTargetNames(baseline);
const qka2 = readGlbDocument(path.join(root, "public", "models", "docent-qka2.glb"));
const qka2Names = glbTargetNames(qka2);

const EMOTION_MORPHS = ["smile", "thinking", "surprised", "sad"];
const VISEME_MORPHS = ["viseme_a", "viseme_i", "viseme_u", "viseme_e", "viseme_o", "viseme_m"];

test("emotion morph targets are the four the runtime drives", () => {
  for (const name of EMOTION_MORPHS) assert.ok(names.includes(name), `missing ${name}`);
  assert.equal(EMOTION_MORPHS.length, 4);
});

test("blink morph target exists", () => {
  assert.ok(names.includes("blink"));
});

test("six viseme morph targets exist", () => {
  for (const name of VISEME_MORPHS) assert.ok(names.includes(name), `missing ${name}`);
  assert.equal(VISEME_MORPHS.length, 6);
});

test("relevant morph target count is eleven", () => {
  const relevant = names.filter(
    (n) => EMOTION_MORPHS.includes(n) || n === "blink" || VISEME_MORPHS.includes(n),
  );
  assert.equal(relevant.length, 11);
});

test("neutral is a runtime state, not a morph target", () => {
  assert.equal(names.filter((n) => n === "neutral").length, 0);
});

test("QK-A2 avatar declares exactly the eleven runtime morph targets", () => {
  const expected = [...VISEME_MORPHS, ...EMOTION_MORPHS, "blink"].sort();
  assert.deepEqual([...qka2Names].sort(), expected);
  assert.equal(qka2Names.includes("neutral"), false);
});

test("QK-A2 avatar embeds and binds its albedo through TEXCOORD_0", () => {
  assert.ok(qka2.images && qka2.images.length > 0, "missing embedded image");
  assert.ok(qka2.textures && qka2.textures.length > 0, "missing texture");
  assert.ok(qka2.materials && qka2.materials.length > 0, "missing material");

  const textureIndex = qka2.materials[0].pbrMetallicRoughness?.baseColorTexture?.index;
  assert.equal(textureIndex, 0, "material does not reference the albedo texture");
  assert.equal(qka2.textures[textureIndex]?.source, 0, "texture does not reference the image");
  assert.equal(qka2.images[0].mimeType, "image/png");
  assert.equal(typeof qka2.images[0].bufferView, "number", "image is not embedded in the GLB");

  const primitives = qka2.meshes?.flatMap((mesh) => mesh.primitives ?? []) ?? [];
  assert.ok(primitives.length > 0, "missing mesh primitive");
  for (const primitive of primitives) {
    assert.equal(typeof primitive.attributes?.TEXCOORD_0, "number", "missing TEXCOORD_0");
    assert.equal(primitive.material, 0, "primitive does not bind the albedo material");
  }
});

test("QK-A2 avatar world-space bounds match the baseline framing", () => {
  const expected = worldPositionBounds(baseline);
  const actual = worldPositionBounds(qka2);
  const tolerance = 0.025;

  for (const edge of ["min", "max"] as const) {
    for (let axis = 0; axis < 3; axis += 1) {
      assert.ok(
        Math.abs(actual[edge][axis] - expected[edge][axis]) <= tolerance,
        `${edge}[${axis}] differs by more than ${tolerance}: ` +
          `expected ${expected[edge][axis]}, received ${actual[edge][axis]}`,
      );
    }
  }
});
