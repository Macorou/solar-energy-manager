# Charging Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Operational EVCC-like charging history, statistics and exports on SEM's real persisted measurements.

**Architecture:** Single local producer (ChargingTracker), normalized SQLite history with atomic runtime checkpoints, authenticated query/aggregate/export endpoints, React SVG charts and responsive table/detail UI.

**Tech Stack:** Existing Python 3.12/FastAPI/SQLite, React 19/TypeScript/Vite, pytest/Vitest/Playwright. Standard-library CSV/XLSX export.

**Spec:** docs/superpowers/specs/2026-10-30-charging-sessions-design.md

## Global Constraints
- Preserve charging control, persistent credentials, existing data and unrelated docs/next-patch.md.
- No external device writes or second EVCC source of truth.
- Missing data is not zero; partial energy/cost/provenance are identified.
- IANA timezone-aware periods; entire session belongs to start date.
- No sponsored EVCC code/assets or additional frontend framework.

## Review Focus
- Crash between history and runtime writes: one atomic SQLite transaction, idempotent UUID migration.
- Delayed terminal meter correction after unplug: same historical record, no duplication/resurrection after deletion.
- Missing data/counter resets: partial totals and unknown provenance, never fictitious grid/solar/cost.
- DST and local-midnight boundaries: calendar selection/buckets use installation timezone.
- Mobile charts/tables/modal: touch, keyboard, safe areas, no horizontal page scroll at 320px.

### Task 1: Persistent session repository
**Files:** backend/app/storage/{database.py,charging_sessions.py}, backend/app/runtime/charging.py, tests/backend/test_session_history.py
**Interfaces:** `SessionHistory(store).checkpoint(runtime_sessions, config)` writes history and charging_sessions KV atomically; migration recovers legacy KV once. Historical rows use UUID and public numeric/null fields without VIN/secret/runtime buffers.
- [x] Write/run failing persistence tests for two plugs, paused transactions, reboot, terminal correction, legacy migration, missing meters and zero records.
- [x] Implement additive schema migration, atomic checkpoints, monotonic history lifecycle and safe historical editing.
- [x] Run new tests and existing charging-accounting tests.

### Task 2: Queries, statistics and export API
**Files:** backend/app/sessions/{service.py,export.py,models.py}, backend/app/api/sessions.py, backend/app/main.py, tests/backend/test_sessions_api.py
**Interfaces:** authenticated `/api/v1/charging-sessions` GET returns page + aggregate buckets/groups/options; GET `/{id}`, PATCH vehicle and DELETE completed local rows with explicit confirmation; GET `/export?format=csv|xlsx` uses same validated query.
- [x] Write/run failing tests for weighted totals/unknown source, filters/paging/sorting, month/year/total boundaries including DST, reliable costs/negative tariffs, CSV/XLSX safety, auth and completed-only mutation.
- [x] Implement server-side selection/aggregation with bounded row pages and strict sort/query validation; standard-library exports.
- [x] Generate OpenAPI and TS schema, run API tests.

### Task 3: React sessions interface
**Files:** frontend/src/pages/Sessions.tsx, frontend/src/sessions/{types.ts,model.ts,SessionChart.tsx,SessionTable.tsx,SessionDetail.tsx,SessionBreakdown.tsx}, frontend/src/sessions.css, frontend/src/App.tsx, frontend/src/main.tsx, frontend/src/components/Icon.tsx
**Interfaces:** TypeScript consumes Task 2 contract; page owns filters/period and abortable requests; model derives chart series and stable colors; components render accessible controls and real response fields.
- [x] Write/run failing tests for period rollovers and chart grouping/missing values.
- [x] Implement period/statistic/group controls, stacked chart/tooltips, summary/breakdowns/table/filter/sort/pagination/detail/edit/delete/export.
- [x] Keep loading/error/empty states, request cancellation and no stale-query display.
- [x] Run frontend tests and production build.

### Task 4: Browser validation and review
**Files:** frontend/tests/e2e/sessions.spec.ts, scripts/e2e_server.py (isolated seed only if needed), frontend/playwright.config.ts, docs/features/charging-sessions.md, docs/research/2026-10-30-evcc-sessions.md
- [x] Test real disposable API with seeded real persisted session shape, period/filter/group/detail/export interactions and mobile/desktop layouts in both themes.
- [x] Run full backend/frontend suites, build, schema consistency and browser suite; inspect screenshots.
- [x] Obtain fresh whole-change code review, resolve material findings and re-run affected checks.
- [x] Report completed behavior, recovery limits and validation evidence. Do not publish or deploy without applicable authorization.
