# Planning and energy flow implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** Ship both approved graphical changes to GitHub.
**Architecture:** Existing React/API contracts, pure energy balance model plus accessible flow component, draft planning form and device commissioning component in Settings.
**Tech Stack:** React, TypeScript, CSS, Vitest, Playwright, existing Python API.
**Spec:** ../specs/2026-10-29-planning-flow-design.md

## Global constraints
- No engine changes or real device commands; preserve credentials, arming and unrelated configuration.
- One flow bar, import gray / local solar green / export yellow; output markers use total device consumption.
- Icon-only markers; four navigation entries; mobile 320px and both themes.

## Review focus
- Missing/unusable readings must never become zero or a fabricated solar split.
- Multiple devices/programs and weekday HC settings remain editable and persist independently.
- A polling refresh must not replace a user’s draft; saved edits must merge untouched latest configuration.
- Failed saves and validation must retain drafts and show actionable errors.
- Connection tests/arming must remain explicit and retain backend protections after navigation removal.

### Task 1 — Energy flow and overview
- [x] Add failing energy-balance/component tests: mixed import, export, night with active consumers, unknown/inconsistent samples, icon-only markers.
- [x] Implement pure model and component; replace overview statistics/phases; preserve controls and Settings links.
- [x] Run focused tests and frontend suite.

### Task 2 — Planning and consolidated navigation
- [x] Add failing tests for draft save, multiple programs/windows, priorities/cloud settings, arming checks from Settings.
- [x] Implement Planning cards/table with existing Settings save API, shared commissioning component and four-entry navigation.
- [x] Run focused tests, frontend suite/build, backend suite; adapt browser workflows to approved navigation.

### Task 3 — Review, browser validation and push
- [x] Review desktop/mobile in both themes, dynamic flow scenarios and real test-server configuration persistence.
- [x] Independent whole-change code review; fix material findings with regression checks.
- [ ] Commit only these two graphical changes and documentation; preserve docs/next-patch.md.
- [ ] Push current branch to origin, verify remote commit and CI; report actual publication state.
