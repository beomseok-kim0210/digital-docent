// Measure what the mouth morph targets in a GLB actually do to the geometry.
//
//   node scripts/inspect_morph_targets.mjs [glb] [--json out.json]
//
// The runtime drives `viseme_*` morph targets, but a morph target existing and
// carrying a name proves nothing about whether it moves a mouth. This reads the
// actual POSITION deltas out of the binary chunk and answers three separate
// questions, because they fail independently:
//
//   1. do the targets exist            — name-level, cheap, already tested
//   2. do they deform geometry         — numeric, measured here
//   3. are the poses distinct          — measured here, pairwise
//
// A target can pass (1) and (2) and still be useless if every viseme produces
// nearly the same pose. Displacements are reported as a percentage of head
// height so they stay meaningful regardless of the asset's unit scale.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const COMPONENT_BYTES = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };
const TYPE_COUNT = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };

function readGlb(file) {
  const buf = readFileSync(file);
  if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error("not a GLB");
  const jsonLength = buf.readUInt32LE(12);
  const json = JSON.parse(buf.subarray(20, 20 + jsonLength).toString("utf8"));
  let offset = 20 + jsonLength;
  let bin = null;
  while (offset + 8 <= buf.length) {
    const len = buf.readUInt32LE(offset);
    const type = buf.readUInt32LE(offset + 4);
    const start = offset + 8;
    if (type === 0x004e4942) bin = buf.subarray(start, start + len);
    offset = start + len;
  }
  if (!bin) throw new Error("GLB has no BIN chunk");
  return { json, bin };
}

/** Read an accessor as Float32Array rows. Only the layouts this asset uses. */
function readVec3(json, bin, accessorIndex) {
  const acc = json.accessors[accessorIndex];
  if (acc.type !== "VEC3" || acc.componentType !== 5126) {
    throw new Error(`accessor ${accessorIndex} is not float VEC3`);
  }
  const view = json.bufferViews[acc.bufferView];
  const base = (view.byteOffset ?? 0) + (acc.byteOffset ?? 0);
  const stride = view.byteStride ?? COMPONENT_BYTES[acc.componentType] * TYPE_COUNT[acc.type];
  const out = new Float32Array(acc.count * 3);
  for (let i = 0; i < acc.count; i += 1) {
    const o = base + i * stride;
    out[i * 3] = bin.readFloatLE(o);
    out[i * 3 + 1] = bin.readFloatLE(o + 4);
    out[i * 3 + 2] = bin.readFloatLE(o + 8);
  }
  return out;
}

function magnitudes(delta) {
  const n = delta.length / 3;
  const mag = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    const x = delta[i * 3], y = delta[i * 3 + 1], z = delta[i * 3 + 2];
    mag[i] = Math.sqrt(x * x + y * y + z * z);
  }
  return mag;
}

/** Bounding box of the vertices a target actually moves most.
 *  A real mouth morph moves a compact cluster; a broken transfer scatters. */
function hotspot(positions, mag, fraction = 0.05) {
  const n = mag.length;
  const idx = Array.from({ length: n }, (_, i) => i).sort((a, b) => mag[b] - mag[a]);
  const take = idx.slice(0, Math.max(1, Math.round(n * fraction)));
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  const centroid = [0, 0, 0];
  for (const i of take) {
    for (let a = 0; a < 3; a += 1) {
      const v = positions[i * 3 + a];
      if (v < min[a]) min[a] = v;
      if (v > max[a]) max[a] = v;
      centroid[a] += v;
    }
  }
  for (let a = 0; a < 3; a += 1) centroid[a] /= take.length;
  return { count: take.length, min, max, size: max.map((v, a) => v - min[a]), centroid };
}

