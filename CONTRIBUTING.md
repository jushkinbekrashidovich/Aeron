# Contributing to AERON

## Principles

- Never invent data, metrics or results. Every number in the docs must come from code in this repository.
- Prevent data leakage. Splits are chronological, and features use only information available at forecast time.
- Report associations as associations, not causes.
- Document limitations as you find them.

## Workflow

1. Create a branch from `main` (`feature/<topic>`, `docs/<topic>`, `research/<topic>`).
2. Make small, focused commits.
3. Check `git status` and `git diff --staged` before every commit.
4. Open a pull request describing what changed and why.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): `chore`, `docs`, `data`, `research`, `feat`, `ml`, `experiment`, `api`, `ui`, `test`.

Examples: `docs: document data sources`, `data: add OpenAQ ingestion`, `ml: add persistence baseline`.

## Never commit

- Secrets, API keys, `.env` files.
- Raw or processed datasets, except small samples whose license permits redistribution (see `data/samples/README.md`).
- Model binaries and temporary experiment outputs.
- Virtual environments and caches.

## Code

- Python 3.11+, type hints on public functions, tests for reusable code in `tests/`.
- Reusable logic goes in `src/aeron/`. Notebooks import from it and stay exploratory.
- Add a dependency only in the change that first uses it.

## Notebooks

- Clear outputs before committing unless the output is the deliverable and is small.
- Notebooks must run top to bottom on data obtainable through documented steps.
