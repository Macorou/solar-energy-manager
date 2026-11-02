# Grouped Settings Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement the tasks inline, then one independent review.

**Goal:** Implement the approved grouped-card settings and global dark/light themes.
**Architecture:** Share existing editors, keep existing API contracts, derive card metrics from LiveState and OCPP connection metadata. Drafts are isolated per opened dialog and only submitted explicitly.
**Tech Stack:** React 19, TypeScript, CSS, Vitest, existing FastAPI API.
**Spec:** docs/superpowers/specs/2026-10-29-grouped-settings-design.md

## Global Constraints

- No new dependencies, backend control changes, secret removal, real-device commands or publication.
- Preserve every existing editable parameter and secret-retention contract.
- Show missing readings as unavailable, never zero or connected by assumption.
- Preserve existing original car and heater illustrations.

## Review Focus

- Dialog save error remains visible and the draft stays open.
- Editing one source retains unrelated settings and credentials.
- Incoming measurements do not reset a user's draft.
- Unavailable telemetry is not rendered as a valid zero or live connection.
- Keyboard focus, small-screen overflow and both themes remain usable.

### Task 1: Global appearance

Files: components/ThemeToggle.tsx, App.tsx, theme.css, main.tsx and ThemeToggle.test.tsx.
Interface: ThemeToggle owns browser-local preference and sets document data-theme; app chrome renders the control on login and authenticated screens.
- [x] Add tests for persisted theme, toggle, and storage unavailable. Run targeted Vitest: expected RED.
- [x] Implement preference and theme tokens. Run targeted test: expected GREEN.
- [x] Apply tokens to existing pages and retain illustrations. Check build.

### Task 2: Grouped settings and shared configuration

Files: pages/Settings.tsx, settings/*.tsx, components/DeviceFields.tsx, pages/Devices.tsx, components/OcppSettings.tsx, api/types.ts, settings.css, SettingsCards.test.tsx and Settings.test.tsx.
Interface: SettingsPage consumes settings, optional LiveState, save, run and connection flags; shares DeviceEditor/VehicleEditor with Devices. Source editors submit unchanged API payloads. Dialogs are native and rendered in a portal outside disabled page fieldset.
- [x] Add tests for live card updates, unavailable metrics, cancel/no writes, source-save preservation, device and vehicle edits, and OCPP URL/secret retention. Run targeted tests: expected RED.
- [x] Extract existing editors and forms; build cards, integration tabs and dialogs around them.
- [x] Keep errors and draft open on rejected save, refresh metadata after credentials save. Run frontend suite: expected GREEN.

### Task 3: Verification and visual review

Files: tests/e2e/settings.spec.ts, approved screenshot outputs under work/ (ignored), this plan's ledger.
Interface: isolated local fixture backend, no production URL or device commands.
- [x] Build frontend, run all frontend tests and relevant backend contract tests; expected successful exit.
- [x] Run browser verification at desktop and 390/320 px for both themes, sources, integrations, keyboard and saved settings.
- [x] Request independent review of the working diff against this spec, fix material findings with regression tests, rerun affected checks.
- [x] Leave changes reviewable locally with evidence and screenshots. No commit/push/deployment unless requested.
