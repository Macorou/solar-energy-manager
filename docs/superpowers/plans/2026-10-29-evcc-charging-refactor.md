# EVCC charging refactor implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace car regulation, OCPP suspension and Peugeot estimation with adapted EVCC behavior and repair OCPP reconnect persistence.

**Architecture:** Keep the Python application, SQLite data, frontend and heater controller. Port the deterministic EVCC algorithms at commit `9404d825d6a659d8ce7f47d3b0d2e14ac04506e0` into focused modules, integrate them with existing scheduling/accounting and the OCPP transport, and preserve the MIT notice.

**Tech Stack:** Python/FastAPI, python-ocpp, SQLite/Fernet, React/TypeScript, pytest/Vitest/Playwright, Docker amd64.

**Spec:** User-approved seven-point summary of 29 October, recorded in `docs/next-patch.md` (last section), and `docs/research/2026-10-29-evcc-{charging-engine,peugeot-soc}.md`. User explicitly authorized starting this patch. Native inline execution is retained from this conversation.

## Global Constraints

- Reuse existing worktree on `feat/v1-energy-manager-impl`, baseline `ab42834`; preserve the local commissioning backlog.
- No live device commands, HA writes or production restarts during development.
- Peugeot measurement dates never select, reject, reanchor or invalidate the effective SoC.
- EVCC estimator starts at 85% efficiency and learns its energy-per-percent gradient. The legacy fixed efficiency field does not control it.
- Actual charging current plus circuit headroom determines the limit; never subtract the same overload from the last command repeatedly.
- Keep physical supply-phase mapping, configurable phase margins, site power limit and minimum 6A/default settings.
- Keep schedule windows, immediate network-window boundary stops and explicit arming. Keep heater behavior and session energy/cost/solar data.
- Suspension normally uses a zero-current OCPP profile with transaction retained. Adapt profiles to Wallbox firmware. Distinguish accepted command from measured charge.
- Retain the five-minute allowance for initial charger measurements; it never postpones correction of a measured overload.
- Authentication secrets stay encrypted under the persistent data directory and are never returned or logged.

## Review Focus

1. Repeated or changed Peugeot percentages with absent, future, reversed or unchanged timestamps must follow the same EVCC estimator results.
2. Identical asynchronous grid/OCPP samples across several ticks must not cause cascading current reductions, while a genuine overload must still reduce/stop below minimum.
3. Pausing with an active OCPP transaction must keep it suspended, not accidentally reauthorize or remote-start it on a renew/reboot.
4. Reconnect with persisted credentials and transaction identity must not require reentry or replay an old start; failed/duplicate authentication must not expose secrets.
5. Multi-load site/phase reservations and existing heater planning must remain effective when a charger is accepted but its physical power lags.

## Task 1: EVCC SoC estimator and session integration

**Files:** Create `backend/app/engine/evcc_soc.py`, `tests/backend/test_evcc_soc.py`; modify `runtime/charging.py`, Peugeot telemetry parsing, vehicle settings/UI and existing accounting tests.

**Interfaces:** `SocEstimator(capacity_kwh)`, `soc(fetched_soc: float|None, charged_energy_wh: float)->float`, serializable state for restart. `ChargingTracker.summary` keeps its public fields. Port the method and vectors from EVCC `core/soc/estimator{,_test}.go`.

- [ ] Write original EVCC vector tests and tracker tests for repeated/changed/missing percentages independent of timestamps, lower API recalage, zero-percent seed and restart without double gains.
- [ ] Run targeted pytest and inspect expected RED assertions.
- [ ] Port the estimator and integrate it, with persisted state scoped to vehicle/plug session. Migrate existing references without using their dates or inventing unobserved energy. Preserve costs and total energy. Remove date-based SoC gates and the old fixed-efficiency input.
- [ ] Run estimator/accounting/Peugeot tests; replace only assertions for deliberately superseded date-based/fixed-efficiency rules. Verify remaining failures rather than weakening unrelated meter checks.
- [ ] Update MIT provenance and commit the allowlisted Task 1 files after green checks.

