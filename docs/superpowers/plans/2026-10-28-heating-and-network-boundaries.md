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

- [x] Review complete patch on the most capable available reviewer; fix critical/
  important findings in one RED→GREEN pass and record rulings/minors.
- [x] Set version0.1.7; rerun schema/build and required complete suites.
- [x] Publish branch/tag; wait for Python/UI/browser/Docker/private-pull CI success.
- [x] Record verified digest and checks in guide, publish private release asset;
  leave deployment to user. Verify only intended local notes remain untracked.

## Verified result

Release commit d324b6087ba8b5c9a86ae38069e9c0aad02fcbb4, immutable tag v0.1.7.
Workflow40641011085 succeeded: Python181, UI22, browser4 and Docker smoke1,
schema/build/Compose plus private visibility and authenticated digest pull.
Digest sha256:af6b4fbfaa75542b59ff61e56719782d25a79ed7ce14fe8a912cc8e48b0aaf88.
Final independent review: three Important findings reproduced and fixed in one
pass (five RED cases, six additional regressions total); no deferred minors.
Native Windows bookkeeping substituted for Bash path limitations. Network
permission and pending stop now share an atomic document, with safe repeated stop
after restart if still unconfirmed. Hardware commissioning remains user-owned;
distribution checked by CI, unrelated older topics outside scope. No deployment.

Private prerelease published (not draft):
https://github.com/Macorou/solar-energy-manager/releases/tag/v0.1.7
Asset mise-a-jour-portainer-0.1.7.md uploaded, 6226 bytes,
SHA25666ee4457d5a6ccf5e11de0cd4d091efe259355811e8627dab851bb2f4a084891.
