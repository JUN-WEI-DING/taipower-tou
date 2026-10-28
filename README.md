[![PyPI Version](https://img.shields.io/pypi/v/taipower-tou)](https://pypi.org/project/taipower-tou/)
[![Python](https://img.shields.io/pypi/pyversions/taipower-tou)](https://pypi.org/project/taipower-tou/)
[![License](https://img.shields.io/github/license/JUN-WEI-DING/taipower-tou)](https://github.com/JUN-WEI-DING/taipower-tou/blob/main/LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/JUN-WEI-DING/taipower-tou/ci.yml?branch=main)](https://github.com/JUN-WEI-DING/taipower-tou/actions/workflows/ci.yml)

# Taiwan Electricity Tariff Calculator

`taipower-tou` computes electricity costs and bills for the 18 plans in Taipower's 電價表, both tiered (累進費率) and time-of-use (時間電價). A bill includes the basic fee, 超約 fees, the 功率因數 adjustment and Taipower's rounding.

`taipower-tou` 依台電電價表計算 18 種方案的電費，包含累進費率與時間電價。完整帳單含基本電費、超約附加費、功率因數調整，並依台電的方式進位。

## Installation

```bash
pip install taipower-tou
uv add taipower-tou  # in a uv project
```

It needs Python 3.9 or later, numpy and pandas.

## Prices and Their Dates (電價版本與適用範圍)

The bundled prices are Taipower's 電價表 effective 2025-10-01 (114/10/1). Taipower's 電價費率審議會 kept them unchanged through 2026-12-31. Usage dated before 2025-10-01 raises `UncheckedPriceWarning` once per process, and usage dated after 2026-12-31 raises it once more, because Taipower billed or may bill those days at other prices.

The prices are the main tables only. Customers in the 電價表's 附錄一 (適用電價調整係數行業或用戶, such as industries with frozen or halved increases, companies using 500 million kWh (5億度) or more a year, and data centers (IDC)) and 附錄二 (農漁業、學校、社福團體) pay other prices, and this package does not cover them. Plans you build with `build_tariff_plan` use your own prices and never raise `UncheckedPriceWarning`.

內建電價是台電 114/10/1 生效的電價表，電價費率審議會決議維持到 2026-12-31。用電日期早於 2025-10-01 時，每個程式發出一次 `UncheckedPriceWarning`；晚於 2026-12-31 時再發出一次。因為那些日子台電用的是（或可能是）別的電價。

內建的只有電價表主表。適用附錄一（電價調整係數行業或用戶，例如凍漲或調幅減半的行業、年用電 5 億度以上的公司、網路資料中心 IDC）或附錄二（農漁業、學校、社福團體）的用戶電價不同，本套件不含這些電價。用 `build_tariff_plan` 自訂的方案用的是您自己的電價，不會發出 `UncheckedPriceWarning`。

When Taipower's 電價費率審議會 meets, a new release of this package moves 2026-12-31 forward if prices stay the same, or adds the new prices if they change. Upgrade after each meeting.

審議會開會後，若電價不變，新版會延後 2026-12-31 這個日期；若電價調整，新版會加入新電價。每次審議會後請升級。

If you have checked the prices, the off-peak days or the billing periods yourself, you can silence the warnings:
若您已自行核對電價、離峰日或計費期間，可以關閉警告：

```python
import warnings

import taipower_tou as tou

warnings.simplefilter("ignore", tou.UncheckedPriceWarning)
warnings.simplefilter("ignore", tou.UncheckedYearWarning)
warnings.simplefilter("ignore", tou.PartialPeriodWarning)
```

## Off-Peak Days (離峰日)

Every time-of-use plan and `is_holiday` follow the 離峰日 list in Taipower's 電價表, not the government office calendar. An off-peak day is a Sunday or a listed day, and it is off-peak all day. From 2014 the list is 1/1, 春節 (除夕 to 初五), 2/28, 4/4, 清明, 5/1, 端午, 中秋 and 10/10. From 2025-09-01 it also has 除夕前1日, 9/28, 10/25 and 12/25. 補假 and 彈性放假 days are not off-peak days, and a listed day that falls on a Saturday is still one. The days are computed offline for 2014–2100. Other years raise `CalendarError`. Pass `calendar_instance=custom_calendar(...)` for them.

Tests compare every day of 2014–2027 with Taipower's official 時間電價日曆表 in `tests/data/taipower_calendar/`. Taipower publishes these calendars about a year ahead. Later years assume the current list stays in force and raise `UncheckedYearWarning`, once per year.

所有時間電價方案與 `is_holiday` 都依台電電價表所列的離峰日，不是行政機關辦公日曆。離峰日是週日或表列日期，全日離峰。2014 年起的表列日期是 1/1、春節（除夕至初五）、2/28、4/4、清明、5/1、端午、中秋與 10/10；2025-09-01 起另加除夕前1日、9/28、10/25 與 12/25。補假與彈性放假不算離峰日，表列日期落在週六仍是離峰日。離峰日不需連網計算，支援 2014–2100 年；其他年份拋出 `CalendarError`，請改傳 `calendar_instance=custom_calendar(...)`。

測試逐日比對 2014–2027 年與 `tests/data/taipower_calendar/` 中台電官方的時間電價日曆表。台電約提前一年公布日曆。之後的年份假設現行清單不變，每個年份發出一次 `UncheckedYearWarning`。

> [!IMPORTANT]
> **Taipower can change the off-peak list.** On 2025-09-01 Taipower added off-peak days and revised the 114年 calendar it had already published, so 2025-10-25 and 2025-12-25 became off-peak days. This package computes the list it knew when it was released and cannot follow a later change, even for a year it has checked. Before you rely on a bill, check Taipower's latest 電價表 and 時間電價日曆表, and upgrade when a new version of this package follows a change.
>
> **台電可能修改離峰日。** 台電在 2025-09-01 新增離峰日，並改版已公布的 114 年日曆，2025-10-25 與 2025-12-25 因此成為離峰日。本套件只能依發布時已知的規則計算，之後的修改不會自動反映，已核對過的年份也一樣。重要的帳單請自行核對台電最新的電價表與時間電價日曆表，並在本套件發布對應新版後升級。

```python
from datetime import datetime

print(tou.is_holiday(datetime(2025, 1, 1)))  # True
# A 彈性放假 day for government offices, but not an off-peak day
print(tou.is_holiday(datetime(2025, 1, 27)))  # False
```

## Quick Start Guide (快速入門)

Two kinds of function compute costs:

| | `TariffPlan.calculate_costs`, `tou.costs` | `calculate_bill`, `calculate_bill_breakdown` |
|---|---|---|
| Result | Energy cost (電能費) only | The whole bill: energy cost, basic fee, 2000 kWh 加計, 超約, 功率因數 and minimum charges |
| Groups usage | By calendar month. Tiered plans group months by `billing_cycle_type`. | Into bills of `billing_cycle_months` calendar months, from the first month of usage |
| Rounding | None | Taipower's, unless `taipower_rounding=False` |
| Plans | Bundled and custom | Bundled only |

`TariffPlan.calculate_costs`（或 `tou.costs`）只算電能費，依日曆月份分組，累進費率方案依 `billing_cycle_type` 分組，不進位，內建與自訂方案都能用。`calculate_bill` 與 `calculate_bill_breakdown` 算完整帳單，含電能費、基本電費、超過 2000 度的加計、超約附加費、功率因數調整與最低收費；從用電資料的第一個月起，每 `billing_cycle_months` 個日曆月一張帳單；依台電方式進位，除非設 `taipower_rounding=False`；只能用內建方案。

- [Tiered Rate Quick Start (累進費率快速入門)](#tiered-rate-quick-start-累進費率快速入門) covers `residential_non_tou` and the `lighting_*_tiered` plans.
- [Time-of-Use Quick Start (時間電價快速入門)](#time-of-use-quick-start-時間電價快速入門) covers the other plans.

---

## Tiered Rate Quick Start (累進費率快速入門)

A tiered plan prices a bill's kWh by tier, and each tier costs more than the one before.

累進費率方案依級距計算帳單度數，用電越多，單價越高。

```
Residential Non-TOU (表燈非時間電價), TWD/kWh
              Non-Summer (非夏月)   Summer (夏月，6/1-9/30)
0 - 120 kWh        1.78                1.78
121 - 330 kWh      2.26                2.55
331 - 500 kWh      3.13                3.80
501 - 700 kWh      4.24                5.14
701 - 1000 kWh     5.27                6.44
1001+ kWh          7.03                8.86
```

`lighting_non_business_tiered` has the same tiers. `lighting_business_tiered` has five tiers of its own, which `tou.plan_details("lighting_business_tiered")["rates"]["tiered_rates"]` lists.

`lighting_non_business_tiered` 的級距相同。`lighting_business_tiered` 有自己的五個級距，可用 `tou.plan_details("lighting_business_tiered")["rates"]["tiered_rates"]` 查看。

### Basic Example (基本範例)

```python
import pandas as pd
import taipower_tou as tou

# Each month's total kWh
# 每個月一筆總度數
monthly_usage = pd.Series(
    [280, 320, 250, 310, 290, 280, 350, 380, 360, 300, 270, 260],
    index=pd.date_range("2026-01-01", periods=12, freq="MS"),
)

plan = tou.plan("residential_non_tou")
costs = plan.calculate_costs(monthly_usage)

print(f"Annual Total: {costs.sum():.2f} TWD")
# Annual Total: 7940.90 TWD

for month, cost in costs.items():
    print(f"{month.strftime('%Y-%m')}: {cost:.2f} TWD")
# 2026-01: 575.20 TWD
# 2026-02: 665.60 TWD
# ...

print(plan.monthly_breakdown(monthly_usage))
#         month      season  period  usage_kwh   cost
# 0  2026-01-01  non_summer  tiered      280.0  575.2
# 1  2026-02-01  non_summer  tiered      320.0  665.6
# ...
```

### Full Bills (完整帳單)

`calculate_bill` bills these plans every two months by default, as Taipower reads most homes' meters. Pass `billing_cycle_months=1` for monthly bills. Give the meter's phase, voltage and ampere for the 底度 ([Minimum Usage and Minimum Fee](#minimum-usage-and-minimum-fee-底度與最低電費)). Without them the bill has no 底度 and warns. `calculate_bill` reads each value as kWh used at its timestamp. Monthly totals stamped on the 1st give each month's bill, but the last month's usage seems to stop on its 1st, so the call raises `PartialPeriodWarning`.

`calculate_bill` 預設每兩個月開一張這些方案的帳單，和台電多數住家的抄表方式相同；要每月一張請傳 `billing_cycle_months=1`。請提供電表的相數、電壓與安培數以計算底度（[底度與最低電費](#minimum-usage-and-minimum-fee-底度與最低電費)），沒有提供時帳單不計底度並發出警告。`calculate_bill` 把每筆數值視為該時間標記用掉的度數。標在每月 1 日的月總度數能算出每月帳單，但最後一個月的用電看起來在 1 日就結束，所以會發出 `PartialPeriodWarning`。

```python
from taipower_tou import BillingInputs, calculate_bill

inputs = BillingInputs(
    meter_phase="single",
    meter_voltage_v=110,
    meter_ampere=10,
    billing_cycle_months=1,
)
bills = calculate_bill(monthly_usage, "residential_non_tou", inputs=inputs)
print(bills.head(2))
#             energy_cost  basic_cost  surcharge  adjustment  total
# 2026-01-01        575.2         0.0        0.0         0.0  575.0
# 2026-02-01        665.6         0.0        0.0         0.0  666.0
```

### Two-Month Billing Cycle (隔月抄表)

Taipower reads most homes' and small shops' meters every two months, some in odd months and some in even months. A two-month bill doubles each tier, so its first 240 kWh cost 1.78 TWD each (電價表 第三章 五(一)2: 用戶因實施隔月抄表、收費，其計費之分段度數加倍計算). `BillingCycleType` picks the months that `TariffPlan.calculate_costs` pairs, and each result is labelled by its reading month:

台電對多數住宅及小商店隔月抄表，有些在單數月抄表，有些在雙數月。兩個月一期的帳單級距加倍，所以前 240 度每度 1.78 元（電價表 第三章 五(一)2：用戶因實施隔月抄表、收費，其計費之分段度數加倍計算）。`BillingCycleType` 決定 `TariffPlan.calculate_costs` 如何兩個月一組，結果以抄表月份標記：

| `BillingCycleType` | Billing Periods (計費週期) | Meter Read Month (抄表月份) |
|---------------------|--------------------------|---------------------------|
| `ODD_MONTH` (奇數月抄表) | 12月-1月, 2月-3月, 4月-5月, 6月-7月, 8月-9月, 10月-11月 | 1, 3, 5, 7, 9, 11月 |
| `EVEN_MONTH` (偶數月抄表) | 1月-2月, 3月-4月, 5月-6月, 7月-8月, 9月-10月, 11月-12月 | 2, 4, 6, 8, 10, 12月 |
| `MONTHLY` (default, 預設) | Each month (每月) | Each month (每月) |

```python
from taipower_tou import BillingCycleType

# 4 kWh a day for 60 days: 120 kWh in June and 120 in July
usage_240 = pd.Series(4.0, index=pd.date_range("2026-06-01", periods=60, freq="D"))

monthly = tou.plan("residential_non_tou").calculate_costs(usage_240)
bimonthly = tou.plan(
    "residential_non_tou", billing_cycle_type=BillingCycleType.ODD_MONTH
).calculate_costs(usage_240)

print(monthly)
# 2026-06-01    213.6
# 2026-07-01    213.6
# Name: cost, dtype: float64
print(bimonthly)  # the same total, since the pair's first tier is 240 kWh
# 2026-07-01    427.2
# Name: cost, dtype: float64
```

#### Rate Change Apportionment (電價異動分攤)

When a billing period spans 夏月 (6/1–9/30) and 非夏月, Taipower's FAQ 請問電費如何計算 prices all of the period's kWh at each season's tiered rates, then weights each total by that season's share of the period's days. For 350 kWh over a 60-day period with 18 summer days:

當計費期間橫跨夏月（6/1–9/30）與非夏月時，台電「請問電費如何計算」FAQ 的算法是：整期度數分別用夏月和非夏月的累進電價各算一次，再依各季天數占全期天數的比例加權。例如 60 天用 350 度，其中 18 天是夏月：

```
[1.78×240 + 2.55×110] × 18/60 + [1.78×240 + 2.26×110] × 42/60
```

`calculate_costs`, `calculate_bill`, and `calculate_bill_breakdown` all use this formula. The breakdown lists one tiered row per season.

`calculate_costs`、`calculate_bill`、`calculate_bill_breakdown` 都用這個算法，明細會分季各列一行。

#### Billing Periods Are Calendar Months (計費期間以日曆月份計算)

`calculate_bill` and `calculate_bill_breakdown` split usage into bills of `billing_cycle_months` calendar months, counted from the first month of usage. A Taipower bill runs from one meter reading to the next, and the reading is often mid-month. Usage that starts or ends mid-month leaves part of a bill's months empty and raises `PartialPeriodWarning` on every such call. Those bills do not match Taipower's. Compare with a real bill only by passing usage for whole calendar months. `TariffPlan.calculate_costs` groups months into the odd- or even-month pairs in the table above and does not warn.

`calculate_bill` 與 `calculate_bill_breakdown` 依日曆月份切帳單，從用電資料的第一個月起，每 `billing_cycle_months` 個月一張。台電帳單的計費期間是從上次抄表日到這次抄表日，抄表日常在月中。用電資料從月中開始或在月中結束時，帳單有幾天沒有資料，每次計算都會發出 `PartialPeriodWarning`，算出的帳單和台電的對不上。要和實際帳單比對，請提供完整日曆月份的用電資料。`TariffPlan.calculate_costs` 依上表的奇數月或偶數月分組，不會發出這個警告。

#### Minimum Usage and Minimum Fee (底度與最低電費)

For `residential_non_tou` and the `lighting_*_tiered` plans, `calculate_bill` bills a month at least its 底度 when `BillingInputs` gives `meter_phase`, `meter_voltage_v` and `meter_ampere`. A single-phase low-voltage meter has 2 kWh per ampere and a three-phase one 6 kWh per ampere, and a low-voltage meter over 10 A counts as 10 A. Any meter under 1000 V is a low-voltage one, so 110, 220 and 380 V meters all are (營業規章 第三條). The 電價表 gives its own kWh per ampere for single-phase 3,300 and 6,600 V meters and three-phase 3,300, 5,700 and 11,400 V meters (第三章 五(一)1). A meter that no 底度 rule covers, such as a three-phase 22,800 V one, warns and is billed without 底度. A bill under 100 TWD a month is charged 100 TWD a month, so a two-month bill is at least 200 TWD.

`residential_non_tou` 與 `lighting_*_tiered` 方案若在 `BillingInputs` 提供 `meter_phase`、`meter_voltage_v` 與 `meter_ampere`，`calculate_bill` 每月至少以底度計費：單相低壓電表每安培 2 度、三相每安培 6 度，超過 10 安培的低壓電表以 10 安培計。未滿 1000 伏特的電表都是低壓電表，110、220、380 伏特都算（營業規章 第三條）。單相 3,300、6,600 伏特與三相 3,300、5,700、11,400 伏特的電表依電價表所列的每安培度數計算（第三章 五(一)1）。沒有底度規則適用的電表，例如三相 22,800 伏特，會發出警告，並且不計底度。每月電費未滿 100 元以 100 元計，兩個月一期至少 200 元。

---

## Time-of-Use Quick Start (時間電價快速入門)

A time-of-use plan prices each kWh by the season, the day type and the time of day it was used. [Available Plans (可用方案)](#available-plans-可用方案) lists the plans.

時間電價方案依用電的季節、日期型別與時段計價。方案列表見[可用方案](#available-plans-可用方案)。

| Factor | Options |
|--------|---------|
| **季節 Season** | 夏月 Summer 6/1-9/30 (高壓 and 特高壓 plans 5/16-10/15, except `high_voltage_ev`) / 非夏月 Non-Summer |
| **日期 Day Type** | 週日及離峰日 Sunday and off-peak days (off-peak all day) / 週六 Saturday / 平日 Weekday |
| **時段 Period** | 尖峰 Peak / 半尖峰 Semi-Peak (三段式 weekdays, and Saturdays as 週六半尖峰 on 標準型, 低壓, 高壓 and 特高壓 plans other than EV) / 離峰 Off-Peak |

### Step 1: Prepare Your Time-Series Data (準備時間序列資料)

A time-of-use bill prices each reading at the period of its timestamp, so it needs hourly or finer usage. Daily kWh would all be priced at 00:00. The 批次生產 plans change period at 15:30 and 21:30, so they need 30-minute or finer usage. `calculate_bill` warns when every gap between `usage` timestamps is a multiple of one step longer than an hour, as in daily or 2-hourly data. Irregular readings such as 09:00, 10:30 and 14:00 have a 30-minute step and do not warn.

時間電價依每筆資料的時間標記計價，所以需要每小時或更細的資料；每日度數會全部算成 00:00 的時段。批次生產方案在 15:30 與 21:30 換時段，需要每 30 分鐘或更細的資料。`usage` 各時間標記的間隔若都是同一個超過一小時的間隔的倍數，例如每日或每兩小時一筆，`calculate_bill` 會發出警告。09:00、10:30、14:00 這類不規則資料的共同間隔是 30 分鐘，不會警告。

Each timestamp in `usage` and `demand_kw` labels the start of its interval. In 15-minute data, the kWh at 08:45 were used from 08:45 to 09:00 and are priced at 08:45's period. A meter export that labels each interval by its end (09:00 for 08:45-09:00) must first be moved back one interval, for example with `usage.shift(-1, freq="15min")`. Timezone-aware timestamps are converted to Taiwan time (UTC+8) first, and naive timestamps are read as Taiwan time. An empty `usage`, a negative, NaN or infinite reading, timestamps out of order, or two readings at the same timestamp raise `InvalidUsageInput`.

每個時間標記代表區間的開始。15 分鐘資料中 08:45 的度數是 08:45 到 09:00 用的，依 08:45 的時段計價。若電表匯出的資料以區間結束時間標記（08:45 到 09:00 標為 09:00），請先往前移一個區間，例如 `usage.shift(-1, freq="15min")`。帶時區的時間會先換成台灣時間（UTC+8），不帶時區的時間視為台灣時間。`usage` 是空的、有負數、NaN 或無窮大、時間未依序排列，或同一時間標記有兩筆資料，會拋出 `InvalidUsageInput`。

#### Example A: Create Data Manually (範例 A：用 Python 手動建立資料)

```python
timestamps = [
    "2026-07-15 06:00",  # summer weekday, off-peak
    "2026-07-15 09:00",  # summer weekday, peak
    "2026-07-15 10:00",
    "2026-07-15 11:00",
]
usage_kwh = [2.4, 1.5, 2.3, 1.8]  # kWh used in each hour

usage_series = pd.Series(usage_kwh, index=pd.to_datetime(timestamps))
print(usage_series)
# 2026-07-15 06:00:00    2.4
# 2026-07-15 09:00:00    1.5
# 2026-07-15 10:00:00    2.3
# 2026-07-15 11:00:00    1.8
# dtype: float64
```

#### Example B: Read from CSV (範例 B：從 CSV 檔案讀取)

Assume you have an `electricity.csv` file:
假設你有一個 `electricity.csv` 檔案：

```csv
timestamp,usage
2026-07-15 09:00,1.5
2026-07-15 10:00,2.3
2026-07-15 11:00,1.8
```

```python
df = pd.read_csv("electricity.csv", parse_dates=["timestamp"], index_col="timestamp")
csv_usage = df["usage"]
```

#### Example C: Lists and Dicts (範例 C：用 list 或 dict)

`calculate_bill_from_list` and `calculate_bill_from_dict` build the Series for you and call `calculate_bill`.

`calculate_bill_from_list` 與 `calculate_bill_from_dict` 會替您建立 Series，再呼叫 `calculate_bill`。

```python
# Regularly spaced readings
# 固定間隔資料
result = tou.calculate_bill_from_list(
    usage=[1.5, 2.3, 1.8, 2.0, 1.6],
    plan_id="簡易型二段式",
    start="2026-07-15 09:00",
    freq="1h",
)
print(f"Total: {result['total'].iloc[0]:.2f} TWD")  # Total: 121.00 TWD

# Irregularly spaced readings
# 不規則間隔資料
result = tou.calculate_bill_from_dict(
    usage={
        "2026-07-15 09:00": 1.5,
        "2026-07-15 10:00": 2.3,
        "2026-07-15 14:30": 2.0,
    },
    plan_id="residential_simple_2_tier",
)
print(f"Total: {result['total'].iloc[0]:.2f} TWD")  # Total: 106.00 TWD
```

### Step 2: Check Rate Period (判斷費率時段)

```python
dt = datetime(2026, 7, 15, 14, 0)  # a summer weekday afternoon

print(tou.period_at(dt, "residential_simple_2_tier"))  # PeriodType.PEAK
print(tou.period_context(dt, "residential_simple_2_tier"))
# {'season': <SeasonType.SUMMER: 'summer'>, 'day_type': 'weekday', 'period': <PeriodType.PEAK: 'peak'>}
print(tou.pricing_context(dt, "residential_simple_2_tier"))
# {'season': 'summer', 'period': 'peak', 'rate': 5.16, 'cost': None}
print(tou.pricing_context(dt, "residential_simple_2_tier", usage=10.0)["cost"])  # 51.6
```

`period_at` returns a `PeriodType`, one of `PEAK`, `SEMI_PEAK` and `OFF_PEAK`. `low_voltage_power` has one price at any hour, and its period is `"flat"`. `pricing_context` gives the season and period as strings. A tiered plan has no price per period, so its `rate` is `None`, and passing a usage raises `InvalidUsageInput`.

### Step 3: Calculate Energy Costs (計算電能費)

```python
plan = tou.plan("residential_simple_2_tier")
costs = plan.calculate_costs(usage_series)  # one row per month
print(f"Total Cost: {costs.iloc[0]:.2f} TWD")  # Total Cost: 33.84 TWD
```

### Step 4: View Detailed Report (檢視詳細報表)

```python
print(plan.monthly_breakdown(usage_series))
#        month  season    period  usage_kwh    cost
# 0 2026-07-01  summer  off_peak        2.4   4.944
# 1 2026-07-01  summer      peak        5.6  28.896
```

### Step 5: Calculate the Full Bill (計算完整帳單)

```python
july_usage = pd.Series(
    30.0, index=pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h")
)  # 30 kW all month
inputs = BillingInputs(
    contract_capacities={"regular": 100},  # 100 kW 經常契約
    power_factor=90.0,  # 90%
)
print(calculate_bill(july_usage, "high_voltage_2_tier", inputs=inputs))
#             energy_cost  basic_cost  surcharge  adjustment     total
# 2026-07-01     102409.2     22360.0        0.0     -1247.6  123522.0
```

`BillingInputs` fields:

| Field | Meaning |
|-------|---------|
| `contract_capacities` | Contracts in kW, by the keys in [Basic Fee](#1-basic-fee-基本費) |
| `contract_capacity_kw` | The 經常契約 in kW, the same as `contract_capacities={"regular": kw}` |
| `basic_fee_inputs` | A 裝置契約 in kW or a 按戶計收 household count, keyed by its 電價表 label |
| `demand_kw` | A Series of demand readings in kW, ideally every 15 minutes ([Data Resolution](#5-data-resolution-requirements-資料解析度要求)) |
| `demand_adjustment_factor` | Multiplies every `demand_kw` reading. Default 1.0. |
| `over_contract_kw` | 超約 kW over the 經常契約 at 尖峰, used for every bill in place of `demand_kw` |
| `power_factor` | Percent, 95 for 95% |
| `meter_phase` | `"single"` or `"three"`. It picks the 按戶計收 fee and whether 功率因數 applies. |
| `meter_voltage_v`, `meter_ampere` | With `meter_phase`, they set the 底度 of the 表燈非時間 plans |
| `billing_cycle_months` | 1, 2 or `None`. `None` takes the plan's default, 2 for 表燈非時間 and 1 for the others. |
| `taipower_rounding` | `True` rounds as Taipower bills. `False` keeps every kWh and amount unrounded. |

`calculate_bill` and `calculate_bill_breakdown` do not change the `BillingInputs` you pass, so one `BillingInputs` can bill several months or plans. A field left as `None`, such as `billing_cycle_months`, takes each plan's default for that bill only.

`calculate_bill` 與 `calculate_bill_breakdown` 不會修改傳入的 `BillingInputs`，同一個 `BillingInputs` 可以重複用於不同月份或方案。留空（`None`）的欄位，例如 `billing_cycle_months`，只在該次計算採用方案的預設值。

`calculate_bill` checks `BillingInputs` before it bills. These values raise `InvalidBillingInput`, with or without `strict=True`:

- A contract, 裝置契約, household count, `over_contract_kw` or `meter_ampere` that is negative, NaN, infinite or not a number. A bad `basic_fee_inputs` value raises `InvalidBasicFeeInput`, which is an `InvalidBillingInput`.
- A `demand_adjustment_factor` of 0 or less.
- A `power_factor` that is NaN, over 100, or 1 or less. It is a percentage, so pass 95 for 95%, not 0.95.
- A `billing_cycle_months` other than 1, 2 or `None`.
- A `meter_phase` other than `"single"` or `"three"`. Case does not matter, so `"Three"` is `"three"`.
- A `contract_capacity_kw` with a different `"regular"` in `contract_capacities`. `contract_capacity_kw=200` is the 經常契約, `contract_capacities={"regular": 200}`.

Every contract in `contract_capacities` is optional, so a 高壓 bill with `{"regular": 200}` alone has no 非夏月, 週六半尖峰 or 離峰 contract. A key the plan does not bill, such as a misspelt `"regualr"`, warns and is left out, and `strict=True` raises `InvalidBillingInput` for it. A 高壓 or 特高壓 bill with no contract raises `MissingRequiredInput`. A 低壓 or 標準型 bill with neither a contract nor a 裝置契約 warns, and `strict=True` raises `MissingRequiredInput`. Taipower bills a 契約容量 every month, since 超約 is on each month's highest demand, so `billing_cycle_months=2` with a contract warns.

`calculate_bill` 計算前會檢查 `BillingInputs`。下列數值不論是否 `strict=True` 都會拋出 `InvalidBillingInput`：

- 契約容量、裝置契約、戶數、`over_contract_kw` 或 `meter_ampere` 為負數、NaN、無窮大或不是數字。`basic_fee_inputs` 的數值有誤時拋出 `InvalidBasicFeeInput`，它也是 `InvalidBillingInput`。
- `demand_adjustment_factor` 小於或等於 0。
- `power_factor` 是 NaN、大於 100，或小於或等於 1。功率因數是百分比，95% 請傳 95，不是 0.95。
- `billing_cycle_months` 不是 1、2 或 `None`。
- `meter_phase` 不是 `"single"` 或 `"three"`。不分大小寫，`"Three"` 就是 `"three"`。
- 同時給 `contract_capacity_kw` 與不同的 `contract_capacities["regular"]`。`contract_capacity_kw=200` 就是經常契約 `contract_capacities={"regular": 200}`。

`contract_capacities` 的每種契約都可以不給，例如高壓只給 `{"regular": 200}` 就是沒有非夏月、週六半尖峰與離峰契約。方案沒有的契約名稱，例如拼錯的 `"regualr"`，會發出警告並略過，`strict=True` 時拋出 `InvalidBillingInput`。高壓與特高壓沒有任何契約會拋出 `MissingRequiredInput`。低壓或標準型既沒有契約也沒有裝置契約時會發出警告，`strict=True` 時拋出 `MissingRequiredInput`。台電的契約容量用戶按月計費，超約依當月最高需量計算，所以有契約時設 `billing_cycle_months=2` 會發出警告。

For 超約, pass `demand_kw` read every **15 minutes**, as [Data Resolution Requirements](#5-data-resolution-requirements-資料解析度要求) explains.
計算超約附加費時，`demand_kw` 請用 **每 15 分鐘** 的需量資料，原因見[資料解析度要求](#5-data-resolution-requirements-資料解析度要求)。

---

## Calculation Logic & Background (計算邏輯與背景)

This section explains how Taipower bills and how the package reads each rule.
這個章節說明臺電如何計算電費，以及本套件如何解讀每條規則。

### Quick Formula (電費計算公式)

```
總電費 = 電能費 + 基本費 + 違約金 ± 功率因數調整 + 其他調整

Total Bill = Energy Cost + Basic Fee + Penalty ± PF Adjustment + Others
```

`calculate_bill` gives each bill as `energy_cost` (電能費), `basic_cost` (基本電費), `surcharge` (the 加計 on kWh over 2000 a month), `adjustment` and `total`. `adjustment` holds the 超約 fee, the 功率因數 adjustment, the extra 60% of the energy price on use outside a 週六半尖峰-only or 離峰-only contract, and the 5% off a `high_voltage_ev` bill. A total under the plan's minimum charge is raised to it, so `total` can be more than the items add up to. `calculate_bill_breakdown`'s `summary` shows the difference as `min_fee_adjustment`.

---

## Tiered Rate Calculation (累進費率計算方式)

```
電能費 = Σ(各累進級距用電度數 × 該級距單價)

Energy Cost = Σ(Tier_kWh × Tier_Rate) for each tier
```

**350 kWh in a summer month on `residential_non_tou`** (the tiers are in the [Tiered Rate Quick Start](#tiered-rate-quick-start-累進費率快速入門)):

| Tier | Usage | Rate | Cost |
|------|-------|------|------|
| 1st tier (0-120) | 120 kWh | 1.78 | 213.60 |
| 2nd tier (121-330) | 210 kWh | 2.55 | 535.50 |
| 3rd tier (331-500) | 20 kWh | 3.80 | 76.00 |
| **Total** | **350 kWh** | - | **825.10 TWD** |

---

## Time-of-Use Calculation (時間電價計算方式)

### How TOU Rates Work (時間電價運作方式)

```
電能費 = Σ(各時段用電度數 × 該時段費率)

Energy Cost = Σ(Period_Usage_kWh × Period_Rate) for each time period
```

The rate depends on the season, the day type and the period ([Time-of-Use Quick Start](#time-of-use-quick-start-時間電價快速入門)).

**Sample TOU Schedule (簡易型二段式):**

From the 電價表 (`src/taipower_tou/data/詳細電價表.md` lines 184-204). Prices are TWD/kWh.

| Day Type | Period | Summer (6/1-9/30) | Non-Summer |
|----------|--------|-------------------|------------|
| Weekday | Peak | 09:00-24:00, 5.16 | 06:00-11:00 and 14:00-24:00, 4.93 |
| Weekday | Off-peak | 00:00-09:00, 2.06 | 00:00-06:00 and 11:00-14:00, 1.99 |
| Saturday, Sunday and 離峰日 | Off-peak | All day, 2.06 | All day, 1.99 |

Each month also pays 75.00 按戶計收, and a month's kWh over 2000 pay 1.04 more each. A two-month bill pays the 1.04 on its kWh over 4000, 2000 for each month, as tiered bills double their tiers.

---

## Common Components (共同計算元件)

These components apply to both tiered rate and TOU plans.
這些元件同樣適用於累進費率和時間電價方案。

### 1. Basic Fee (基本費)

A basic fee is charged per household (按戶計收) or per kW of contract. A month of a 需量契約 bill pays (電價表 第三章 五(三), 第四章 五(三), 第五章 五(一)):

```
基本電費 = 經常契約電價 × 經常契約容量
        + 非夏月契約電價 × 非夏月契約容量 (in 非夏月 only)
        + 週六半尖峰或離峰契約電價 × max(0, (週六半尖峰 + 離峰契約容量) − (經常 + 非夏月契約容量) × 0.5)
```

A 三段式 bill has 半尖峰契約 in place of 非夏月契約, in both seasons. The 週六半尖峰 and 離峰 contracts pay only for their kW beyond half of the others. `contract_capacities` names the contracts by these keys:

| Key | Contract | Plans |
|-----|----------|-------|
| `"regular"` | 經常契約 | Every plan with a contract |
| `"non_summer"` | 非夏月契約 | 標準型, 低壓, 高壓 and 特高壓 二段式, the 批次生產 plans and `low_voltage_power` |
| `"semi_peak"` | 半尖峰契約 | 標準型, 低壓, 高壓 and 特高壓 三段式 |
| `"saturday_semi_peak"` | 週六半尖峰契約 | The plans with `"non_summer"` or `"semi_peak"`, except `low_voltage_power` |
| `"off_peak"` | 離峰契約 | The plans with `"non_summer"` or `"semi_peak"`, except `low_voltage_power` |

The EV plans take `"regular"` alone. `basic_fee_inputs` takes a 裝置契約 in kW for `low_voltage_power` and `low_voltage_2_tier` billed by installed capacity, and the household count of a 按戶計收 fee, 1 by default. On 簡易型 the household count's key is `"basic_fee"`. `get_plan_requirements(plan_id)["valid_basic_fee_labels"]` lists a plan's labels.

A bill pays one 按戶計收 fee, chosen by its contract type and `meter_phase`. 標準型 charges 129.10 TWD single-phase and 262.50 three-phase. `low_voltage_2_tier` charges 105.00 with a 裝置契約 and 262.50 with a 需量契約. `low_voltage_three_stage`, `low_voltage_ev` and `high_voltage_ev` charge 262.50. 簡易型 charges 75.00 a month. The 表燈非時間 plans have no basic fee.

A month with no use pays half its basic fee on the 標準型, 低壓, 高壓 and
特高壓 plans (電價表 第三章 五(三)4, 第四章 五(五), 第五章 五(二)). No use means 0 kWh
and 0 kW of 最高需量, both read as 第二十八條 reads them, so a month with
0.4 kWh and a 0.6 kW reading had none. A month given `over_contract_kw`
above 0 had demand, so it pays the whole fee. A 裝置契約 bill looks only at
its kWh, its 尖峰 kWh on a time-of-use plan, never at its demand.

---

### 2. Demand Penalty (違約金)

**If your peak demand exceeds your contract capacity, you pay extra basic fee.**
如果最高需量超過契約容量，超出部分加收基本電費。

```
最高需量 = 當月內任意15分鐘平均功率的最大值
Peak Demand = Maximum 15-minute average power during the month
```

Each time of day has its own excess (超約瓩數). For a two-stage plan:

| Time | Excess |
|------|--------|
| 尖峰 (summer) | peak-time demand − 經常契約 |
| 尖峰 (non-summer) | peak-time demand − (經常 + 非夏月契約) |
| 週六半尖峰 | Saturday demand − (經常 + 非夏月 + 週六半尖峰契約) |
| 離峰 | off-peak demand − (all four contracts) |

A three-stage plan's 尖峰 excess is over the 經常契約 in both seasons. A 半尖峰 row follows it, half-peak demand − (經常 + 半尖峰契約), and 半尖峰契約 takes the place of 非夏月契約 in the later rows. A later time leaves out the largest excess before it, so no kW is counted twice. Each excess is billed at its own contract's basic fee rate (超出部分依適用電價).

**Penalty Rates:**

| Over-contract Amount | Penalty Rate |
|---------------------|--------------|
| Within 10% of contract | **2×** basic fee rate |
| Exceeds 10% of contract | **3×** basic fee rate (for the excess portion) |

**Example:**
- Contract: 200 kW
- Actual peak: 230 kW
- Over-contract: 30 kW (15% over)
- Penalty calculation:
  - First 20 kW (10%): 20 × Rate × 2
  - Remaining 10 kW: 10 × Rate × 3

Each time's 10% is taken of the contracts its excess is over, the sum in its
row above, less the kW earlier times already billed. With a 200 kW 經常契約
alone, 230 kW at 尖峰 and 240 kW at 離峰, 離峰 bills 10 kW, all at 3×, since
尖峰's 30 kW used up the 20 kW. The tariff does not say which contract the
10% means, and no Taipower example has a 10% split after 尖峰 or with more
than one contract. This is the package's reading, the one the per-time
formulas and a 2015 paper (Journal of Energy and Power Engineering 9:660)
use. A published 離峰 example (POXA, 2026) rules out taking it of that time's
own contract alone. `docs/references/README.md` lists what was searched.
最高需量 counts whole kW, dropping the fraction (營業規章施行細則
第二十八條), so 205.9 kW on a 200 kW contract is 5 kW over.

`over_contract_kw` gives the 超約 kW over the 經常契約 at 尖峰 directly. It
applies to every bill in the usage, in place of the 超約 from `demand_kw`.

A customer may contract for 週六半尖峰 or 離峰 time alone (第八章 二(一)8).
Use at other times then pays 4.8× that time's basic fee rate on its highest
demand and 1.6× its energy price, in place of 超約. Such a customer pays
按戶計收 on 三段式 plans too. The 三段式 sentence leaves 按戶 out, but its rule
is 按戶及按契約容量計算 and its table lists 按戶計收 with no exception. No
Taipower example settles it.

A 裝置契約 customer with `demand_kw` pays no 超約. When the demand passes the
裝置契約 kW, Taipower moves the bill to 需量契約電價, at a contract the tariff
does not give, so the package warns and asks for `contract_capacities`.

高壓 and 特高壓 夏月 runs from 5/16 to 10/15, so May and October are part
非夏月 and part 夏月. The 電價表 does not say how such a month pays its basic
fee and 超約. The package bills it like a month whose prices change
mid-month (營業規章 第二十七條, 營業規章施行細則 第三十六條). Each season's
part pays that season's basic fee, and its own 超約 from its own highest
demand at that season's contracts and prices, weighted by its share of the
bill's days. This is the package's reading. With 200 kW 經常契約 and 50 kW
非夏月契約 on `high_voltage_2_tier`, May 2026 pays 15/31 × 166.90 × 250 +
16/31 × 223.60 × 200 = 43,270.8 TWD of basic fee. A two-month bill over the
6/1 or 10/1 edge, such as a 表燈 bill for May and June, is weighted by days
the same way, 31/61 and 30/61. The breakdown's `basic_details` lists each
fee once per season, with that season's `share` of the bill's days.

---

### 3. Power Factor Adjustment (功率因數調整)

The tariff changes the month's bill (該月份電費), basic fee plus energy cost,
by 0.1% for each 1% of power factor away from 80%. A power factor above 95%
counts as 95%. The 按戶計收 basic fee is left out. Over-contract fees get no
discount, but below 80% they get the surcharge with the rest of the bill
(營業規章施行細則 第三十條). A month with no kWh counts as 80% (第三十八條),
even when it is billed its 底度.

```
功率因數調整 = (基本電費 − 按戶計收 + 流動電費 [+ 超約, below 80%]) × (80% − 實際功率因數%) × 0.1%
```

Only the bills the tariff names are adjusted: three-phase 表燈 bills (a
標準型 one only with contracts of 20 kW or more), three-phase 低壓 bills with
a 裝置契約 of 20 kW or more or 需量契約 of 30 kW or more, and every 高壓 and
特高壓 bill. A bill without
`meter_phase` counts as three-phase. A value of 1 or less, such as 0.95,
raises `InvalidBillingInput`.

| Power Factor | Result | Example |
|--------------|--------|---------|
| **> 80%** (base) | Discount | 95% PF → 1.5% off the month's bill |
| **< 80%** (base) | Surcharge | 75% PF → 0.5% added to the month's bill |
| **Max discount** | Up to 95% PF | Max discount = (95-80) × 0.1% = 1.5% |

---

### 4. Complete Bill Example (完整帳單範例)

**Scenario:** `high_voltage_2_tier` in July 2026 (summer), 200 kW 經常契約,
a 230 kW peak on a weekday afternoon and 95% power factor.

| Item | Calculation | Amount (TWD) |
|------|-------------|--------------|
| Energy Cost (Peak) | 10,000 kWh × $6.75 | 67,500 |
| Energy Cost (Off-peak) | 20,000 kWh × $2.71 | 54,200 |
| **Energy Cost (Subtotal)** | 121,700 (sum) | **121,700** |
| Basic Fee | 200 kW × $223.60 | 44,720 |
| Penalty | (20 × 2 + 10 × 3) kW × $223.60 | 15,652 |
| PF Discount | -(44,720 + 121,700) × 1.5% | -2,496.30 |
| **Total** | 179,575.70 (sum) | **179,575.70** |

`calculate_bill` gives the same items, with the penalty and the discount
together in `adjustment` (13,155.70). Its total is 179,576, rounded to the
元 as Taipower bills.

Taipower reads each bill's kWh to the whole kWh, half up, and its 最高需量
to the whole kW, dropping the fraction (營業規章施行細則 第二十八條). It cuts
each bill item (energy, basic fee, 超約, 功率因數) to the 角, dropping the 分,
and rounds the total half up to the 元 (第二十九條). `calculate_bill` does
the same. A plan without time-of-use prices has one reading, the bill's
kWh. 第二十八條 does not say how a time-of-use meter is read. The package
reads each time, 尖峰, 半尖峰, 週六半尖峰 and 離峰, on its own and rounds
each, since each is priced on its own kWh. This is the package's reading.
A reading's whole kWh are spread over its intervals in proportion to their
kWh, so a bill over two seasons keeps each season's share. The bill prices
the read kWh and compares them with the 2000 kWh of 加計 and with the 底度.
A month that reads 0 kWh, such as one with 0.4 kWh, had no use. 功率因數 is
worked from the cut items. Pass `BillingInputs(taipower_rounding=False)` to
keep every kWh and amount unrounded, for example to compare plans or
optimize a load. 最高需量 is whole kW either way, so the bill steps at each
kW of demand.

A `high_voltage_ev` bill lists the `low_voltage_ev` amounts and pays 95% of
their total rounded to the 元, as Taipower's 各類電價表及計算範例 works it
(89,729元×95%=85,243元). `adjustment` takes off the 5%. `calculate_costs`
and `pricing_context` give its prices at 95%.

### Rules the package does not apply

Tests mark each of these as an expected failure, since no input describes
the customer or the decision is open:

- 包制電價, the 電價表's 第一章 包燈 and 第二章 包用電力.
- 免計營業稅 customers, 公用路燈, 農業動力 and the 軍眷 and 退休 family discounts.
- Transformer losses, since 變壓器容量 is not an input.
- 用電設備容量 (kVA) for 表燈 power factor eligibility.
- 儲冷式空調 off-peak energy at 60%.
- 充換電設備 capacity checks for the EV tariff.
- 三段式尖峰時間可變動時間電價. Taipower tells each customer its 指定 days the
  day before, and no public list exists.
- 自備 161 kV or 345 kV substation discounts and 常閉環路 or backup lines.
- A contract change within a month (營業規章 第二十七條). One `BillingInputs`
  covers all the usage.
- The basic fee taken off for outage and 卸載 hours (營業規章 第三十九、四十條).

The 電價表's 第六章 臨時用電 and 第七章 備用電力 have no plan here either.

Tariff clauses and their tests are listed in `tests/data/clauses/`. The
documents behind them are in `docs/references/`.

---

### 5. Data Resolution Requirements (資料解析度要求)

Taipower's 需量 is a 15-minute average (營業規章 第三條), and the 電價表 sets
a 需量契約容量 on it (第八章 二: 以雙方約定最高需量（15分鐘平均）為契約容量).
臺電規定：契約容量與超約以 **15 分鐘平均** 需量計算。

| Calculation Type | Resolution | Notes |
|------------------|------------|-------|
| Energy Cost (電能費) | Hourly or finer, 30 minutes or finer for 批次生產 | [Step 1](#step-1-prepare-your-time-series-data-準備時間序列資料). Tiered plans take any resolution. |
| Demand Penalty (違約金) | **15 minutes** | Coarser data understates the peak |
| Basic Fee (基本費) | N/A | Based on contract capacity, not usage |

Readings finer than 15 minutes, such as every 5 minutes, are averaged over
each quarter hour before the month's highest is taken. `calculate_bill`
warns when the median gap between `demand_kw` readings is over 15 minutes. An hourly
average can understate a 15-minute peak by up to 75%, when the other three
quarters are 0. `demand_adjustment_factor` multiplies every reading, and the
warning suggests 1.1-1.2 for hourly data. That figure is a guess, not a
Taipower rule. In this example 1.15 does not bring back the peak that an
hourly average hides:

```python
july = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
usage_15min = pd.Series(25.0, index=july)  # 100 kW all month
demand_15min = pd.Series(100.0, index=july)
demand_15min["2026-07-15 14:15"] = 230.0

inputs = BillingInputs(contract_capacities={"regular": 200}, demand_kw=demand_15min)
bill = calculate_bill(usage_15min, "high_voltage_2_tier", inputs=inputs)
print(bill["adjustment"].iloc[0])  # 15652.0, (20 × 2 + 10 × 3) kW × 223.60

# The same demand as hourly averages: 132.5 kW at 14:00, no 超約, and a warning
inputs = BillingInputs(
    contract_capacities={"regular": 200},
    demand_kw=demand_15min.resample("h").mean(),
    demand_adjustment_factor=1.15,
)
bill = calculate_bill(usage_15min, "high_voltage_2_tier", inputs=inputs)
print(bill["adjustment"].iloc[0])  # 0.0
```

`demand_kw` is read on its own timestamps, not on those of `usage`, so
hourly `usage` with 15-minute `demand_kw` bills every quarter hour.
Timezone-aware demand is read in Taiwan time, like usage. Each 15-minute
average is multiplied by `demand_adjustment_factor`, cut to the whole kW
(第二十八條), and counts in the bill, season and time of its own timestamp.
Readings outside the bills of `usage` are not billed.

## Public API Index (公開 API 總覽)

`taipower_tou` exports every function and class below. `docs/api_zh.md` describes them in 中文.

### Plans (方案)
- `available_plans()` returns `{plan_id: 中文名稱}` for the 18 plans.
- `plan(name)` returns a `TariffPlan`. `name` is a plan ID, its name in `available_plans()`, or the plan's full name (`tou.plan(plan_id).name`), ignoring case and surrounding spaces. Part of a name works when no other plan contains it, so `"住宅用"` names `residential_non_tou`, while `"批次"` is in two plans' names. A name that matches no plan or more than one raises `UnknownPlanError`. `calculate_bill` and the other functions that take a plan name match it the same way.
- `plan_details(name)` and `TariffPlan.describe()` return a plan's seasons, day types, schedules and prices.
- `get_plan_requirements(name)` says whether a plan needs a contract or meter details and lists its `basic_fee_inputs` labels. `PlanRequirements` holds the same fields.
- `TariffFactory` builds a `TariffPlan` from the bundled data with a calendar of your choice.
- `residential_simple_2_tier_plan()`, `high_voltage_2_tier_plan()` and `residential_non_tou_plan()` are `plan(...)` for those plans.

### Time and price (時段與費率)
- `period_at`, `period_context` and `pricing_context` take a datetime and a plan name. `get_period` and `get_context` take a `TariffProfile`. A `pandas.DatetimeIndex` in place of the datetime returns a Series or DataFrame.

### Costs and bills (電費與帳單)
- `TariffPlan.calculate_costs`, `costs(usage, name)` and `calculate_costs(usage, plan)` return the energy cost per month.
- `TariffPlan.monthly_breakdown` and `monthly_breakdown(usage, name)` return kWh and cost per month, season and period. `include_shares=True` adds each row's share of its month.
- `calculate_bill` returns one row per bill. `calculate_bill_simple` is `calculate_bill` with no `BillingInputs`. `calculate_bill_from_list` and `calculate_bill_from_dict` take a list or dict in place of a Series.
- `calculate_bill_breakdown` returns a dict of DataFrames: `summary` (the bill items, `min_fee_adjustment` and `total`), `details` (kWh and energy cost per bill, season and period), `basic_details` (each basic fee's `season`, `share`, `quantity`, `rate` and `cost`) and `adjustment_details` (each 超約, 功率因數 or other adjustment).
- `BillingInputs` holds a bill's inputs. `BillingInputs.for_high_voltage`, `for_high_voltage_three_stage`, `for_extra_high_voltage`, `for_extra_high_voltage_three_stage`, `for_residential` and `for_lighting_standard` build common ones.
- `BillingCycleType` is `MONTHLY`, `ODD_MONTH` or `EVEN_MONTH`.

### Calendars (日曆)
- `taiwan_calendar()` returns a `TaiwanCalendar` of Taipower's off-peak days, and `is_holiday` asks it about a day.
- `custom_calendar(holidays=..., weekend_days=...)` returns a `CustomCalendar` of your own days. It takes `date` objects, not strings.

### Custom plan builders (自定義方案)
- `build_tariff_profile`, `build_day_schedule`, `build_tariff_rate` and `build_tariff_plan`, with `TaiwanSeasonStrategy`, `TaiwanDayTypeStrategy` and `WeekdayDayTypeStrategy`. See [Custom Plans](#custom-plans-自定義費率).

### Types & enums (型別與列舉)
- `TariffPlan`, `TariffProfile`, `PeriodType`, `SeasonType`.

### Errors (錯誤型別)
- `PowerKitError` is the base of `CalendarError`, `TariffError`, `InvalidUsageInput`, `MissingRequiredInput`, `InvalidBillingInput` and `UnknownPlanError`.
- `InvalidBillingInput` is also a `ValueError`, and `InvalidBasicFeeInput` is an `InvalidBillingInput`. `UnknownPlanError` is also a `ValueError` and a `KeyError`.
- `UncheckedPriceWarning`, `UncheckedYearWarning` and `PartialPeriodWarning` are `UserWarning`s.

## API Examples (公開 API 範例)

```python
from datetime import date

from taipower_tou import PowerKitError, TariffFactory, calculate_bill_breakdown

print(tou.plan_details("residential_simple_2_tier")["profile"]["name"])
# 簡易型時間電價-二段式
print(tou.get_plan_requirements("high_voltage_2_tier")["valid_basic_fee_labels"])

# 150 kW of 週六半尖峰契約 pays for 150 - 200 × 0.5 = 50 kW
inputs = BillingInputs(contract_capacities={"regular": 200, "saturday_semi_peak": 150})
breakdown = calculate_bill_breakdown(july_usage, "high_voltage_2_tier", inputs=inputs)
print(breakdown["basic_details"])
#       period    label  season  share  quantity   rate     cost
# 0 2026-07-01     經常契約  summer    1.0     200.0  223.6  44720.0
# 1 2026-07-01  週六半尖峰契約  summer    1.0      50.0   44.7   2235.0

calendar = tou.custom_calendar(holidays=[date(2026, 1, 2)])
print(calendar.is_holiday(datetime(2026, 1, 2)))  # True
plan = TariffFactory.create("residential_simple_2_tier", calendar=calendar)

try:
    tou.plan("unknown_plan")
except PowerKitError as exc:
    print("powerkit error:", exc)
```

## Available Plans (可用方案)

18 Taipower plans are supported. Plans are organized by billing type:
支援 18 種臺電方案，按計費方式分類：

### Tiered Rate Plans (累進費率方案)

Rates increase progressively based on monthly usage volume. `calculate_bill` bills them every two months by default.
費率隨每月用電量逐級上調。`calculate_bill` 預設兩個月一期。

| Category | Plan ID | 中文名稱 |
|----------|---------|---------|
| **Residential** | `residential_non_tou` | 表燈非時間電價 |
| **Lighting** | `lighting_non_business_tiered` | 表燈非時間-住宅非營業 |
| **Lighting** | `lighting_business_tiered` | 表燈非時間-營業用 |

### Time-of-Use Plans (時間電價方案)

Rates vary by time period, season, and day type. `low_voltage_power` has one price per season at any hour.
費率隨時段、季節和日期型別變動。`low_voltage_power` 每季只有一種單價，不分時段。

| Category | Plan ID | 中文名稱 |
|----------|---------|---------|
| **Residential** | `residential_simple_2_tier` | 簡易型二段式 |
| **Residential** | `residential_simple_3_tier` | 簡易型三段式 |
| **Lighting** | `lighting_standard_2_tier` | 標準型二段式 |
| **Lighting** | `lighting_standard_3_tier` | 標準型三段式 |
| **Low Voltage** | `low_voltage_2_tier` | 低壓電力二段式 |
| **Low Voltage** | `low_voltage_three_stage` | 低壓電力三段式 |
| **Low Voltage** | `low_voltage_ev` | 低壓電動車 |
| **Low Voltage** | `low_voltage_power` | 低壓電力非時間 |
| **High Voltage** | `high_voltage_2_tier` | 高壓電力二段式 |
| **High Voltage** | `high_voltage_three_stage` | 高壓電力三段式 |
| **High Voltage** | `high_voltage_ev` | 高壓電動車 |
| **High Voltage** | `high_voltage_batch` | 高壓批次生產 |
| **Extra High Voltage** | `extra_high_voltage_2_tier` | 特高壓電力二段式 |
| **Extra High Voltage** | `extra_high_voltage_three_stage` | 特高壓電力三段式 |
| **Extra High Voltage** | `extra_high_voltage_batch` | 特高壓批次生產 |

The 電價表 has no 高壓 or 特高壓 非時間電價, so 0.2.0 removed `high_voltage_power` and `extra_high_voltage_power`. Asking for one raises an error that names the 二段式 plan, which bills the same.
電價表沒有高壓與特高壓非時間電價，0.2.0 移除了 `high_voltage_power` 與 `extra_high_voltage_power`。使用這兩個名稱會拋出錯誤，並指出計費相同的二段式方案。

## Custom Plans (自定義費率)

Build a plan with your own seasons, day types, hours and prices when no bundled plan fits. A custom plan has `calculate_costs`, `monthly_breakdown` and `pricing_context`, but `calculate_bill` takes only the bundled plans. A day type with no schedule takes `default_period`, and a season and period with no price cost 0.

```python
from taipower_tou import (
    TaiwanSeasonStrategy,
    WeekdayDayTypeStrategy,
    build_tariff_plan,
    build_tariff_profile,
    build_tariff_rate,
)

season_strategy = TaiwanSeasonStrategy(summer_start=(6, 1), summer_end=(9, 30))
# "weekday", "saturday" and "sunday", or "holiday" on the calendar's days
day_type_strategy = WeekdayDayTypeStrategy(tou.custom_calendar())

profile = build_tariff_profile(
    name="demo_plan",
    season_strategy=season_strategy,
    day_type_strategy=day_type_strategy,
    schedules=[
        {
            "season": season,
            "day_type": "weekday",
            "slots": [
                {"start": "09:00", "end": "24:00", "period": "peak"},
                {"start": "00:00", "end": "09:00", "period": "off_peak"},
            ],
        }
        for season in ("summer", "non_summer")
    ],
    default_period="off_peak",
)
rates = build_tariff_rate(
    period_costs=[
        {"season": "summer", "period": "peak", "cost": 5.0},
        {"season": "summer", "period": "off_peak", "cost": 2.0},
        {"season": "non_summer", "period": "peak", "cost": 4.0},
        {"season": "non_summer", "period": "off_peak", "cost": 1.5},
    ],
    season_strategy=season_strategy,
)
custom_plan = build_tariff_plan(profile=profile, rates=rates)
print(custom_plan.calculate_costs(usage_series).iloc[0])  # 32.8, 2.4 × 2.0 + 5.6 × 5.0
```

## Performance (效能)

Costs and bills look up each timestamp's season and day type once per date, and its period in a table of the 1440 minutes of the day. Each year's off-peak days are computed once per process.

## Quality & Testing (品質與測試)

The tests check these:

- Every day of 2014–2027 against Taipower's 時間電價日曆表 (`tests/data/taipower_calendar/`).
- Every price in `plans.json` against the bundled 電價表 text, and every plan at every half hour against `tests/data/tariff_114_10_01.json`, a transcription of the 電價表 that gives each number's source line.
- Each clause of the 電價表's 第三、四、五、八章 and of every chapter of the 營業規章 and its 施行細則 (`tests/data/clauses/`). A clause that changes a bill names its tests, and the others say why no bill depends on them.
- The worked bills in Taipower's 各類電價表及計算範例, bills computed two ways that must agree, and the Python examples in this README and `docs/api_zh.md`.

CI runs the tests on Python 3.9 to 3.13, and runs ruff, mypy and four scripts in `examples/`.

## Acknowledgements (致謝)

- `scripts/generate_festival_dates.py` computes the 春節, 端午, 中秋 and 清明 dates with both `lunar_python` and `astronomy-engine`, and fails if they disagree.
- [ruyut/TaiwanCalendar](https://github.com/ruyut/TaiwanCalendar) supplied the holiday data of 0.1.0's calendar.

## Links (相關連結)

- **Repository:** https://github.com/JUN-WEI-DING/taipower-tou
- **Issues:** https://github.com/JUN-WEI-DING/taipower-tou/issues
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **License:** [MIT](LICENSE)
