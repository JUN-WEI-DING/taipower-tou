# taipower_tou API 說明

本文件列出 `taipower_tou` 匯出的每個名稱。用法範例見
`examples/usage_examples.py`。

## 共通規則

- 帶時區的時間先換成台灣時間（UTC+8），不帶時區的時間視為台灣時間。每個時間標記代表該區間的起點，時間電價方案依它所在的時段計價。
- 內建電價是台電 114/10/1 生效的電價表，電價費率審議會決議維持到 2026-12-31。用電日期早於 2025-10-01 時發出一次 `UncheckedPriceWarning`，晚於 2026-12-31 時再發出一次。電價表附錄一、附錄二的用戶（例如凍漲行業、年用電 5 億度以上公司、IDC、農漁業、學校、社福團體）電價不同，本套件不含。
- 支援 2014–2100 年。其他年份拋出 `CalendarError`，請改傳 `calendar_instance=custom_calendar(...)`。
- 方案名稱可用 `available_plans()` 的 ID 或中文名稱、`plans.json` 的全名或舊版 README 的名稱，不分大小寫，忽略前後空白。完全相符優先，否則只有一個方案的 ID 或名稱包含該字串時才相符。
- 引數 `cache_dir`、`api_timeout` 已無作用，傳入時發出 `DeprecationWarning`，仍可傳入。
- 所有警告都指向呼叫端的程式行。

## 行事曆

- `taiwan_calendar()` 回傳 `TaiwanCalendar`。離峰日是週日加上電價表所列日期。補假與彈性放假不算，所列日期落在週六也算。2025-09-01 起清單加入除夕前一日、9/28、10/25、12/25。
- `TaiwanCalendar.is_holiday(target)` 對 `date`、`datetime` 回傳 `bool`，對 `DatetimeIndex` 回傳布林 `pd.Series`，其他型別拋出 `CalendarError`。`preload_years(years)` 先檢查並算好多個年份。
- 2014–2027 年已和台電時間電價日曆表逐日核對。2028 年以後假設現行清單不變，每個年份發出一次 `UncheckedYearWarning`。台電可能再改清單（例如 2025-09-01 改版已公布的 114 年日曆），重要帳單請核對台電最新的電價表與時間電價日曆表。
- `is_holiday(target, calendar=None)` 等同 `calendar.is_holiday(target)`，預設用 `taiwan_calendar()`。
- `custom_calendar(holidays=None, weekend_days=None)` 回傳 `CustomCalendar`。`holidays` 是 `date` 清單，`weekend_days` 是星期幾（0 為週一，6 為週日），兩者都算假日。它不限年份，`is_holiday` 對 `datetime` 用它本身的日期，不換成台灣時間。

## 方案

- `available_plans()` 回傳 `{plan_id: 中文名稱}`，共 18 個方案。
- `plan(name, calendar_instance=None, billing_cycle_type=BillingCycleType.MONTHLY)` 回傳 `TariffPlan`。`billing_cycle_type` 只影響累進電價方案的 `calculate_costs` 與 `monthly_breakdown`。`high_voltage_ev` 的單價是低壓電動車電價的 95%。
- `residential_simple_2_tier_plan()`、`high_voltage_2_tier_plan()`、`residential_non_tou_plan(billing_cycle_type=...)` 等同用該 ID 呼叫 `plan()`。
- `plan_details(plan_name)` 回傳 `TariffPlan.describe()`，含時段表 `profile` 與費率表 `rates`。
- `get_plan_requirements(plan_name)` 回傳 dict，鍵為 `requires_contract_capacity`（高壓、特高壓方案必填契約容量）、`requires_meter_spec`（表燈非時間方案的底度需電表規格）、`valid_basic_fee_labels`、`uses_basic_fee_formula` 與 `formula_type`（`two_stage`、`three_stage`、`regular_only` 或 `None`）。
- `PlanRequirements` 是同樣欄位的 dataclass（`valid_basic_fee_labels` 為 set）。`PlanRequirements.from_plan_data(plan_data)` 從 `plans.json` 的一個方案建立。

## 時段查詢

- `get_period(target, profile)` 對 `datetime` 回傳該時刻的時段，為 `PeriodType` 或字串（例如 `low_voltage_power` 的 `"flat"`），對 `DatetimeIndex` 回傳 `pd.Series`。其他型別（包括 `date`）拋出 `NotImplementedError`。
- `get_context(target, profile)` 回傳季節、日型與時段。單點為 dict，`DatetimeIndex` 為欄位 `season`、`day_type`、`period` 的 `DataFrame`。
- `period_at(target, plan_name)` 與 `period_context(target, plan_name)` 以方案名稱呼叫上面兩個函式。
- `pricing_context(target, plan_name, usage=None, include_details=False)` 回傳 `season`、`period`、`rate`、`cost`，單點為 dict，`DatetimeIndex` 為 `DataFrame`。單點的 `usage` 是數值，序列的 `usage` 須為 `pd.Series`。沒給 `usage` 時 `cost` 為 `None`。累進電價方案沒有逐時單價，`rate` 為 `None`，傳入 `usage` 拋出 `InvalidUsageInput`。`include_details=True` 回傳鍵為 `context`、`rate_details`、`profile_details` 的 dict。

