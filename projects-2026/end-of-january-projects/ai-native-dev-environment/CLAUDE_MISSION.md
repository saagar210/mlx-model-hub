# CLAUDE_MISSION.md
# Universal Context Engine Remediation Master Plan

## SECTION A: THE AUDIT VERDICT (The "Why")

### 1. 🛡️ Security Issues Summary
- Dashboard is unauthenticated, allows any origin with credentials, and binds to `0.0.0.0`, exposing internal data to LAN by default.
- Service start script binds KAS/LocalCrew/Dashboard to `0.0.0.0` with no auth, violating the “local-only” security posture.
- Context and feedback data are stored in plaintext with no redaction or encryption; any sensitive content is persisted.
- Dependencies are specified with `>=` without a pinned vulnerability policy or lock verification.

### 2. 💎 Code Quality Report
- Tool interfaces rely on untyped `dict`/`list` and loose parameter types, weakening contract clarity and mypy strictness.
- Widespread exception swallowing without logging hides root causes and impedes triage.
- Duplicate git detection logic; unused imports/variables; dead code paths.
- Linting/formatting policy not enforced (line length violations).

### 3. 🏗️ Architecture Assessment
- Global singletons and process-wide session state make concurrent sessions unsafe.
- Core tools lack error boundaries and do not satisfy the documented graceful-degradation contract.
- Feedback logging exists but is not wired into tool execution; metrics are effectively empty.
- Documented behaviors are not implemented (dedupe, embedding cache, lazy init).

### 4. 🧪 Test Coverage Analysis
- No tests for router, adapters, embedding, feedback, dashboard, config/models.
- No error-path tests (service outages, invalid params, embedding failures).
- Session tests are not fully isolated (Redis may leak into runtime tests).
- No integration tests for dashboard endpoints or end-to-end MCP flows.

### 5. ⚡ Performance Observations
- Async functions call synchronous ChromaDB operations directly, blocking the event loop under load.
- `get_recent` scans full collections and filters in Python (O(n) per call).
- Feedback stats load full metadata for all interactions; unbounded growth risk.
- HTTP clients are never closed in normal server lifecycle; potential resource leak.

### 6. ⚠️ Risk Assessment
- Single points of failure: Ollama and ChromaDB for save/search/end_session.
- Default LAN exposure and lack of auth increase operational risk.
- `allow_reset=True` enables catastrophic data loss if misused.
- No retention/compaction strategy for context or feedback data.
- Metrics computed on a capped interaction set; operational drift likely.

### 7. 💡 Improvement Recommendations
- Lock services to localhost by default and restrict CORS; make host/origins configurable.
- Implement consistent error boundaries + structured logging for all tools.
- Wire feedback logging into every tool call with latency/error capture.
- Align docs with code (tool params, endpoints, dedupe/cache claims) or implement the claims.
- Add async-safe storage access, pagination for `get_recent`, and close HTTP clients on shutdown.
- Expand tests across untested modules and error paths; isolate Redis in tests.

## SECTION B: THE STRATEGIC ROADMAP (The "What")

### Phase 1: Security Hardening (Localhost-Only)
- [ ] Task 1.1: Bind Dashboard host to `127.0.0.1` by default; make host configurable via settings or env.
- [ ] Task 1.2: Restrict CORS to localhost origins; disable `allow_credentials` unless required.
- [ ] Task 1.3: Update `scripts/start_services.sh` to bind KAS/LocalCrew/Dashboard to localhost and document overrides.
- [ ] Task 1.4: Add a hard warning in docs if users override localhost binding.
- **Gatekeeper:** Verify all services listen on `127.0.0.1` in default configuration and CORS is not `*`.

### Phase 2: Error Boundaries + Logging
- [ ] Task 2.1: Add structured logging for exceptions in context store, adapters, session manager, router, and dashboard.
- [ ] Task 2.2: Standardize error responses for all MCP tools (consistent keys, no raw tracebacks).
- [ ] Task 2.3: Ensure graceful degradation aligns with `docs/ARCHITECTURE.md`.
- **Gatekeeper:** Induce a simulated outage and confirm tools return structured errors without crashing.

### Phase 3: Feedback Logging Integration
- [ ] Task 3.1: Wrap all MCP tools to log interactions (tool name, params, latency, error).
- [ ] Task 3.2: Ensure logs capture error state and output preview consistently.
- [ ] Task 3.3: Add tests to verify logging is called per tool invocation.
- **Gatekeeper:** Run `quality_stats` after tool calls and verify metrics increment.

### Phase 4: Doc/Code Alignment
- [ ] Task 4.1: Fix README Quick Start `mcp` import or export from package.
- [ ] Task 4.2: Align `docs/MCP_TOOLS.md` tool parameters/returns with actual code.
- [ ] Task 4.3: Correct architecture claims (dedupe, embedding cache, lazy init) or implement them.
- **Gatekeeper:** Every documented tool parameter is verifiably present in code.

### Phase 5: Performance and Resource Safety
- [ ] Task 5.1: Offload blocking ChromaDB calls from async paths (executor or sync boundary).
- [ ] Task 5.2: Add pagination/limits to `get_recent` and avoid full scans where possible.
- [ ] Task 5.3: Close HTTP clients on shutdown; wire lifecycle hooks for cleanup.
- **Gatekeeper:** Documented latency and resource behavior is reproducible under load test.

### Phase 6: Test Coverage Expansion
- [ ] Task 6.1: Add router classifier/handler tests (pattern + LLM fallback mocked).
- [ ] Task 6.2: Add adapter tests (success + failure paths).
- [ ] Task 6.3: Add feedback tracker/metrics tests.
- [ ] Task 6.4: Add dashboard endpoint tests with mocked dependencies.
- [ ] Task 6.5: Add error-path tests for critical tool flows.
- **Gatekeeper:** Coverage report shows meaningful coverage for all major modules; no critical path untested.

### Phase 7: Risk Controls and Data Hygiene
- [ ] Task 7.1: Add retention/compaction policy for feedback/context data (configurable).
- [ ] Task 7.2: Review `allow_reset=True` usage; add safeguards in production mode.
- [ ] Task 7.3: Add warnings or validation around sensitive data storage.
- **Gatekeeper:** Documented data lifecycle policy and safeguards are implemented and tested.

## SECTION C: THE MARCHING ORDERS (The "How")

> **TO: CLAUDE (JUNIOR ENGINEER)**
> **FROM: CODEX (SENIOR ARCHITECT)**
>
> 1.  **READ** this entire document. This is your contract.
> 2.  **EXECUTE** Phase 1. Run tests. Verify "Definition of Done."
> 3.  **COMMIT** your changes to the local branch (`git commit -m "feat: Phase 1 complete"`).
> 4.  **LOOP** immediately to Phase 2. Do not ask for permission unless you hit a critical blocker.
> 5.  **CONTINUE** until all Phases are marked [x].
> 6.  **REPORT** back only when the entire Roadmap is complete. Generate `MISSION_REPORT.md` summarizing your actions.