## Task 2: EVCC car current regulation and reconciliation

**Files:** Create `backend/app/engine/evcc_loadpoint.py`, focused regression tests; modify `phase_limits.py`, `engine.py`, `runtime/coordinator.py`, `runtime/dispatcher.py` and domain telemetry only where needed.

**Interfaces:** Pure PV current/timer controller consuming actual/offered currents and site balance; phase limiter returns power/current for existing command transport. Existing heater decisions and schedule authorizations remain in charge of eligibility and shared allocation.

- [ ] Write failing cases for the observed 20.3A/22.376A/19A incident with repeated ticks, EVCC 5.9A/6A minimum cases, phase mapping and signed export, PV timer start/stop and first-current grace.
- [ ] Verify RED, port `effectiveCurrent`, `pvMaxCurrent` supported fixed-phase path and `ValidateCurrent`/power behavior. Introduce a 30s normal car regulation cadence with immediate explicit/boundary stops; accepted commands update offered state only after transport success.
- [ ] Prefer usable OCPP power/current over delayed HA charger power. Remove strict two-second cross-source ordering and accepted-charger global confirmation gates; maintain independent source freshness and conservative pending allocations.
- [ ] Reconcile charger suspension through fresh native suspended state and telemetry, including active transaction. Accepted cap waiting on the vehicle is not an unknown result solely because power is below the cap. Keep heater confirmation logic.
- [ ] Run phase, budget, cloud, schedule, startup and runtime suites. Commit the allowlisted Task 2 files after green checks.

## Task 3: EVCC OCPP profiles, meter parsing and restart authentication

**Files:** Modify `connectors/ocpp/{profiles,registry,station,metering,server}.py`, `api/devices.py`, `settings.py`, Settings UI, and protocol/API tests.

**Interfaces:** Profiles support 0A and tenths of an amp, TxDefault by default, Wallbox relative/current and firmware-5 variants selected from boot metadata/config override. Protected GET connection metadata reports only saved/connected/error flags, never a secret. Blank credential saves retain existing secrets.

- [ ] Write failing tests for zero-profile suspend/resume preserving transaction, no duplicate RemoteStart, firmware profiles, ordering of periodic/boundary values, local receive freshness, active transaction recovery, and authenticated reconnect using a newly created application and the same data directory.
- [ ] Verify RED, port appropriate EVCC profile and meter behaviors. OCPP profiles use EVCC persistent limits rather than a 90s expiration that can fall back to the hardware maximum. Retain logical arming/authorization; reconcile state before restarting control.
- [ ] Bound dead connection reads, clean owned connections, log sanitized reason codes, preserve encrypted credentials and make saved access visible. Keep active-connection duplicate protection. Do not weaken password verification.
- [ ] Add UI tests for recorded identity/saved-secret status/blank retention. Run protocol and API suites and commit after green checks.

## Task 4: Integration, version, documentation and whole-change review

**Files:** OpenAPI/types if changed, release/deployment docs, version references; regression tests where a cross-component issue requires them.

- [ ] Run complete Python and frontend suites, schema generation and frontend build; run browser smoke and Docker checks where the available environment permits them.
- [ ] Add a release note describing the actual migrated behavior, profile lifetime/offline behavior, retained data, firmware selection and hardware validation still required. Prepare the next image tag consistently, without retagging an old release.
- [ ] Dispatch one fresh reviewer for this patch diff, plan, sources and ledger. Fix important findings in one RED/GREEN pass and rerun affected/full suites as required.
- [ ] Preserve the local-only `docs/next-patch.md`; commit only implementation, tests, source provenance and release documents. Finish with exact verification evidence and publication/deployment state.

## Execution notes

The existing Git Bash skill helpers are known to fail on this Windows workspace.
Use the native PowerShell equivalent for the plan-owned `.superpowers/sdd` ledger
and briefs; do not rerun the broken helpers. Scope review to this patch baseline,
not to previously reviewed commits on the existing long-lived branch.