## 能量費

- `calculate_costs(usage, plan)` 與 `costs(usage, plan_name)` 回傳每期能量費的 `pd.Series`（名稱 `cost`，索引為該期的抄表月）。時間電價方案依台灣時間的月份加總。累進電價方案依方案的 `billing_cycle_type` 分期，兩個月一期時級距度數加倍。一期橫跨夏月與非夏月時，依台電「請問電費如何計算」FAQ，整期度數分別以兩季累進電價計算，再依各季天數比例加權。結果不進位，也不含基本費、超約與功率因數。
- `monthly_breakdown(usage, plan_name, include_shares=False, billing_cycle_type=...)` 回傳每月、季節、時段一列的 `DataFrame`，欄位為 `month`、`season`、`period`、`usage_kwh`、`cost`。累進電價方案每期一列，`period` 為 `"tiered"`，`season` 為多數資料所在的季節。`include_shares=True` 加上 `usage_share` 與 `cost_share`。
- `usage` 須為索引是 `DatetimeIndex` 的 `pd.Series`。空的、含 NaN、無限大或負值、時間未排序、同一時間有兩筆的資料拋出 `InvalidUsageInput`。

## 帳單

`calculate_bill(usage, plan_id, inputs=None, calendar_instance=None, strict=False)` 回傳每期一列的 `DataFrame`，索引為該期第一個月。欄位如下：

- `energy_cost` 是流動電費。
- `basic_cost` 是基本電費。
- `surcharge` 是簡易型超過 2000 度部分的加計，兩個月一期從 4000 度起算。
- `adjustment` 是超約、契約時間外用電、功率因數與 `high_voltage_ev` 的 95%。
- `total` 是總額，表燈非時間方案每月未滿 100 元以 100 元計，兩個月一期至少 200 元。

計費規則如下：

- 計費期間依日曆月份切，從資料第一個月起每 `billing_cycle_months` 個月一期。台電依抄表日計費，資料從月中開始或結束時發出 `PartialPeriodWarning`，該期和台電帳單對不上。
- 預設依營業規章施行細則第二十八、二十九條進位。每期各時段的度數四捨五入到整度，各項金額計至角位（分位捨去），功率因數以截位後的金額計算，總額四捨五入到元。`BillingInputs(taipower_rounding=False)` 保留未進位的度數與金額。最高需量一律以整瓩計，小數捨去。
- 表燈非時間方案提供完整電表規格時，每月至少以底度計費。1000 V 以下的電表單相每安培 2 度、三相每安培 6 度，超過 10 安培以 10 安培計。高壓電表（單相 3300、6600 V，三相 3300、5700、11400 V）依電價表的度數。
- 抄見度數與最高需量均為 0 的月份，標準型、低壓、高壓與特高壓方案的基本費減半。裝置契約只看尖峰時間度數。一期只收一筆按戶計收，依契約種類與 `meter_phase` 決定。
- 高壓與特高壓方案的夏月為 5/16–10/15，5 月與 10 月的基本費與超約依兩季天數比例計算。其他方案的夏月為 6/1–9/30。
- 超約依 `demand_kw` 或 `over_contract_kw` 計算，契約容量 10% 以內按 2 倍、超過部分按 3 倍。各時間的超約不重複計算。只有週六半尖峰或離峰契約時，契約未涵蓋時間的用電按 4.8 倍基本電費與 1.6 倍流動電費計收。裝置契約不計超約，最高需量超過裝置契約容量時發出警告。
- 功率因數只調整電價表列出的帳單，即三相的表燈非時間與簡易型、契約 20 kW 以上的三相標準型、裝置契約 20 kW 或需量契約 30 kW 以上的三相低壓，以及所有高壓與特高壓。沒給 `meter_phase` 時視為符合。以 80% 為基準，每差 1% 調整 0.1%，95% 以上以 95% 計。調整的對象不含按戶計收，低於 80% 時含超約。當月沒有用電度數時不調整。
- `high_voltage_ev` 先算低壓電動車帳單並進位到元，再於 `adjustment` 扣 5%。

輸入檢查如下：

