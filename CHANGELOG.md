# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-28

### Upgrading from 0.1.0
Most bills change, so compute results stored from 0.1.0 again. The sections
below give the details.

Bills that change the most:
- 超約 from `demand_kw` was always 0 and is now charged.
- Three-stage plans priced weekday 半尖峰 at about half its price. A factory
  drawing 100 kW on weekdays 08:00–18:00 on `high_voltage_three_stage` pays
  143198 TWD of energy for July 2026 instead of 90873.
- `low_voltage_power` billed no energy and now does.
- Timezone-aware usage is priced in Taiwan time. A weekday daytime load in
  July 2026 came out 5–9% low with an `Asia/Taipei` index and 9–43% low
  with a UTC index.
- Off-peak days follow the 電價表's list. The office calendar 0.1.0 used was
  wrong on about six days a year.
- 高壓 and 特高壓 bills for May and October pay each season for its share of
  the days. This alone makes a simulated factory pay 1.9% more in May and
  2.9% less in October.
- Bills round as Taipower's do. Reading kWh to the whole kWh moved the
  monthly bills we measured by 0 to 3 TWD.
  `BillingInputs(taipower_rounding=False)` keeps the unrounded amounts.

Code that may stop working:
- `high_voltage_power` and `extra_high_voltage_power` are removed. Use
  `high_voltage_2_tier` and `extra_high_voltage_2_tier`, which bill the same.
- A `BillingInputs` value no bill can have raises `InvalidBillingInput`, a
  `ValueError`. Pass `power_factor` in percent, 95 and not 0.95.
- Two readings at one timestamp, or an empty series, raise
  `InvalidUsageInput`.
- An unknown or ambiguous plan name raises `UnknownPlanError` with a new
  message. It is still a `ValueError` and a `KeyError`.
- Years outside 2014–2100 raise `CalendarError`.
- `get_period`, `get_context` and `TaiwanCalendar.is_holiday` no longer have
  `.register`.
- The `lunar` extra and the `platformdirs` dependency are gone. `cache_dir`
  and `api_timeout` do nothing and warn.

New warnings name the caller's line. They are `PartialPeriodWarning` for
usage that starts or ends mid-month, `UncheckedPriceWarning` for dates the bundled
電價表 does not cover, `UncheckedYearWarning` after 2027, and warnings for
time-of-use usage coarser than an hour, two-month bills with a 契約容量 and
`contract_capacities` keys the plan does not bill.

To optimize a bill, use `taipower_rounding=False`. 最高需量 still counts
whole kW with it, so the bill steps at each kW of demand.

### Fixed
- Timezone-aware input is priced in Taiwan time (UTC+8), a single
  `datetime` as well as a `DatetimeIndex`. An `Asia/Taipei` index took each
  day's day type from the day before, and UTC input used UTC hours and
  months. 2026-07-13 01:00 UTC, 09:00 on a Monday in Taiwan, was 離峰 at
  2.06 TWD on `residential_simple_2_tier` instead of 尖峰 at 5.16.
- Off-peak days (離峰日) follow the list in Taipower's 電價表 instead of the
  government office calendar. 補假 and 彈性放假 days are not off-peak, and a
  listed day that falls on a Saturday is. The office calendar was wrong on
  about six days a year, for example 2026-02-21, 2026-02-27 and 2027-03-01.
  Results no longer depend on network access, a local cache or `zhdate`.
- `DatetimeIndex.dayofweek` and string `inferred_freq`, which pandas 4
  removes, are no longer used.
- An ID or plan name matches exactly, ignoring case and surrounding spaces,
  before part of a longer name does, so `plan(p.name)` finds `p` for every
  plan. `高壓電力-二段式時間電價` and `" HIGH_VOLTAGE_2_TIER "` named no
  plan. The six names the README gave that matched no plan, such as
  表燈標準二段式 and 高壓電動車充電, now name their plans.
- `calculate_bill` and `calculate_bill_breakdown` leave the `BillingInputs`
  they are given unchanged. They wrote the plan's default
  `billing_cycle_months` into it, so a `BillingInputs` used once for
  `residential_non_tou` billed every later plan in two-month bills. A July
  `residential_simple_2_tier` bill with 1 kWh at 尖峰 came to 155.16 TWD for
  July and August instead of 80 TWD for July.
