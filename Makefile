.PHONY: demo ui-dev ui-build types figures test

# `just` is not installed on this machine (measured 2026-09-05) — hence a Makefile,
# no justfile.

# Recorded by default, on purpose: a demo must run on a conference wifi with no
# internet and no live model, so `demo` sets the same two variables
# `ui/playwright.config.ts`'s `webServer` sets for the smoke suite —
# `DOCKET_LLM_RECORDING` (the committed fixture `Intake`'s "Load the recorded request"
# button answers against) and `DOCKET_UI_MODE=recorded` (forces every agent-stage route
# to the recorded backend regardless of what provider is configured, so a stray
# `~/.config/docket/llm.json` from an earlier live session cannot leak in) — and opens
# straight into Demo A (`--demo a`; `--demo b` or `--demo none` are the other choices
# `docket ui --help` documents).
#
# To run the demo against a real, local model instead (the fallback story IS the demo,
# so this is meant to be shown, not hidden): override both variables on the command
# line, e.g.
#   DOCKET_UI_MODE=live DOCKET_LLM_PROVIDER=openai-compatible \
#     DOCKET_LLM_BASE_URL=http://127.0.0.1:11434/v1 DOCKET_LLM_MODEL=gemma4:e4b \
#     make demo
# (loopback needs no API key; never point this at a denylisted, PRC-origin model —
# `agent.backend.check_model_policy` refuses one either way). `DOCKET_UI_MODE` can also
# be left unset for "auto" (live if reachable, recorded the instant it is not) — set
# here to `recorded` explicitly so a demo that has not been told otherwise never
# depends on a network being up.
demo: ui-build
	DOCKET_LLM_RECORDING=$${DOCKET_LLM_RECORDING:-tests/fixtures/recorded/elicit.json} \
	DOCKET_UI_MODE=$${DOCKET_UI_MODE:-recorded} \
	uv run docket ui --open --demo a

ui-dev:
	cd ui && npm run dev

# Build only when the bundle is missing (ledger ruling 3) — an unconditional `npm ci`
# deletes node_modules and reinstalls from the registry every time, which is the exact
# failure mode the self-hosted-fonts decision exists to avoid at a venue with no
# internet. `vite.config.ts` outputs to src/docket/api/static/, so that is what this
# checks for.
ui-build:
	@if [ ! -f src/docket/api/static/index.html ] || [ -n "$$(find ui/src ui/index.html ui/vite.config.ts -newer src/docket/api/static/index.html -print -quit 2>/dev/null)" ]; then \
	  (cd ui && ([ -d node_modules ] || npm ci) && npm run build); \
	else echo "ui bundle is current"; fi

types:
	cd ui && npm run gen:types

# `@playwright/test` and Chromium landed with plan 07 Task 9 — `ui/node_modules/
# @playwright` is checked anyway (not assumed) so a worktree that skipped `npm ci`
# fails soft here rather than with a bare `npx` registry fetch mid-demo;
# `npx --no-install` below is the same guarantee at the tool-invocation level.
# The PNGs land in ui/test-results/figures/ (gitignored); set DOCKET_FIGURES_DIR to
# write them anywhere else.
figures:
	@test -d ui/node_modules/@playwright && cd ui && npx --no-install playwright test --project=figures \
	  || echo "skipping figures: run 'cd ui && npm ci' first"

test:
	uv run pytest -q
	@test -d ui/node_modules/@playwright && cd ui && npx --no-install playwright test --project=smoke \
	  || echo "skipping the UI smoke suite: run 'cd ui && npm ci' first"
