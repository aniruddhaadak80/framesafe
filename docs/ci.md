# CI and quality gates

## Jobs

Branch protection keys on exact job names, so these are stable:

| Job                 | Workflow       | What it proves                                 |
| ------------------- | -------------- | ---------------------------------------------- |
| `Format`            | `ci.yml`       | Prettier agrees with the tree                  |
| `Lint`              | `ci.yml`       | ESLint, including the React hooks rules        |
| `Typecheck`         | `ci.yml`       | `tsc --noEmit` across every workspace          |
| `Policy gates`      | `ci.yml`       | the seven policy gates below                   |
| `Test`              | `ci.yml`       | Vitest on Node 22 and 24                       |
| `Python test`       | `ci.yml`       | pytest on 3.11 and 3.12, plus mypy and ruff    |
| `Build`             | `ci.yml`       | every package builds, and the web app builds   |
| `Evals`             | `ci.yml`       | every audit case produces its expected verdict |
| `MCP proof`         | `ci.yml`       | a real MCP client over real stdio              |
| `Doctor smoke test` | `ci.yml`       | `framesafe doctor` exits 0 on a clean install  |
| `Secret scan`       | `gitleaks.yml` | no credentials, whole history                  |

Every third-party action is pinned to a commit SHA with the version in a trailing comment, the
workflow sets `permissions: contents: read`, and the concurrency group cancels superseded runs.

## The policy gates

Cheap and mechanical first, so a bad hex literal fails in 200 ms rather than after a build.

| Gate                    | Fails when                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------- |
| `check:skill-version`   | a `SKILL.md` body changed without a `metadata.version` bump                        |
| `check:no-secrets`      | a `.env` with values, a key file, or a token-shaped string is committed            |
| `check:theme-tokens`    | a raw hex/rgb/hsl literal appears under `apps/web` outside `tokens.css`            |
| `check:boundaries`      | a package imports another package's deep path                                      |
| `check:public-hygiene`  | stray logs, editor dirs, caches, or a >1 MB non-asset file                         |
| `check:readme-commands` | a README command is not a real script, bin, or script path                         |
| `check:clip-specs`      | a spec does not compile, or a text layer leaves the safe inset or overlaps another |
| `check:manifests`       | a manifest disagrees with its spec, its frames, its audits, or its video           |

`check:readme-commands` was extended during this build: it now resolves `node <path>` and
`python <path>` invocations and fails if the file does not exist. That is the dominant command
shape in this repository's README, and the gate had been silently skipping all of them.

## Local gate

```bash
npm run check
```

That is the exact command CI runs, so local and CI cannot drift. It is: format → lint → typecheck →
policy gates → Python lint and types → Vitest → pytest → build.

Two Python gates run standalone too:

```bash
python -m ruff check services/engine
python -m mypy services/engine/src
```

## The expensive gates

Not part of `npm run check`, because they render video:

```bash
npm run evals        # ~40s: renders seven audit cases
npm run verify -- --all   # re-renders the whole library
```

They run in CI as their own jobs so a slow failure is attributable.

## Why `check:manifests` calls the engine

It re-derives each spec digest rather than re-implementing canonicalisation in JavaScript. A gate
with its own idea of what a spec hashes to is a second implementation of the contract, and two
implementations of a digest is how a digest stops meaning anything. The first version of this gate
was written in JS and flagged all fifteen clips, because it hashed the raw document while the
engine hashes the normalised one.

## Ratchets

Shipped from day one even though the tree is clean, because a baseline is what keeps a gate
meaningful at month six: `lint-baseline.json` and `.vulnerability-exceptions.schema.json`. Debt
reduction shows up as a diff; debt growth fails CI.