- `contract_capacity_kw` is the 經常契約, `contract_capacities["regular"]`.
  Given alone, it billed no basic fee, so a 200 kW `high_voltage_2_tier`
  contract paid none of its 44720.0 TWD for July.
- `BillingInputs.for_lighting_standard` keeps `phase` and passes
  `contract_kw` as `contract_capacities["regular"]`, so a three-phase bill
  pays the three-phase 按戶計收 and demand within the contract pays no 超約.
- `BillingInputs.for_residential` gives no `basic_fee_inputs` for one
  household, so strict mode accepts it on `residential_non_tou`. It raised
  `InvalidBasicFeeInput`.
- Every contract in `contract_capacities` is optional. Strict mode accepts a
  裝置契約 bill on `low_voltage_2_tier`, which raised `MissingRequiredInput`,
  and a bill with some of its plan's contracts no longer warns "Formula may
  require contract_capacities keys".
- An empty usage series raises `InvalidUsageInput` from every entry point
  instead of an error from inside pandas. `float32` usage is billed in
  `float64`, so its drift does not move an amount cut to the 角.
- Three-stage plans price weekday 半尖峰 at the weekday price. They used the
  Saturday price, about half as much, so a factory drawing 100 kW on
  weekdays 08:00–18:00 on `high_voltage_three_stage` paid 90873 TWD of
  energy for July 2026 instead of 143198.
- `residential_simple_3_tier` prices non-summer weekday 16:00–22:00 as
  半尖峰 at 4.48 TWD. It used a 尖峰 price of 6.36 TWD, but 簡易型三段式 has
  尖峰 only in 夏月. `costs` of 1 kWh every hour of January 2026 drops from
  2501.79 to 2264.91 TWD.
- `low_voltage_power` charges 4.08 TWD per kWh in 夏月 and 3.87 otherwise.
  Its energy cost was always 0, since every hour fell in a period it had no
  price for.
- A two-month bill doubles each tier's kWh and starts the 簡易型 1.04 TWD
  加計 at 4000 kWh, as the 電價表 does for 隔月抄表. It used one month's
  limits, so 2200 kWh in each month paid 2496.0 TWD of 加計 instead of
  416.0.
- A tiered bill that spans 夏月 and 非夏月 is priced as Taipower's FAQ
  請問電費如何計算 does. All of its kWh are priced at each season's tiered
  rates, weighted by each season's share of the days. For 610 kWh over
  May–June 2026 on `residential_non_tou`, `calculate_bill` gives 1316.1 TWD
  of energy, and `TariffPlan.calculate_costs`, which does not round,
  1316.17. 0.1.0 gave 1686.7 and 1263.4, all at 非夏月 rates.
  `calculate_bill_breakdown` no longer fails on such usage and lists one
  priced tiered row per season.
- Every meter under 1000 V has the 低壓 底度, a meter over 10 A counts as
  10 A, and `meter_phase` is read ignoring case. 0.1.0 multiplied the
  ampere by 20 (single-phase) or 60 (three-phase), so an empty January on a
  30 A single-phase meter cost 1644.3 TWD instead of the 100 TWD minimum.
  A 380 V meter or `meter_phase="Three"` had none. A meter no 底度 rule
  covers warns.
- The 100 TWD minimum applies per month, so a two-month bill is at least
  200 TWD. It was 100 TWD for any bill.
- A month whose meter reads no kWh and no 最高需量 pays half the basic fee
  on 標準型, 低壓, 高壓 and 特高壓 plans, as the 電價表 says. 0.1.0 never
  applied the rule. A given `over_contract_kw` counts as a 最高需量. A 裝置契約 bill
  reads its 尖峰 kWh alone, so a 21 kW 裝置契約 month with only Sunday kWh
  pays 1496.2 TWD of basic fee.
