# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-27

### Fixed
- Off-peak days (離峰日) now follow the list in Taipower's 電價表 instead of
  the government office calendar. 補假 and 彈性放假 days are no longer
  off-peak, and listed days that fall on a Saturday are now off-peak. The
  old calendar was wrong on about six days per year, for example
  2026-02-21, 2026-02-27 and 2027-03-01.
- Results no longer depend on network access, the local cache, or whether
  `zhdate` is installed.
- Timezone-aware input is evaluated in Taiwan local time (UTC+8). An
  Asia/Taipei index used to get the previous day's day type, and a UTC index
  used UTC hours and months. For a weekday daytime load this underbilled by
  6–10%. This bug was present in 0.1.0.
- `DatetimeIndex.dayofweek` and string `inferred_freq`, which pandas 4
  removes, are no longer used.
- `calculate_bill` doubles each tier's kWh for two-month bills, as the
  電價表 says. It used one-month tiers before.
- A tiered billing period that spans 夏月 and 非夏月 is priced as Taipower's
  FAQ 請問電費如何計算 does: all of the period's kWh at each season's tiered
  rates, weighted by each season's share of the days. For 610 kWh over
  May–June 2026 on `residential_non_tou` billed every two months, the energy
  cost is now 1316.2 TWD. 0.1.0 gave 1686.7 TWD from `calculate_bill` and
  1263.4 TWD (all at 非夏月 rates) from `TariffPlan.calculate_costs`.
- `calculate_bill_breakdown` no longer fails on usage that spans two seasons,
  and its tiered rows now have costs, one row per season.
- An empty usage series raises `InvalidUsageInput`.
- 底度 for a low-voltage meter over 10 A counts the meter as 10 A, as the
  電價表 says. It multiplied the ampere by 20 (single-phase) or 60
  (three-phase), so an empty house with a 30 A single-phase meter was billed
  1644.3 TWD a month instead of 100 TWD.
- The 100 TWD minimum applies per month, so a two-month bill is at least
  200 TWD. It was 100 TWD for any bill.
- Three-stage plans price weekday 半尖峰 at the weekday price. It used the
  Saturday 半尖峰 price, about half as much. A factory drawing 100 kW on
  weekdays 08:00–18:00 on `high_voltage_three_stage` was billed 90873 TWD
  for July 2026 instead of 143198 TWD. This bug was present in 0.1.0.
- `residential_simple_3_tier` prices non-summer weekday 16:00–22:00 as
  半尖峰 at 4.48 TWD. It used a 尖峰 price of 6.36 TWD that the 電價表 does
  not list, since 簡易型三段式 has 尖峰 only in 夏月. A January bill of
  1 kWh every hour drops from 2501.79 to 2264.91 TWD of energy. This bug was
  present in 0.1.0.
- `low_voltage_power` charges its 4.08 / 3.87 TWD per kWh. Its energy cost
  was always 0, since every hour fell in a period it has no price for.
  This bug was present in 0.1.0.
- 超約 from `demand_kw` is charged. It was always 0, because demand was
  grouped under labels the formula did not look up. This bug was present
  in 0.1.0. The excess now follows the 電價表: 二段式 summer peak leaves
  out only 經常契約, each time leaves out the excess of the times before
  it, the excesses add up, and each is billed at its own contract's rate.
- 功率因數 adjusts the month's bill less the 按戶計收 fee, on every plan.
  Lighting, low-voltage and `high_voltage_ev` plans adjusted the energy
  cost alone, and other high-voltage plans included 按戶計收. The rule is
  added to the 表燈非時間, 簡易型 and `low_voltage_power` plans. The
  `apply_to` field of `power_factor_adjustment` is removed.
- A month with no kWh and no demand pays half the basic fee on the
  標準型, low-voltage and high-voltage plans. The rule was in plans.json
  but never applied, and was missing from the low-voltage plans and
  `high_voltage_ev`.
- 標準型時間電價 charges 按戶計收 (129.10 TWD single-phase, 262.50
  three-phase, chosen by `meter_phase`). It was never charged.

### Changed
- Off-peak days use the list in force on each date. From 2014 the list is
  1/1, 春節 (除夕 to 初五), 2/28, 4/4, 清明, 5/1, 端午, 中秋 and 10/10. From
  2025-09-01 the list adds 除夕前1日, 9/28, 10/25 and 12/25.
