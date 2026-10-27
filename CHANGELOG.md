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

### Changed
- Off-peak days use the list in force on each date. From 2014 the list is
  1/1, 春節 (除夕 to 初五), 2/28, 4/4, 清明, 5/1, 端午, 中秋 and 10/10. From
  2025-09-01 the list adds 除夕前1日, 9/28, 10/25 and 12/25.
- Supported years are 2014–2100. Other years raise `CalendarError`; pass
  `calendar_instance=custom_calendar(...)` for them.
- Tests compare every day of 2014–2027 with Taipower's official
  時間電價日曆表 (`tests/data/taipower_calendar/`).
  Years after 2027 assume the current list stays in force.

### Deprecated
- `cache_dir` and `api_timeout` have no effect and raise a
  `DeprecationWarning`. They will be removed in a future release.

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