- A bill pays one 按戶計收 fee, the one for its contract type and meter
  phase, and 標準型時間電價 now pays it (129.10 TWD single-phase, 262.50
  three-phase). A `low_voltage_2_tier` bill without `contract_capacities`
  paid both 105.00 and 262.50 TWD, and its 需量契約 bill paid the 105.00 of
  a 裝置契約.
- 超約 from `demand_kw` is charged. It was always 0, because demand was
  grouped under labels the formula did not look up. The excess follows the
  電價表. 二段式 夏月 尖峰 is over 經常契約 alone, each time leaves out the
  excess of the times before it, the excesses add up, and each is billed at
  its own contract's price. In the package's reading, the 2x part is up to
  10% of the contracts each time's excess is over, less the kW earlier
  times counted, so 10 kW over a 300 kW 週六半尖峰契約 pays 894 TWD.
- `demand_kw` is read as Taipower reads 需量. It is read on its own
  timestamps in Taiwan time, readings finer than 15 minutes are averaged
  over each quarter hour (營業規章 第三條), and 最高需量 counts whole kW
  (施行細則 第二十八條). So 230, 200 and 200 kW in one quarter hour on a
  200 kW contract are 10 kW over, and 205.9 kW is 5 kW over.
- A 裝置契約 bill pays no 超約. It warns when 最高需量 passes the 裝置契約 kW,
  since Taipower then bills 需量契約電價 at a 契約容量 the 電價表 does not
  give.
- `low_voltage_power` bills a 需量契約 per kW of 經常 and 非夏月契約 and
  charges its 超約. It ignored `contract_capacities`.
- A contract for 週六半尖峰 or 離峰 time alone follows 電價表 第八章
  二(一)8. Use at the times it does not cover pays 4.8 times that time's basic fee and
  1.6 times its energy price instead of 超約.
- 高壓 and 特高壓 months that straddle 5/16 or 10/16 pay each season's basic
  fee and 超約 for its share of the days, as a mid-month price change does
  (營業規章 第二十七條, 施行細則 第三十六條). In the package's reading, each
  part is billed on its own highest demand.
  The whole month took its 1st day's season, so with 200 kW 經常契約 and 50
  kW 非夏月契約 on `high_voltage_2_tier`, May 2026 paid 41725.0 TWD of basic
  fee instead of 43270.8. Two-month bills over the 6/1 or 10/1 edge are
  weighted the same way.
- 功率因數 adjusts the bill less its 按戶計收 fee, and only on the bills the
  電價表 names. These are three-phase 表燈 bills (標準型 with a contract of
  20 kW or more), three-phase 低壓 bills with a 20 kW 裝置契約 or a 30 kW
  需量契約, and every 高壓 and 特高壓 bill. 0.1.0 adjusted any bill given a
  `power_factor`, on lighting, 低壓 and `high_voltage_ev` plans the energy
  cost alone. The 表燈非時間, 簡易型 and `low_voltage_power` plans gain the
  rule, and `power_factor_adjustment` loses its `apply_to` field.
- Below 80% 功率因數 the 超約 fee is adjusted too (施行細則 第三十條), and a
  month with no kWh gets no adjustment, even when it pays a 底度
  (第三十八條).
- `high_voltage_ev` uses the 6/1–9/30 夏月 of the 低壓 table it is 95% of,
  not 5/16–10/15. For 100 kW all day on a 200 kW contract, this alone takes
  May 2026 from 324865 to 317132 TWD.
- `high_voltage_ev` pays 95% of the 低壓 bill after that bill is rounded to
  the 元, as page 16 of Taipower's 各類電價表及計算範例 (114/10/1) does,
  89,729元×95%=85,243元. 0.1.0 took 95% of every price, which gives
  85,242 TWD for that bill. The bill lists the 低壓 amounts and
  `adjustment` takes the 5% off. `pricing_context` and `calculate_costs`
  still give 95% prices.
- The README's plan tables, 簡易型二段式 schedule, 高壓 夏月, 超約, 功率因數
  and bill examples follow the 電價表 and the code.