- 不會修改傳入的 `BillingInputs`。
- 帳單不可能有的值拋出 `InvalidBillingInput`，例如負的契約容量、0.95 的功率因數（請傳 95）、`billing_cycle_months=3`。
- 高壓與特高壓方案沒有契約容量時拋出 `MissingRequiredInput`。
- 下列情況發出 `UserWarning`。前四項在 `strict=True` 時改為拋出錯誤。
  - 方案沒有的 `basic_fee_inputs` 標籤，不計入帳單（strict 拋出 `InvalidBasicFeeInput`）。
  - 方案沒有的 `contract_capacities` 鍵，不計入帳單（strict 拋出 `InvalidBillingInput`）。
  - 需量契約方案沒有任何契約容量或裝置契約（strict 拋出 `MissingRequiredInput`）。
  - 表燈非時間方案缺少電表規格（strict 拋出 `MissingRequiredInput`）。
  - 兩個月一期的帳單有契約容量。台電每月依當月最高需量計費。
  - 沒有對應底度規則的電表。
  - 時間電價方案的資料間隔大於一小時。
  - 需量資料間隔大於 15 分鐘。
  - 裝置契約的最高需量超過裝置契約容量。

其他帳單函式：

- `calculate_bill_breakdown(...)` 的引數同 `calculate_bill`，回傳 dict。`summary` 是 `calculate_bill` 的欄位加上 `min_fee_adjustment`（`total` 中補到最低電費的部分）。`details` 是每期、季節、時段的 `usage_kwh` 與未進位的 `energy_cost`。`basic_details` 是每期、每項基本費與季節的 `share`、`quantity`、`rate`、`cost`。`adjustment_details` 的 `type` 為 `over_contract`、`outside_contract_energy`、`power_factor` 或 `bill_ratio`。
- `calculate_bill_simple(usage, plan_id)` 等同不傳 `inputs` 的 `calculate_bill`。
- `calculate_bill_from_list(usage, plan_id, start, freq="1h", inputs=None)` 從 `start` 起每 `freq` 一筆建立序列再計算。
- `calculate_bill_from_dict(usage, plan_id, inputs=None)` 以 dict 的鍵為時間。

## BillingInputs

欄位如下，皆可省略：

- `contract_capacities` 是契約容量（kW），鍵為 `regular`（經常）、`non_summer`（非夏月，二段式）、`semi_peak`（半尖峰，三段式）、`saturday_semi_peak` 與 `off_peak`。
- `contract_capacity_kw` 等同 `contract_capacities["regular"]`，兩者不同時拋出 `InvalidBillingInput`。
- `basic_fee_inputs` 是基本費標籤對應的數量，例如 `{"裝置契約": 10}`（kW）或按戶計收的戶數。簡易型的戶數用 `"basic_fee"`。各方案的標籤見 `get_plan_requirements()`。
- `demand_kw` 是需量的 `pd.Series`（kW）。間隔小於 15 分鐘時取每 15 分鐘平均，再乘上 `demand_adjustment_factor`（預設 1.0）。
- `over_contract_kw` 直接給尖峰時間超出經常契約的瓩數，每期都用這個值，優先於 `demand_kw`。
- `power_factor` 是功率因數百分比，須大於 1 且不超過 100。
- `meter_phase`（`"single"` 或 `"three"`，不分大小寫）、`meter_voltage_v` 與 `meter_ampere` 是電表規格。
- `billing_cycle_months` 為 1、2 或 `None`。`None` 用方案預設值，表燈非時間方案為 2，其他為 1。
- `taipower_rounding` 預設 `True`。

建構方法：

- `BillingInputs.for_high_voltage(regular, non_summer, saturday_semi_peak, off_peak, power_factor=None, demand_kw=None, demand_adjustment_factor=1.0)` 與 `for_extra_high_voltage(...)` 設定二段式契約。
- `for_high_voltage_three_stage(regular, semi_peak, saturday_semi_peak, off_peak, ...)` 與 `for_extra_high_voltage_three_stage(...)` 設定三段式契約。
- `for_residential(phase, voltage, ampere, basic_fee_multiplier=1.0)` 設定電表規格。`basic_fee_multiplier` 不是 1 時設為簡易型的戶數，其他方案會發出未知標籤的警告。
- `for_lighting_standard(phase, contract_kw, household_count=1.0)` 設定標準型的相別、經常契約與按戶計收戶數。

## 型別與策略

