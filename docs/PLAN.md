# Retry semantics and file merge behavior

This note explains how the Phase‑2 pipeline handles reviewer-driven retries and how generator nodes should return or merge file maps. Put simply:

- The pipeline runs these nodes in order: planner → architecture → backend → database → testing → reviewer → package.
- The reviewer validates the assembled project and can either:
  - pass the build (no review_feedback), or
  - request a retry by returning a `review_feedback` string and setting `files` to `None` (this intentionally wipes the file map so the rebuild starts from a clean state), or
  - fail the build for good after a bounded number of attempts.

Key state fields (ApiBuilderAgentState)
- `spec` — planner's build spec ({project_name, database, auth, entities}).
- `attempts` — integer, incremented by the planner each time a new planning run starts (first attempt = 1). Used to bound retries.
- `context` — normalized render context derived from `spec` (entities, flags like `use_jwt`, etc.).
- `files` — the generated project file map (path -> content). Nodes that render should return their slice of files; the framework merges them into the full file map using `merge_files`.
- `review_feedback` — optional string containing the reviewer's problem report. When the planner consumes feedback it should clear this field so stale feedback doesn't leak forward.
- `zip_bytes` — packaged archive bytes produced by the `package` node on success.

merge_files behavior
- The runtime uses the helper `merge_files(current, update)` (see src/agents/api_builder_agent/state.py) with this contract:
  - If a node returns `update` as `None`, `merge_files` returns an empty dict: this wipes the accumulated file map. This is used intentionally by the reviewer when requesting a rebuild so no stale files remain.
  - Otherwise, `merge_files` returns `{**(current or {}), **update}`: the update's keys overwrite existing keys. Each renderer node should return only the files it is responsible for (a slice), not the entire map.

Retry flow (example)
1. Planner runs (attempts increments to 1) and writes `spec`.
2. Architecture node builds `context` and returns scaffold files (files slice).
3. Backend, database, and testing nodes each return their files; the runtime merges slices into `files`.
4. Reviewer runs and discovers problems. If problems are found and `attempts < _MAX_BUILD_ATTEMPTS`, the reviewer returns:
   - `review_feedback`: concatenated problem report (string)
   - `files`: `None` (wipe file map)
   - messages describing the retry
5. Graph conditional routes back to the planner. Planner receives `review_feedback` and `previous_spec` in its prompt and should attempt to return a corrected `spec`. Planner also clears `review_feedback` on output to avoid double application.
6. Planner runs again (attempts increments). Nodes render again from a clean state. If reviewer still fails and attempts reach the configured max, the reviewer returns an `error` which fails the build permanently.

Invariants and maintainer guidance
- Nodes should return only their slice of files. Do not mutate the full file map in-place.
- Returning `files: None` is a deliberate signal to wipe the file map. Use it only when you intend a full rebuild from scratch.
- The reviewer currently uses text- and AST-based checks to validate wiring and syntax. If you modify templates, ensure the invariants the reviewer relies on (router names, class names, mount patterns) are preserved or update the reviewer accordingly.
- The planner consumes `review_feedback` and `previous_spec` to produce a corrected spec. Ensure planner prompt construction and normalization remain aligned with what the reviewer reports.

Where to look in code
- State & merge helper: src/agents/api_builder_agent/state.py
- Planner: src/agents/api_builder_agent/nodes/planner.py
- Reviewer: src/agents/api_builder_agent/nodes/reviewer.py
- Graph wiring & conditional retry: src/agents/api_builder_agent/graph.py
- Renderer groups: src/agents/api_builder_agent/generators/renderer.py

Tests
- The tests covering retry/rebuild behavior live in tests/test_api_builder.py. They mock the LLM and renderer outputs to exercise retry-success and retry-exhausted paths. Update or add tests when changing retry bounds or the merge semantics.

If you want, I can also:
- Add a short example state transition (JSON) showing the planner output and reviewer feedback, or
- Add a short diagram to this note illustrating the conditional loop.
