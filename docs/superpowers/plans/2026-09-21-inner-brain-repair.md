# Inner Brain repair implementation plan

**Goal:** Repair the existing advisory model and context connections before adding web search.

**Architecture:** Inner Brain analyzes only; Context Builder reads through public services; conversation owners pass context and own persistence. Core remains routing only. The user's repair request authorizes restoring the already documented V1 behavior.

**Constraints:** Preserve explicit commands, approval requirements, manual metadata, Flow history isolation, and primary model settings. Do not implement web search or change Creation model routing.

## Execution checklist

- [x] Add regression tests in `tests/test_inner_brain.py` and repair the contradictory Flow assertion in `tests/test_flow_chat.py`. Cover failed refresh preservation, malformed output, one inference per Flow request, export non-mutation, and secondary-client settings.
- [x] Repair `inner_brain/service.py` and `models.py`: separate intent and refresh prompts, bounded JSON validation, safe failure status, recent transcript retention, and actual client model attribution.
- [x] Add optional response format and temperature settings in `llm_client/ollama_client.py`; configure only Inner Brain in `amadeus_app/composition.py` with JSON format, temperature zero, thinking disabled, and a 30-second timeout.
- [x] Repair `context_builder/inferred_context.py`: use read-only inventories for sheets, exports, and graph hints rather than mutation-capable display handlers; retain existing verified file/metadata handlers. Flow sheet inventory is global only; no inferred body retrieval.
- [x] Pass already resolved context from `flow_chat/request_handler.py` to `flow_chat/flow_chat_service.py`, avoiding a second inference call. Report safe analysis status in both conversation traces.
- [x] Guard `chat_workspace/metadata.py` against saving failed/incomplete refreshes. Preserve the existing analysis and surface the existing GUI error path.
- [x] Run focused tests and public synthetic live-model checks. Run full regression discovery with offscreen Qt and `python -m compileall .` using an available Python runtime. Update module docs and changelog with measured outcomes and limitations.
- [x] Review diff, stage only intended paths, inspect staged summary, commit as `fix: restore reliable inner brain analysis`, and push the current branch.

## Verification commands

`python -m unittest discover -s tests -p test_inner_brain.py -v`

`python -m unittest discover -s tests -p test_flow_chat.py -q`

`python -m unittest discover -s tests -v` with `QT_QPA_PLATFORM=offscreen`

`python -m compileall .`

Synthetic live checks must use disposable temporary storage and report success/failure and timing without logging user data or model thinking. No automatic model download or substitution.

## Result

354 automated regressions passed; two optional live-model tests passed separately (eight intent cases and one summary). Compilation passed. The repair is complete; web search remains deferred. Delivery uses the commit and push recorded in the task completion report.
