# smoke: the Codex worker channel works end to end

Read-only. Run this after a change to `codex-launcher.cjs`, `codex-run.mjs` or the Codex CLI,
to prove the launcher resolves, a session starts, and the final message reaches the ledger.

## Outcome

A three-section report about this repository's shape, and nothing else.

## Scope

Working root: the repository root.
Read: the top-level directory listing, `AGENTS.md`, `pyproject.toml`.
Write: nothing.

## Inputs

None. This prompt is self-contained.

## Task

1. List the top-level entries of the working directory.
2. From `AGENTS.md`, name in one line each the two products this repository builds.
3. From the root `pyproject.toml`, report the workspace member directories. If the file you
   are asked for does not exist, say so plainly rather than substituting another file.

## Hard rules

- Read only. Do not create, edit or delete any file.
- Do not run git, a test suite, a linter, a build, a server or a database.
- Do not run any command that reaches the network.

## Reply contract

Three labelled sections, `LISTING`, `PRODUCTS`, `PACKAGE`, with no preamble and no summary of
these instructions.
