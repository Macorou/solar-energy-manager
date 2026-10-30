# EVCC Sessions — source review and provenance

Reference inspected on 2026-10-30: EVCC commit [`943b17fa958c487768e6be2b636bc5ce78aa5350`](https://github.com/evcc-io/evcc/tree/943b17fa958c487768e6be2b636bc5ce78aa5350).

## Files and observed behavior

- [`assets/js/views/Sessions.vue`](https://github.com/evcc-io/evcc/blob/943b17fa958c487768e6be2b636bc5ce78aa5350/assets/js/views/Sessions.vue): segmented periods, date navigator, icon statistics/grouping, weighted totals, history graph, optional secondary charts, overview and download. Price and CO₂ modes depend on available data. Group colors are stable across period changes. Default table order is descending creation date.
- `PeriodSelector.vue`, `DateNavigator.vue`, `historyChart.ts`, `types.ts`: month/year/total, day/month/year buckets, calendar period bounds, session timestamps/durations/nullable prices. The chart assigns a whole session to its creation date. SEM uses installation IANA timezone consistently instead of browser-local date bucketing.
- `EnergyHistoryChart.vue`: stacked grid/self energy, weighted solar fraction, shared legend, hover/click chart interaction, adaptive scale and right-side axis. SEM keeps a separate unknown-origin series rather than coercing missing solar to grid.
- `CostHistoryChart.vue`: stacked costs by grouping and an additional average price line. Mean price is energy-weighted. SEM excludes incomplete financial coverage from final totals and preserves null in unpriced buckets.
- `EnergyGroupedChart.vue`, `CostGroupedChart.vue`, `AvgCostGroupedChart.vue`: donut totals and energy-weighted group averages. SEM draws native SVG with the existing React stack.
- `SolarGroupedChart.vue`, `SolarYearChart.vue`: weighted solar percentages per group and monthly curves over one or several years. SEM supplies monthly/yearly aggregates directly from the existing SQLite store.
- `SessionTable.vue`, `SessionDetailsModal.vue`, `LegendList.vue`, `echarts.ts`: compact breakpoint-dependent table, optional columns, filters/totals, vehicle assignment, confirm-delete modal, tooltip and legend behavior. SEM retains its own dialog/theme/icon system and adds pagination to bound rendered rows.
- `core/session/{session.go,db.go}`, `core/loadpoint_session.go`: stored session fields and meter finalization, no session persistence when charging never started. SEM preserves zero plug periods internally and hides confirmed empty completed sessions by default, because its existing session lifecycle starts on plug rather than first charge.

Also consulted [charging-session documentation](https://docs.evcc.io/en/features/sessions/) and [REST API documentation](https://docs.evcc.io/integrations/rest-api/operations/getsessions/). SEM has no EVCC connector and controls its own charger; fetching `/api/sessions` from another engine would introduce duplicate histories, so no such connector is added.

## License boundary

EVCC's root [LICENSE](https://github.com/evcc-io/evcc/blob/943b17fa958c487768e6be2b636bc5ce78aa5350/LICENSE) is MIT, copyright evcc.io (andig, naltatis, premultiply). The existing `docs/third-party/evcc-MIT.txt` retains that notice. The inspected [README](https://github.com/evcc-io/evcc/blob/943b17fa958c487768e6be2b636bc5ce78aa5350/README.md) and [exclusions](https://github.com/evcc-io/evcc/blob/943b17fa958c487768e6be2b636bc5ce78aa5350/LICENSES/exclusions.md) explicitly exclude sponsor-required components. None of those components is used for this section; no sponsorship check is bypassed.

The inspected Sessions UI files have no sponsor-required license header. The implementation is newly written Python/React/TypeScript/SVG adapting the information architecture and calculation conventions; it does not import Vue, Bootstrap, ECharts, EVCC fonts, Material Symbols or Shopicons. EVCC's [icon licenses](https://github.com/evcc-io/evcc/blob/943b17fa958c487768e6be2b636bc5ce78aa5350/LICENSES/icons.md) were checked; all rendered icons remain SEM's existing independently drawn SVG path set. No EVCC logos, screenshots or graphical assets are shipped.

The latest mission text mentions two session screenshots but attaches no new session images. Source layout and official documentation were therefore the available visual reference. Browser validation uses an explicitly isolated temporary database, not the installation or any device command.
