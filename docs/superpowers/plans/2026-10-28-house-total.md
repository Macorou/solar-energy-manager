# House total Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

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

- [x] Write failing frontend tests for total import/export, independence from
  device meters, checked_at pairing, direct sensor0/invalid/no silent fallback.
- [x] Write failing HA snapshot/public-state tests and form persistence test.
- [x] Run focused tests and confirm RED for missing behavior.
- [x] Implement minimal existing-path extension; regenerate schema.
- [x] Run full Python/UI suites and build, then commit.

### Task 2: Review and private delivery

**Files:** version files, README, docs/deployment/patch-0.1.8.md, output guide.
**Interfaces:** unchanged controls, new private GHCR0.1.8 and verified guide.

- [x] One fresh independent final review; Important/Critical findings get one
  regression-first fix pass and a full green suite. Record rulings/minors.
- [x] Version0.1.8, schema/types/build, update browser fixture to total semantics
  and verify new field persistence in existing e2e flow.
- [x] Push/tag and verify CI Python/UI/browser/Compose/Docker/private-pull.
- [x] Publish private prerelease guide with exact digest, preserve worktree and
  local commissioning notes; do not deploy Portainer.

## Verified result

Code e24b7ba59dbaac8b5cb5f19e4b86d08cbce323ef, tagv0.1.8.
Workflow40645494184 succeeded: Python194, UI30, browser4, Docker smoke1,
schema/build/Compose and private visibility/authenticated digest pull.
Digest sha256:965f8f6d5ec3730d64c91cac3f81c998db810d6ec0cfacbdeaba23f3aa6bfe37.
One independent review found two Important issues, fixed in one pass with four
RED→GREEN regressions and a full green suite; no deferred minors.
Ruling: shared normalization validates timestamp type and post-conversion
finiteness; invalid optional parsing remains isolated from control. Native
Windows bookkeeping retained. Older unrelated source anomalies remain outside
scope; delivery verified by CI, physical installation not changed by assistant.

Private prerelease published, not draft:
https://github.com/Macorou/solar-energy-manager/releases/tag/v0.1.8
Guide asset4602bytes, SHA2563777b77bf6a21bdd0374d3765899b19a4e04954c30639e5d151ed378172a154a.
