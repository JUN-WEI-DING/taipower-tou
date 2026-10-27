# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-27

### Fixed
- A timezone-aware single `datetime` is priced in Taiwan time by `period_at`,
  `period_context`, `pricing_context`, `get_period` and `get_context`, as a
  `DatetimeIndex` already was. 2026-07-13 01:00 UTC, 09:00 on a Monday in
  Taiwan, was 離峰 at 2.06 TWD on `residential_simple_2_tier` instead of
  尖峰 at 5.16 TWD.
- `TariffPlan.calculate_costs` and `costs` raise `CalendarError` for tiered
  plans in years outside 2014–2100, as `calculate_bill` and
  `monthly_breakdown` do. They priced 2013 and 2101 without a word.
- `UncheckedYearWarning`, `UncheckedPriceWarning` and the `cache_dir` /
  `api_timeout` `DeprecationWarning` name the caller's line. They named a line
  inside the package or in `functools`, and Python's default filter hid the
  `DeprecationWarning`.
- `plan(p.name)` finds `p` for every plan. An exact ID or name wins over part
  of a longer name. `高壓電力-二段式時間電價` also matched
  `extra_high_voltage_2_tier` and raised an ambiguity error.
- Plan IDs, names and the removed-plan hints match ignoring case and
  surrounding spaces, so `" HIGH_VOLTAGE_POWER "` names `high_voltage_2_tier`.
- The README's plan tables give the names `available_plans()` returns. Six of
  the names they gave matched no plan: 表燈非營業（累進）, 表燈營業（累進）,
  表燈標準二段式, 表燈標準三段式, 低壓電動車充電 and 高壓電動車充電. They are
  accepted as other names for their plans.
- The README's 簡易型二段式 schedule follows the 電價表: weekday 尖峰 is
  09:00–24:00 in 夏月 and 06:00–11:00 and 14:00–24:00 otherwise, and
  Saturdays are 離峰 all day. It showed 07:00–23:00 and a Saturday 半尖峰 at
  3.19 TWD that the plan does not have.
- The README gives 高壓 and 特高壓 plans their 5/16–10/15 夏月 and says that
  `UncheckedPriceWarning` is raised once for usage before 2025-10-01 and once
  more for usage after 2026-12-31. It also says that each timestamp labels
  the start of its interval and that a bill does not change the
  `BillingInputs` it is given.
- `demand_kw` finer than 15 minutes is averaged over each quarter hour, as
  營業規章 第三條 defines 需量. The highest 5-minute reading was billed as
  the month's demand before. Readings of 230, 200 and 200 kW on a 200 kW
  contract paid 15652 TWD of 超約 instead of 4472.
- `demand_kw` is read on its own timestamps, in Taiwan time. It was
  reindexed to the timestamps of `usage`, so hourly usage dropped every
  15-minute reading off the hour, and demand in another timezone than the
  usage was dropped altogether. 220 kW at 14:15 on a 200 kW
  `high_voltage_2_tier` contract paid no 超約 instead of 8944.0 TWD, with
  hourly usage or with usage and demand in different timezones.
- 高壓 and 特高壓 months that straddle 5/16 or 10/16 pay each season's basic
  fee and 超約 for that season's share of the days, as a mid-month price
  change does (營業規章 第二十七條, 營業規章施行細則 第三十六條). The whole
  month took its 1st day's season before. With 200 kW 經常契約 and 50 kW
  非夏月契約 on `high_voltage_2_tier`, 260 kW at 尖峰 on a 非夏月 day and
  215 kW on a 夏月 day, May 2026 pays 43270.8 TWD of basic fee instead of
  41725.0 and 5077.3 of 超約 instead of 3338.0, and October pays 43174.1
  instead of 44720.0 and 4968.6 instead of 35776.0. A simulated factory
  month on a 280 kW 經常契約 totals 1.9% more for May and 2.9% less for
  October. Two-month bills over the 6/1 or 10/1 edge are weighted the
  same way.
- A month with no use is told apart as the 電價表 and 第三十八條 say. 底度
  billed on an empty month is not use, so 功率因數 leaves it alone; an empty
  30 A three-phase house on `residential_non_tou` paid 2.1 TWD more for
  January and February at 70% and 3.2 less at 95%. `over_contract_kw`
  above 0 is use, so the month pays the whole basic fee; it paid half. A
  reading under 1 kW is 0 kW, so a
  month with no kWh and a 0.6 kW reading pays half; it paid the whole fee.
  A 裝置契約 bill halves on its 尖峰 kWh alone, so 4 kW of demand in a month
  without 尖峰 kWh no longer makes it pay 2992.5 TWD instead of 1496.2.
- The warning that demand passed the 裝置契約 compares whole kW of the
  15-minute 最高需量, so 10.9 kW no longer passes a 10 kW 裝置契約.
- Every meter under 1000 V has the 低壓 底度, including the three-phase
  380 V meters 表燈 is supplied at (第三章 二). They had none, so an empty
  July on `residential_non_tou` with a 30 A meter paid the 100 TWD minimum
  instead of 60 kWh at 1.78, 106.8 TWD. A meter no 底度 rule covers warns
  instead of being billed without one in silence.
- A two-month 簡易型 bill pays the 1.04 TWD 加計 on its kWh over 4000, 2000
  for each month, as tiered bills double their tiers. 2000 kWh in each
  month paid 2080.0 TWD of 加計 instead of none, and 2200 kWh in each paid
  2496.0 instead of 416.0.
