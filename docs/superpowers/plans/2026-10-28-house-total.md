# House total Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show total household consumption and allow an optional HA power entity.
**Architecture:** Optional display-only sample through existing HA snapshot;
explicit configured-source precedence, otherwise checked-frame grid+solar total.
**Tech Stack:** Existing Python/FastAPI/React/TypeScript/SQLite/Docker.
**Spec:** `docs/superpowers/specs/2026-10-28-house-total-design.md`

## Global Constraints

- Household total includes charger and heater; do not subtract their meters.
- Keep electrical control/budgets independent of the optional display sensor.
- Preserve configuration/secrets/arming and8090/volume. No production commands or deployment.
- Existing worktree/branch; new immutable private Linuxamd64 release0.1.8.

## Review Focus

- Configured sensor unavailable must not silently switch to calculated total.
- A valid zero is displayed; negatives/nonfinite/unavailable values remain unknown.
- Unchanged old publications checked together are coherent; raw mixed frames are not.
- Invalid optional sensor, including SEM feedback source, must not break grid control.
- Existing settings with no house_entity must keep working and secrets stay unchanged.

### Task 1: Total consumption end to end

**Files:** settings.py, domain/site.py, HA client, coordinator public state;
frontend API types, dashboard.ts/tests, Overview.tsx, Settings.tsx/new test,
new tests/backend/test_house_consumption.py; generated OpenAPI/schema.
**Interfaces:** `house_entity: str=''`, `SiteSnapshot.house: Sample|None=None`
appended to dataclass, `LiveState.house` and `house_configured` optional on client.

- [ ] Write failing frontend tests for total import/export, independence from
  device meters, checked_at pairing, direct sensor0/invalid/no silent fallback.
- [ ] Write failing HA snapshot/public-state tests and form persistence test.
- [ ] Run focused tests and confirm RED for missing behavior.
- [ ] Implement minimal existing-path extension; regenerate schema.
- [ ] Run full Python/UI suites and build, then commit.

### Task 2: Review and private delivery

**Files:** version files, README, docs/deployment/patch-0.1.8.md, output guide.
**Interfaces:** unchanged controls, new private GHCR0.1.8 and verified guide.

- [ ] One fresh independent final review; Important/Critical findings get one
  regression-first fix pass and a full green suite. Record rulings/minors.
- [ ] Version0.1.8, schema/types/build, update browser fixture to total semantics
  and verify new field persistence in existing e2e flow.
- [ ] Push/tag and verify CI Python/UI/browser/Compose/Docker/private-pull.
- [ ] Publish private prerelease guide with exact digest, preserve worktree and
  local commissioning notes; do not deploy Portainer.