- Supported years are 2014–2100. Other years raise `CalendarError`; pass
  `calendar_instance=custom_calendar(...)` for them.
- Tests compare every day of 2014–2027 with Taipower's official
  時間電價日曆表 (`tests/data/taipower_calendar/`).
  Years after 2027 assume the current list stays in force.
- Tests check every price in `plans.json` against the bundled 電價表 text,
  bills at the edges of its rules against amounts worked from that text,
  bills computed two ways that must agree, and the Python examples in the
  README.
- `tests/data/tariff_114_10_01.json` transcribes the 電價表's prices,
  hours, tiers and basic fees with the source line of each number. Tests
  check every plan against it at every half hour.
- The README's over-contract, power factor and bill example sections
  follow the 電價表. `high_voltage_power` and `extra_high_voltage_power`
  are documented as the same as the 二段式 plans, since the 電價表 has no
  高壓 or 特高壓 非時間電價.
- Examples use 2026 dates, which the bundled prices cover.

### Added
- `UncheckedYearWarning`, raised once per year for years after the last
  Taipower calendar this version was checked against (2027). Taipower can
  change the off-peak list, as it did on 2025-09-01.
- `UncheckedPriceWarning`, raised once per process when usage falls before
  2025-10-01, when the bundled 電價表 took effect, or after 2026-12-31, the
  last day Taipower's 電價費率審議會 has decided. Plans built with
  `build_tariff_plan` use the caller's prices and do not raise it.
- `PartialPeriodWarning`, raised by `calculate_bill` and
  `calculate_bill_breakdown` when usage starts or ends mid-month. Bills are
  whole calendar months counted from the first month of usage, while
  Taipower bills from one meter reading to the next, so such bills do not
  match Taipower's.

### Deprecated
- `cache_dir` and `api_timeout` have no effect and raise a
  `DeprecationWarning`. They stay accepted so existing code keeps working.

### Removed
- Holiday downloads from the ruyut/TaiwanCalendar API and the local cache.
- The `platformdirs` dependency and the `lunar` extra (`zhdate`).

## [0.1.0] - 2026-02-06

### Added
- Initial release of Taiwan TOU Calculator
- Support for all 20 Taipower tariff plans
  - Residential: non-TOU, simple 2-tier, simple 3-tier
  - Lighting: non-business tiered, business tiered, standard 2/3-tier
  - Low Voltage: power, 2-tier, 3-stage, EV
  - High Voltage: power, 2-tier, 3-stage, batch production, EV
  - Extra High Voltage: power, 2-tier, 3-stage, batch production
- Flexible plan name matching (English ID, Chinese, bilingual, with/without spaces)
- Taiwan holiday calendar with API fallback
- Energy cost calculation with monthly aggregation
- Full bill calculation (energy cost, basic fee, penalty, power factor adjustment)
- Demand penalty calculation based on 15-minute peak demand
- Custom plan builders for creating custom tariff schedules
- No-pandas convenience functions (`calculate_bill_from_list`, `calculate_bill_from_dict`)
- Bilingual API documentation (English/Chinese)

### Testing
- 364 tests across 12 test modules
- 104 production readiness tests covering:
  - Security & input validation
  - Multilingual & encoding support
  - Extreme scenarios (leap years, century transitions)
  - Data type compatibility
  - API compatibility
  - Concurrency & race conditions
  - Resource management
  - Documentation examples
  - Boundary values
  - Error recovery
  - Performance benchmarks
  - Version compatibility
- Accuracy validation against Taipower official rates
- Stress tests (5M+ records, concurrent access, memory stability)
- End-to-end tests simulating real-world scenarios

### Documentation
- Comprehensive README with bilingual quick start tutorial
- API documentation (English and Chinese)
- Calculation logic background with formulas
- Performance benchmarks and optimization tips

### Development Status
- Python 3.9-3.13 support
- CI/CD with GitHub Actions (tests on Python 3.9, 3.10, 3.11, 3.12, 3.13)
- Pre-commit hooks for code quality (ruff, mypy)
- MIT License

### Release Notes
- First stable release
- Published to PyPI