### Changed
- `calculate_bill` and `calculate_bill_breakdown` raise `InvalidBillingInput`
  for a `BillingInputs` value no bill can have, with or without
  `strict=True`. These are a negative, NaN or infinite contract,
  `basic_fee_inputs` value, `over_contract_kw` or `meter_ampere`, a
  `demand_adjustment_factor` of 0 or less, a `power_factor` that is NaN,
  over 100, or 1 or less, a `billing_cycle_months` other than 1, 2 or
  `None`, a `meter_phase` other than single or three, and a
  `contract_capacity_kw` that differs from `contract_capacities["regular"]`.
  They were billed, so a `power_factor` of 0.95, meant as 95%, added 3804.96
  TWD to a 200 kW `high_voltage_2_tier` July bill instead of taking 722.0
  off. A bad `basic_fee_inputs` value raises `InvalidBasicFeeInput`, which
  is now an `InvalidBillingInput`.
- A `contract_capacities` key the plan does not bill, such as `"regualr"`,
  warns and is left out, and `strict=True` raises `InvalidBillingInput`. It
  was left out without a word.
- Two readings at one timestamp raise `InvalidUsageInput`, in `usage` from
  every entry point and in `demand_kw` from `calculate_bill` and
  `calculate_bill_breakdown`. Both readings were billed.
- `calculate_bill` warns for a two-month bill with a 契約容量, since Taipower
  bills those every month on 當月最高需量. It also warns for time-of-use
  usage whose timestamps step by more than an hour, which it prices at the
  period of each timestamp. 24 kWh a day in July on
  `residential_simple_2_tier` costs 1532.6 TWD of energy as daily data, all
  at 00:00's 離峰 price, and 2602.1 TWD as 1 kWh an hour.
- `calculate_bill_breakdown`'s `basic_details` has `season` and `share`
  columns, and lists each fee once for each season of a bill that spans two.
- `get_period`, `get_context` and `TaiwanCalendar.is_holiday` are plain
  functions instead of `functools.singledispatch` ones. They accept the same
  types as before.
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
  2025-09-01 it adds 除夕前1日, 9/28, 10/25 and 12/25. Supported years are
  2014–2100, and other years raise `CalendarError` from every entry point.
  Pass `calendar_instance=custom_calendar(...)` for them.
- Tests compare every day of 2014–2027 with Taipower's 時間電價日曆表
  (`tests/data/taipower_calendar/`), and years after 2027 assume the current
  list stays in force. They check every price and hour in `plans.json`
  against the bundled 電價表 at every half hour, through
  `tests/data/tariff_114_10_01.json`, which gives the source line of each
  number. They also bill Taipower's 計算範例 and check bills at the edges of
  each rule, bills computed two ways that must agree, and the Python
  examples in the docs.
- `tests/data/clauses/` splits the 電價表's 第三、四、五、八章 and every
  chapter of 營業規章 and 營業規章施行細則 into clauses. Each clause that
  changes a bill names its tests, and the others say why no bill depends on
  them. Rules with no input in this package, such as 免計營業稅 or
  儲冷式空調, are expected failures.
- `docs/references/` keeps the Taipower documents the tests cite beyond the
  電價表, with their sources and sha256.
- Examples use dates the bundled prices cover.

### Added
- `UnknownPlanError`, raised for a plan name that matches no plan or more
  than one, a removed plan, and a plan that is not a string (`None` raised
  `AttributeError`). It is a `PowerKitError`, and also the `ValueError` and
  `KeyError` that `plan` and `calculate_bill` raised before.
- `InvalidBillingInput` is exported from `taipower_tou`.
- `UncheckedYearWarning`, raised once per year for years after 2027, the
  last Taipower calendar this version was checked against. Taipower can
  change the off-peak list, as it did on 2025-09-01.
- `UncheckedPriceWarning`, raised once per process for usage before
  2025-10-01, when the bundled 電價表 took effect, and once for usage after
  2026-12-31, the last day Taipower's 電價費率審議會 has decided. Plans built
  with `build_tariff_plan` use the caller's prices and do not raise it.
- `PartialPeriodWarning`, raised by `calculate_bill` and
  `calculate_bill_breakdown` on each bill whose usage starts or ends
  mid-month. Bills are whole calendar months counted from the first month
  of usage, while Taipower bills from one meter reading to the next, so
  such a bill does not match Taipower's.

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
