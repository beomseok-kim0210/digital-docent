# AGENTS.md — Repository Engineering Guide

Working instructions for anyone (human or agent) writing code in this repository.

## What this repository is

A photo-personalized 3D digital docent. A user supplies a photograph; the docent
renders as a 3D head that reacts with facial expressions and lip-sync while answering
questions from a retrieval-backed corpus.

## Layout

```
src/          implementation
tests/        node:test suites (*.test.ts)
public/       static assets (3D models, textures)
scripts/      offline asset-generation pipelines (Python)
knowledge/    retrieval corpus snapshot
docs/         design notes and measurement records
```

## Commands

```
npm test        node --test    — the authoritative check; discovers *.test.ts
npm run build   tsc --noEmit   — type check
```

`npm test` must exit 0 before any change is considered finished.

## Language and runtime

- TypeScript on Node.js 24 or newer. Node runs `.ts` directly; there is no build step
  for tests.
- **Zero runtime dependencies is the default.** Adding one requires a written reason.
  Development-only type packages are fine.
- `node:test` and `node:assert/strict`. Do not add another test runner or assertion library.

## Design boundary — keep the core free of the DOM

Core algorithms take and return plain values and typed arrays. Canvas, WebGL, React,
and network calls live at the edges and stay thin.

This is not a style preference. It is what allows `node --test` to verify the real
logic without a browser or a bundler.

```
pure function + typed array   ← testable, and where the logic belongs
      ↑
thin adapter (canvas / React / route handler)
```

## Windows-first rules

This repository is developed on Windows 10 with PowerShell 5.1 and Git Bash.

- Paths: always `path.join` / `path.resolve`. Never hardcode `/` or `\`.
- File writes: write to a temporary file, then `fs.renameSync` into place.
- Encoding: state `utf8` explicitly on every read and write.
- Line endings: LF. `.gitattributes` enforces it.
- Shell examples in docs: no `&&` chaining — PowerShell 5.1 fails to parse it.
  One command per line.
- Filenames: avoid `:` `?` `*` `<` `>` `|` `"`.

## Source boundaries

- `public/` holds generated artifacts. Regenerate them with `scripts/`; do not hand-edit.
- `knowledge/` is a frozen corpus snapshot. Changing its contents changes retrieval
  results, so treat any edit as a behavioral change and say so.
- `scripts/` is Python and is not covered by `npm test`. Changes there need their own
  stated evidence.

## Security and privacy

- User photographs are personal data. Do not add code that uploads, stores, logs, or
  transmits them off the device without an explicit decision recorded in `docs/`.
- Never commit API keys, `.env` files, or private keys. Read secrets from the
  environment at runtime.
- Do not commit photographs of real people to this repository.
- Do not print secrets or absolute user paths into logs or committed artifacts; mask
  them.

## Writing changes

- Make the smallest change that satisfies what was asked. Unrelated refactoring in the
  same change makes it impossible to tell which edit caused which effect.
- Prefer reusing what is already here over adding a new file.
- Do not create interfaces with one implementation, factories with one product, or
  configuration for a value that never varies.
- If you are blocked or the request is contradictory, stop and say what blocked you.
  Guessing forward costs more to undo than stopping costs.

## Evidence

State what you ran and paste the output. "Tests pass" is a claim, not evidence.