- `float32` usage is billed in `float64`. Its sums drifted, so 5005 kWh in a
  month on `residential_simple_2_tier` paid 3125.1 TWD of 加計 instead of
  3125.2.
- `PartialPeriodWarning` is raised on every partial bill. It was raised once
  per date range, so a second customer read on the same days got no
  warning.
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
- A bill pays one 按戶計收 fee, the one for its contract type and meter
  phase. A bill without `contract_capacities` paid every 按戶計收 fee of
  its plan, for example 105.00 + 262.50 TWD on `low_voltage_2_tier`, and
  a `low_voltage_2_tier` 需量契約 bill paid the 裝置契約 105.00 TWD
  instead of 262.50 TWD.
- 功率因數 adjusts only the bills the 電價表 names: three-phase 表燈 bills
  (標準型 with a contract of 20 kW or more), three-phase 低壓 bills with a
  20 kW 裝置契約 or a 30 kW 需量契約, and every 高壓 bill. Any bill given a
  `power_factor` was adjusted.
- Below 80% 功率因數 the 超約 fee is adjusted too, and a month with no kWh
  gets no 功率因數 adjustment, as Taipower's 營業規章施行細則 第三十、三十八條 say.
  最高需量 counts whole kW (第二十八條), so 205.9 kW on a 200 kW contract
  is 5 kW over.
- `low_voltage_power` bills a 需量契約 per kW of 經常 and 非夏月契約 and
  charges its 超約. `contract_capacities` were ignored and demand was
  never checked.
- A 裝置契約 bill with `demand_kw` pays no 超約. It was charged against a
  0 kW contract, so a 9 kW demand on a 10 kW 裝置契約 added 6377 TWD.
  When demand passes the 裝置契約 kW the bill warns, since Taipower moves
  it to 需量契約電價 at a contract the 電價表 does not give.
- Contracts for 週六半尖峰 or 離峰 time alone follow 第八章 二(一)8. Use
  at other times pays 4.8x that time's basic fee and 1.6x its energy
  price instead of 超約, and 10% of the contract is taken of the contract
  each time's excess is over. 10 kW over
  a 300 kW 週六半尖峰 contract was 1341 TWD and is now 894 TWD.
- `high_voltage_ev` uses the 6/1–9/30 夏月 of the 低壓 table it is 95% of.
  It used the 5/16–10/15 of the other 高壓 tables. For 100 kW all day on a
  200 kW contract, May 2026 drops from 323629.4 to 317131.4 TWD and
  October from 336317.6 to 327665.0 TWD.
- `high_voltage_ev` pays 95% of the 低壓 bill after that bill is rounded
  to the 元, as page 16 of Taipower's 各類電價表及計算範例 (114/10/1) does,
  89,729元×95%=85,243元. Every price was 95% before, so the page's 280 kW
  bill with 25,000 off-peak kWh came to 85,242 TWD instead of 85,243. The
  bill now lists the 低壓 amounts and `adjustment` takes the 5% off.
  Unrounded totals, `pricing_context` and `calculate_costs` are unchanged.

### Changed
- `calculate_bill_breakdown`'s `basic_details` has `season` and `share`
  columns, and lists each fee once for each season of a bill that spans
  two.
- `get_period`, `get_context` and `TaiwanCalendar.is_holiday` are plain
  functions instead of `functools.singledispatch` ones, so they no longer have
  `.register`. They accept the same types as before.
- `calculate_bill` and `calculate_bill_breakdown` round as Taipower bills
  (營業規章施行細則 第二十八、二十九條). Each bill's kWh are read to the whole
  kWh, half up, each item is cut to the 角, 功率因數 is worked from the cut
  items, and the total is rounded half up to the 元. A time-of-use bill
  reads each of 尖峰, 半尖峰, 週六半尖峰 and 離峰 on its own, the package's
  reading of 第二十八條. A `low_voltage_2_tier` July bill with 38 kWh at 尖峰
  and a 10 kW 裝置契約 totals 1691 TWD instead of 1690.52.
  `BillingInputs(taipower_rounding=False)` keeps the unrounded kWh and
  amounts. `TariffPlan.calculate_costs` does not round.
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
- `tests/data/clauses/` splits the 電價表's 第三、四、五、八章 and the
  第四章 of 營業規章 and of 營業規章施行細則 into clauses. Each clause that changes a bill names its tests,
  and the others say why no bill depends on them. Rules with no input in
  this package, such as 免計營業稅 or 儲冷式空調, are expected failures.
- `docs/references/` keeps the Taipower documents the tests cite beyond
  the 電價表, with their sources and sha256.
- The README's over-contract, power factor and bill example sections
  follow the 電價表.
- Examples use 2026 dates, which the bundled prices cover.

### Added
- `UnknownPlanError`, raised for a plan name that matches no plan or more than
  one, a removed plan, and a plan that is not a string (`None` raised
  `AttributeError`). `plan`, `calculate_bill`, `get_plan_requirements` and
  `TariffFactory` raise it. It is a `PowerKitError`, so the README's
  `except PowerKitError` example catches it, and also a `ValueError` and a
  `KeyError`, which `plan` and `calculate_bill` raised before. Its message no
  longer starts with "Unsupported plan name".
- `InvalidBillingInput` is exported from `taipower_tou`.
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
- `high_voltage_power` (高壓電力) and `extra_high_voltage_power` (特高壓電力).
  The 電價表 has no 高壓 or 特高壓 非時間電價, and 0.1.0 billed them exactly as
  `high_voltage_2_tier` and `extra_high_voltage_2_tier`. Asking for one
  raises an error that names the 二段式 plan to use.
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