function main() {
  const args = process.argv.slice(2);
  const jsonFlag = args.indexOf("--json");
  const outPath = jsonFlag >= 0 ? args[jsonFlag + 1] : null;
  const file = args.find((a) => a.endsWith(".glb"))
    ?? path.join(process.cwd(), "public", "models", "docent-qka2.glb");

  const { json, bin } = readGlb(file);
  const node = (json.nodes ?? []).find((n) => typeof n.mesh === "number");
  const nodeScale = node?.scale ?? [1, 1, 1];
  const uniformScale = nodeScale[0];
  const mesh = json.meshes[node.mesh];
  const prim = mesh.primitives[0];
  const names = mesh.extras?.targetNames ?? [];

  const positions = readVec3(json, bin, prim.attributes.POSITION);
  const posAcc = json.accessors[prim.attributes.POSITION];
  const headHeightWorld = (posAcc.max[1] - posAcc.min[1]) * nodeScale[1];

  const pct = (v) => (100 * v * uniformScale) / headHeightWorld;

  const results = {};
  const magsByName = {};
  for (let t = 0; t < (prim.targets ?? []).length; t += 1) {
    const name = names[t] ?? `target_${t}`;
    const delta = readVec3(json, bin, prim.targets[t].POSITION);
    const mag = magnitudes(delta);
    magsByName[name] = mag;

    const eps = 1e-7;
    let moved = 0, sum = 0, max = 0;
    for (let i = 0; i < mag.length; i += 1) {
      if (mag[i] > eps) { moved += 1; sum += mag[i]; if (mag[i] > max) max = mag[i]; }
    }
    const hs = hotspot(positions, mag);
    results[name] = {
      affected_vertices: moved,
      affected_pct: +((100 * moved) / mag.length).toFixed(2),
      max_displacement_pct_of_head_height: +pct(max).toFixed(3),
      mean_displacement_pct_of_head_height: +pct(moved ? sum / moved : 0).toFixed(4),
      hotspot_size_pct_of_head_height: hs.size.map((v) => +pct(v).toFixed(2)),
      hotspot_centroid_local: hs.centroid.map((v) => +v.toFixed(4)),
    };
  }

  // Pairwise distinctness between the six mouth poses. Two visemes that differ
  // by almost nothing cannot read as different mouth shapes no matter how
  // correct the naming is.
  const visemes = names.filter((n) => n.startsWith("viseme_"));
  const pairwise = {};
  for (let i = 0; i < visemes.length; i += 1) {
    for (let j = i + 1; j < visemes.length; j += 1) {
      const a = magsByName[visemes[i]], b = magsByName[visemes[j]];
      let sum = 0, max = 0;
      for (let k = 0; k < a.length; k += 1) {
        const d = Math.abs(a[k] - b[k]);
        sum += d; if (d > max) max = d;
      }
      pairwise[`${visemes[i]} vs ${visemes[j]}`] = {
        max_pct: +pct(max).toFixed(3),
        mean_pct: +pct(sum / a.length).toFixed(4),
      };
    }
  }

  const report = {
    file,
    node_scale: nodeScale,
    head_height_world: +headHeightWorld.toFixed(5),
    vertices: posAcc.count,
    target_count: (prim.targets ?? []).length,
    target_names: names,
    note: "displacements are % of head height; the asset's own units are arbitrary",
    targets: results,
    viseme_pairwise_difference: pairwise,
  };

  const text = JSON.stringify(report, null, 2);
  if (outPath) writeFileSync(outPath, text + "\n", "utf8");

  console.log(`file            ${path.basename(file)}`);
  console.log(`vertices        ${posAcc.count}   head height (world) ${headHeightWorld.toFixed(4)}`);
  console.log(`node scale      ${uniformScale}`);
  console.log("");
  console.log("target        affected      %     max%   mean%   hotspot size % (x,y,z)");
  for (const [name, r] of Object.entries(results)) {
    console.log(
      `${name.padEnd(12)}  ${String(r.affected_vertices).padStart(7)}  ${String(r.affected_pct).padStart(6)}  ` +
      `${String(r.max_displacement_pct_of_head_height).padStart(6)}  ${String(r.mean_displacement_pct_of_head_height).padStart(6)}  ` +
      `${r.hotspot_size_pct_of_head_height.join(", ")}`
    );
  }
  console.log("");
  console.log("viseme pairwise difference (% of head height)");
  for (const [k, v] of Object.entries(pairwise)) {
    console.log(`  ${k.padEnd(26)} max ${String(v.max_pct).padStart(6)}   mean ${v.mean_pct}`);
  }
}

main();