- `PeriodType` 有 `PEAK`、`SEMI_PEAK`、`OFF_PEAK`。`SeasonType` 有 `SUMMER`、`NON_SUMMER`。
- `BillingCycleType` 有 `MONTHLY`、`ODD_MONTH`（奇數月抄表，12、1 月併入 1 月）與 `EVEN_MONTH`（偶數月抄表，1、2 月併入 2 月），每期以抄表月命名。`calculate_bill` 不用它，改用 `BillingInputs.billing_cycle_months`。
- `TaiwanSeasonStrategy(summer_start, summer_end)` 的引數為 `(月, 日)`，含首尾兩日。
- `TaiwanDayTypeStrategy(calendar)` 給出 `weekday`、`saturday` 或 `sunday_holiday`（行事曆的離峰日）。
- `TariffProfile` 是時段表。`evaluate(index)` 回傳欄位 `season`、`day_type`、`period` 的 `DataFrame`，`describe()` 回傳 dict。
- `TariffPlan(profile, rates, billing_cycle_type=BillingCycleType.MONTHLY)` 有 `name`、`profile`、`rates`、`billing_cycle_type`，以及 `describe()`、`pricing_context(target, usage_kwh=None, include_details=False)`、`calculate_costs(usage_kwh)` 與 `monthly_breakdown(usage_kwh, include_shares=False)`。

## 自訂方案

- `CustomCalendar` 與 `custom_calendar()` 見「行事曆」。
- `WeekdayDayTypeStrategy(calendar, weekday_map=None, holiday_label="holiday")` 依星期幾給日型，預設週一至週五為 `weekday`、週六 `saturday`、週日 `sunday`。行事曆的假日改為 `holiday_label`。
- `build_day_schedule(slots)` 把 slot 清單轉成 `DaySchedule`。
- `build_tariff_profile(name, season_strategy, day_type_strategy, schedules, default_period=PeriodType.OFF_PEAK)` 回傳 `TariffProfile`。`schedules` 可為 `{(season, day_type): slots}`，或含 `season`、`day_type`、`slots` 的 dict 清單。slot 的時間格式為 `"HH:MM"`，`"24:00"` 視為隔天 00:00，起訖相同表示全天。沒有 slot 涵蓋的時間為 `default_period`。
- `build_tariff_rate(period_costs=None, tiered_rates=None, season_strategy=None)` 回傳 `TariffRate`。`period_costs` 可為 `{(season, period): cost}`，或含 `season`、`period`、`cost` 與選用 `day_type` 的 dict 清單。period 可為 `PeriodType` 或自訂字串。`tiered_rates` 每級有 `start_kwh`、`end_kwh`、`summer_cost`、`non_summer_cost`，`end_kwh` 為 999999 以上時沒有上限。
- `build_tariff_plan(profile, rates, billing_cycle_type=BillingCycleType.MONTHLY)` 回傳 `TariffPlan`。自訂方案用呼叫端的電價，不發出 `UncheckedPriceWarning`。

```python
from datetime import datetime
import taipower_tou as tou

calendar = tou.custom_calendar()
day_types = tou.WeekdayDayTypeStrategy(calendar)
season = tou.TaiwanSeasonStrategy((6, 1), (9, 30))

profile = tou.build_tariff_profile(
    name="Custom-Plan",
    season_strategy=season,
    day_type_strategy=day_types,
    schedules=[
        {
            "season": "summer",
            "day_type": "weekday",
            "slots": [
                {"start": "00:00", "end": "12:00", "period": "off_peak"},
                {"start": "12:00", "end": "18:00", "period": "super_peak"},
                {"start": "18:00", "end": "00:00", "period": "off_peak"},
            ],
        },
    ],
)
rates = tou.build_tariff_rate(
    period_costs=[
        {"season": "summer", "period": "off_peak", "cost": 1.0},
        {"season": "summer", "period": "super_peak", "cost": 5.0},
    ],
    season_strategy=season,
)
plan = tou.build_tariff_plan(profile, rates)
print(plan.pricing_context(datetime(2025, 7, 1, 13, 0)))
```

## 錯誤

所有錯誤都繼承 `PowerKitError`。

- `CalendarError` 表示年份超出 2014–2100，或 `is_holiday` 收到不支援的型別。
- `TariffError` 表示自訂時段的時間格式錯誤，或缺少 pandas。
- `InvalidUsageInput` 表示用電或需量資料不合法，或累進電價方案的 `pricing_context` 收到 `usage`。
- `MissingRequiredInput` 表示缺少方案必需的輸入。
- `InvalidBillingInput` 也是 `ValueError`，表示 `BillingInputs` 有帳單不可能有的值，或 strict 模式下方案沒有的契約鍵。
- `InvalidBasicFeeInput` 是 `InvalidBillingInput` 的子類別，表示 `basic_fee_inputs` 的值不合法，或 strict 模式下方案沒有的標籤。
- `UnknownPlanError` 也是 `KeyError` 與 `ValueError`，表示方案名稱找不到、相符超過一個、已移除或不是字串。

## 警告

- `UncheckedPriceWarning`、`UncheckedYearWarning` 與 `PartialPeriodWarning` 都是 `UserWarning`，觸發條件見上。
- `calculate_bill` 的其他輸入警告是 `UserWarning`，見「帳單」。
- `cache_dir`、`api_timeout` 發出 `DeprecationWarning`。

`__version__` 是套件版本字串。
