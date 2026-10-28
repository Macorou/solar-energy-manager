# Heating and network boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship the three approved changes together as private version 0.1.7.

**Architecture:** Keep one budget engine. Carry immutable effective setpoints in
commands, pair checked HA readings for confirmation, persist effective grid
permission for explicit boundary stops. Extend existing configuration and cards.

**Tech Stack:** Python/FastAPI/Pydantic/SQLite, React/TypeScript/Vitest, Docker/GHCR.

**Spec:** `docs/superpowers/specs/2026-10-28-heating-and-network-boundaries-design.md`

## Global Constraints

- Preserve secrets, activation, existing temperature, priorities, power limits and artwork.
- No real device commands, HA changes, Portainer deployment or merge to main.
- Private Linux amd64 image; immutable new tag 0.1.7, existing worktree/branch.
- Keep strict new physical power evidence for starts and native evidence for stops.

## Review Focus

- An old nonzero power rechecked after a new start must not confirm its effect.
- Solar target above network target must remain reachable after 55 °C.
- Setpoint-only updates while heating must not require a fictitious wattage jump.
- A pending start or process restart at a network boundary must not escape the stop.
- Overlapping network permissions and manual mode must not cause false tariff stops.

### Task 1: Confirmation clock and waiting reason

**Files:** Modify `backend/app/runtime/dispatcher.py`, `backend/app/engine/budget.py`,
`backend/app/engine/engine.py`; create `tests/runtime/test_async_confirmation.py`.

**Interfaces:** `Sample.availability_at` pairs checked frames; expose
`measurements_coherent(snapshot) -> bool` separately from transition blocking.

- [x] Write tests: provider dates 11 s apart with equal current checks confirm;
  old effect, invalid checks and raw mixed frames do not; coherent pending frame
  reports confirmation waiting, not incoherent measurements.
- [x] Run `python -m pytest tests/runtime/test_async_confirmation.py -q` (RED).
- [x] Implement pairing and reason, retaining source measurement > sent for starts.
- [x] Run focused confirmation/manual-cycle/coordination tests (GREEN).
- [x] Commit this tested unit.

### Task 2: Explicit network boundary stops

**Files:** Modify `backend/app/engine/engine.py`, `backend/app/runtime/coordinator.py`,
`backend/app/scheduling/authorization.py`; create `tests/runtime/test_network_boundaries.py`.

**Interfaces:** Engine `network_allowed: dict[str,bool]` and pending boundary stops,
persisted atomically in one `runtime_network_state` document. Effective grid permission is independent of
temporary equipment eligibility and unioned across applicable charge programs.

- [x] Write tests for both device kinds: permission loss immediately emits one
  suspend despite cloud/min-run delays and even with solar; subsequent restart
  waits for observed stop; persist/restart, pending start, midnight, overlaps,
  manual and unarmed cases.
- [x] Run new file (RED).
- [x] Implement transition detection/reset of solar start stability and persistence.
- [x] Run new file and scheduling/cloud/allocation suites (GREEN).
- [x] Commit this tested unit.

### Task 3: Dual heater targets end to end

**Files:** Modify settings, domain/commands, engine/policies, engine, dispatcher,
coordinator, Ariston adapter/API, Devices form, DeviceCard/API types and generated
schema. Create `tests/runtime/test_heater_targets.py` and `frontend/src/pages/Devices.test.tsx`;
extend Ariston and card tests.

**Interfaces:** `DeviceConfig.solar_target: float|None`, `DevicePolicy.solar_target`,
`CommandIntent.target_temperature: float|None`, action `set_temperature` for
setpoint-only control. DecisionBatch exposes effective targets and target sources;
public state exposes `effective_target` and `target_source` per device.

- [x] Write tests for preserved legacy configuration, 55/70 grid/solar choice,
  stable surplus in HC, target reached above 55, cloud tolerance then network55,
  manual55, priorities, immutable command target and setpoint-only confirmation.
- [x] Write tests for native rejection outside bounds and no power replay on
  setpoint-only command; form saves both values and card shows effective target.
- [x] Run new focused tests (RED).
- [x] Implement through existing paths, checking native bounds and cooldown.
- [x] Regenerate OpenAPI/types; run complete Python/UI suites and production build (GREEN).
- [x] Commit this tested unit.

### Task 4: Review and private release

**Files:** Version files, README, `docs/deployment/patch-0.1.7.md` and output guide.

**Interfaces:** One fresh final code review, tests before immutable tag and push.

- [ ] Review complete patch on the most capable available reviewer; fix critical/
  important findings in one RED→GREEN pass and record rulings/minors.
- [ ] Set version0.1.7; rerun schema/build and required complete suites.
- [ ] Publish branch/tag; wait for Python/UI/browser/Docker/private-pull CI success.
- [ ] Record verified digest and checks in guide, publish private release asset;
  leave deployment to user. Verify only intended local notes remain untracked.
