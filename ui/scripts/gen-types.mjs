#!/usr/bin/env node
// Generate ui/src/types/objects.d.ts from the 39 committed JSON Schemas under
// src/docket/schema/json/, so the UI's TypeScript shapes cannot drift from what the
// kernel and agent actually write. Run via `npm run gen:types` (also wired as
// `prebuild`); CI and Task 9 run this then `git diff --exit-code src/types` — a schema
// change the UI has not regenerated against fails the build rather than mis-rendering
// a field.
//
// Each schema file is self-contained (no cross-file `$ref`s in this codebase — verified
// at the time this script was written), but every file duplicates a handful of shared
// local `$defs` (`actor`, `provenance`, `exclusionRef`, `gapRef`, `id`, `timestamp`, …).
// Compiling each file independently with `compileFromFile` and concatenating the
// results — the literal reading of the plan's Step 2 — hoists those local `$defs` into
// top-level named types (`Actor`, `Provenance`, `Id`, `Timestamp`, ...) once per file.
// Interfaces with identical shapes merge harmlessly, but `Id`/`Timestamp` compile to
// `type` aliases (because they're bare `"type": "string"` schemas, not objects), and
// TypeScript does not allow two `type` alias declarations with the same name even when
// they're identical — `tsc --noEmit` fails with `Duplicate identifier 'Id'` (and
// `'Timestamp'`) the moment a second schema file is compiled. So this script inlines
// every local `$ref` before handing the schema to json-schema-to-typescript: each of
// the 39 output types is one self-contained interface (or type, where the schema's own
// root uses `allOf`/`if`/`then` and so cannot be a plain interface — see `Evidence`),
// named after the schema's own `title`, with no shared names to collide across files.

import { readdir, readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_DIR = path.resolve(HERE, '..', '..', 'src', 'docket', 'schema', 'json');
const OUT_DIR = path.resolve(HERE, '..', 'src', 'types');
const OUT_FILE = path.join(OUT_DIR, 'objects.d.ts');

const BANNER =
  '/* GENERATED from src/docket/schema/json — do not edit. Run `npm run gen:types`.\n' +
  '   One interface per committed JSON Schema (39 object shapes) so the UI cannot\n' +
  '   silently drift from what the kernel and agent actually write. Local `$defs`\n' +
  '   (actor, provenance, exclusionRef, gapRef, id, timestamp, ...) are inlined per\n' +
  '   file rather than hoisted to shared names — see ui/scripts/gen-types.mjs. */';

/** Recursively replace every `{"$ref": "#/$defs/x"}` with a deep clone of
 * `$defs.x`, then drop `$defs` itself. `$defs` entries may reference other
 * `$defs` entries in the same file (e.g. `exclusionRef` refs `id`) but none
 * reference themselves — this is a finite, non-circular walk over these
 * schemas as authored; a cycle would recurse until the stack overflows,
 * which is a loud enough failure for a generator script. */
function inlineLocalRefs(node, defs) {
  if (Array.isArray(node)) return node.map((n) => inlineLocalRefs(n, defs));
  if (node && typeof node === 'object') {
    if (typeof node.$ref === 'string' && node.$ref.startsWith('#/$defs/')) {
      const key = node.$ref.slice('#/$defs/'.length);
      const target = defs[key];
      if (!target) throw new Error(`dangling $ref: #/$defs/${key}`);
      return inlineLocalRefs(structuredClone(target), defs);
    }
    const out = {};
    for (const [k, v] of Object.entries(node)) {
      if (k === '$defs') continue; // nothing should still reference this after inlining
      out[k] = inlineLocalRefs(v, defs);
    }
    return out;
  }
  return node;
}

async function main() {
  const entries = await readdir(SCHEMA_DIR);
  const files = entries.filter((f) => f.endsWith('.schema.json')).sort();
  if (files.length === 0) {
    throw new Error(`no *.schema.json files found under ${SCHEMA_DIR}`);
  }

  const blocks = [];
  for (const file of files) {
    const raw = JSON.parse(await readFile(path.join(SCHEMA_DIR, file), 'utf8'));
    const inlined = inlineLocalRefs(raw, raw.$defs ?? {});
    const ts = await compile(inlined, raw.title ?? path.basename(file, '.schema.json'), {
      additionalProperties: false,
      bannerComment: '',
      style: { semi: true, singleQuote: true },
    });
    blocks.push(ts.trim());
  }

  await mkdir(OUT_DIR, { recursive: true });
  await writeFile(OUT_FILE, `${BANNER}\n\n${blocks.join('\n\n')}\n`, 'utf8');
  console.log(`wrote ${path.relative(process.cwd(), OUT_FILE)} from ${files.length} schemas`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
