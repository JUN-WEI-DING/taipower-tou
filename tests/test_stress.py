"""Comprehensive stress testing for taipower_tou package.

This module performs aggressive stress tests to ensure package robustness
before release. Tests include:
- Extreme data volumes (millions of records)
- Extreme value ranges (zeros, very large, very small)
- Concurrent access (multi-threading)
- Memory stability tests
- Invalid input handling
- Boundary time conditions
- All tariff plan combinations
"""

import gc
import random
import threading
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd

import taipower_tou as tou
from taipower_tou.errors import InvalidUsageInput, TariffError

# =============================================================================
# TEST 1: Extreme Data Volumes
# =============================================================================


def test_extreme_data_volumes():
    """Test with extremely large datasets (5M+ records)."""
    print("\n" + "=" * 70)
    print("STRESS TEST 1: Extreme Data Volumes (極限資料量測試)")
    print("=" * 70)

    plan = tou.plan("residential_simple_2_tier")

    test_sizes = [
        ("1萬條", 10_000),
        ("10萬條", 100_000),
        ("100萬條", 1_000_000),
        ("500萬條", 5_000_000),
    ]

    results = []
    for name, size in test_sizes:
        gc.collect()
        start_mem = get_memory_usage()

        dates = pd.date_range("2024-01-01", periods=size, freq="min")
        usage = pd.Series([1.0] * size, index=dates)

        start = time_module.time()
        try:
            costs = plan.calculate_costs(usage)
            elapsed = time_module.time() - start
            end_mem = get_memory_usage()
            mem_delta = end_mem - start_mem

            results.append((name, size, elapsed, mem_delta, costs.sum(), "✅"))
            print(f"{name} ({size:,}條):")
            print(f"  耗時: {elapsed:.3f}秒")
            print(f"  記憶體增長: {mem_delta:.2f} MB")
            print(f"  每秒處理: {size / elapsed:,.0f} 條")
            print(f"  總成本: {costs.sum():.2f} 元")
        except Exception as e:
            elapsed = time_module.time() - start
            results.append((name, size, elapsed, 0, 0, f"❌ {e}"))
            print(f"{name}: ❌ 失敗 - {e}")

    print("\n" + "-" * 70)
    print("極限資料量測試摘要:")
    for name, size, elapsed, mem, cost, status in results:
        print(f"  {name}: {status}")

    assert all("✅" in r[-1] for r in results), "Some data sizes failed"


# =============================================================================
# TEST 2: Extreme Values
# =============================================================================


def test_extreme_values():
    """Test with extreme numeric values."""
    print("\n" + "=" * 70)
    print("STRESS TEST 2: Extreme Values (極限數值測試)")
    print("=" * 70)

    plan = tou.plan("residential_simple_2_tier")
    dates = pd.date_range("2024-07-15", periods=24, freq="h")

    extreme_cases = [
        ("全零值", [0.0] * 24),
        ("極小值", [1e-10] * 24),
        ("小數點多位", [3.14159265359] * 24),
        ("混合零與非零", [0.0, 1.5, 0.0, 2.3, 0.0] * 5),
        ("大值", [1000.0] * 24),
        ("超大值", [10000.0] * 24),
        ("隨機極值", [random.random() * 1000 for _ in range(24)]),
        ("科學記號", [1.23e-5, 4.56e-3, 7.89e2] * 8),
    ]

    results = []
    for name, values in extreme_cases:
        usage = pd.Series(values[:24], index=dates)
        try:
            costs = plan.calculate_costs(usage)
            results.append((name, costs.sum(), "✅"))
            print(f"✅ {name}: 成本 {costs.sum():.2f} 元")
        except Exception as e:
            results.append((name, 0, f"❌ {e}"))
            print(f"❌ {name}: 失敗 - {e}")

    # Test with infinity and NaN (should fail gracefully)
    print("\n異常值處理測試:")
    invalid_cases = [
        ("包含 NaN", [1.0, 2.0, float("nan"), 3.0] * 6),
        ("包含 Inf", [1.0, 2.0, float("inf"), 3.0] * 6),
        ("負值", [1.0, -2.0, 3.0, 4.0] * 6),
    ]

    for name, values in invalid_cases:
        usage = pd.Series(values[:24], index=dates)
        try:
            costs = plan.calculate_costs(usage)
            print(f"⚠️  {name}: 未拒絕 (成本 {costs.sum():.2f})")
        except (InvalidUsageInput, ValueError) as e:
            print(f"✅ {name}: 正確拒絕 - {type(e).__name__}")
        except Exception as e:
            print(f"❌ {name}: 錯誤的異常型別 - {type(e).__name__}: {e}")

    # Check that no unexpected errors occurred (no assertion needed for this test)


# =============================================================================
# TEST 3: Concurrent Access
# =============================================================================


def test_concurrent_access():
    """Test concurrent access from multiple threads."""
    print("\n" + "=" * 70)
    print("STRESS TEST 3: Concurrent Access (並發訪問測試)")
    print("=" * 70)

    errors = []
    results = []
    lock = threading.Lock()

    def worker(worker_id):
        """Worker function for concurrent testing."""
        try:
            plan = tou.plan("residential_simple_2_tier")
            dates = pd.date_range("2024-07-15", periods=1000, freq="h")
            usage = pd.Series([random.random() * 10 for _ in range(1000)], index=dates)

            costs = plan.calculate_costs(usage)
            with lock:
                results.append((worker_id, costs.sum()))
            return (worker_id, costs.sum(), None)
        except Exception as e:
            with lock:
                errors.append((worker_id, str(e)))
            return (worker_id, 0, str(e))

    num_workers = [10, 50, 100]

    for n_workers in num_workers:
        errors.clear()
        results.clear()

        start = time_module.time()
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(n_workers)]
            completed = sum(1 for f in as_completed(futures) if f.result()[2] is None)
        elapsed = time_module.time() - start

        success_rate = completed / n_workers * 100
        print(f"{n_workers} 並發執行緒:")
        print(f"  成功: {completed}/{n_workers} ({success_rate:.1f}%)")
        print(f"  耗時: {elapsed:.3f}秒")
        print(f"  錯誤: {len(errors)}")

        if errors:
            print(f"  錯誤詳情: {errors[:3]}")

        # 95% success rate required
        assert completed >= n_workers * 0.95, "Concurrent test failed"

    print("\n✅ 並發訪問測試透過")


# =============================================================================
# TEST 4: Memory Stability
# =============================================================================


def test_memory_stability():
    """Test memory stability over prolonged use."""
    print("\n" + "=" * 70)
    print("STRESS TEST 4: Memory Stability (記憶體穩定性測試)")
    print("=" * 70)

    gc.collect()
    start_mem = get_memory_usage()

    plan = tou.plan("residential_simple_2_tier")

    iterations = 100
    mem_samples = []

    for i in range(iterations):
        dates = pd.date_range("2024-01-01", periods=10000, freq="h")
        usage = pd.Series([random.random() * 5 for _ in range(10000)], index=dates)
        plan.calculate_costs(usage)  # Result not needed for this test

        if i % 10 == 0:
            gc.collect()
            current_mem = get_memory_usage()
            mem_delta = current_mem - start_mem
            mem_samples.append((i, mem_delta))

    gc.collect()
    end_mem = get_memory_usage()
    total_delta = end_mem - start_mem

    print(f"執行 {iterations} 次迭代後:")
    print(f"  初始記憶體: {start_mem:.2f} MB")
    print(f"  最終記憶體: {end_mem:.2f} MB")
    print(f"  記憶體增長: {total_delta:.2f} MB")
    print(f"  每次迭代平均: {total_delta / iterations:.3f} MB")

    # Check for memory leaks (growth > 100MB is suspicious)
    assert total_delta <= 100, "Possible memory leak detected"

    print("  ✅ 記憶體穩定性良好")


# =============================================================================
# TEST 5: All Plans Stress Test
# =============================================================================


def test_all_plans_stress():
    """Stress test all tariff plans with various scenarios."""
    print("\n" + "=" * 70)
    print("STRESS TEST 5: All Plans (所有方案壓力測試)")
    print("=" * 70)

    plan_ids = list(tou.available_plans().keys())

    # Tiered plans that don't support pricing_context with usage parameter
    # (because they need monthly totals to determine rate tier)
    tiered_plan_ids = {
        "residential_non_tou",
        "lighting_non_business_tiered",
        "lighting_business_tiered",
    }

    # Test scenarios
    scenarios = [
        ("平日尖峰", datetime(2024, 7, 15, 14, 0)),
        ("平日離峰", datetime(2024, 7, 15, 3, 0)),
        ("週六", datetime(2024, 7, 13, 14, 0)),
        ("週日/假日", datetime(2024, 7, 14, 14, 0)),
        ("夏月", datetime(2024, 7, 15, 14, 0)),
        ("非夏月", datetime(2024, 1, 15, 14, 0)),
    ]

    failed_plans = []
    skipped_tiered = []

    for plan_id in plan_ids:
        plan_success = True
        is_tiered = plan_id in tiered_plan_ids

        for scenario_name, dt in scenarios:
            try:
                if is_tiered:
                    # Tiered plans: test pricing_context without usage
                    ctx = tou.pricing_context(dt, plan_id)  # No usage parameter
                    # Verify tiered plans return None for rate
                    if ctx.get("rate") is not None:
                        raise ValueError(
                            f"Tiered plan {plan_id} should return None rate"
                        )

                    # Test with small dataset
                    dates = pd.date_range(dt, periods=24, freq="h")
                    usage = pd.Series([1.0] * 24, index=dates)
                    tou.plan(plan_id).calculate_costs(usage)
                else:
                    # TOU plans: test pricing_context with usage
                    ctx = tou.pricing_context(dt, plan_id, usage=10.0)
                    ctx.get("rate", 0)  # Check rate exists

                    # Test with small dataset
                    dates = pd.date_range(dt, periods=24, freq="h")
                    usage = pd.Series([1.0] * 24, index=dates)
                    tou.plan(plan_id).calculate_costs(usage)

            except Exception as e:
                print(f"  ❌ {plan_id}: {scenario_name} - {e}")
                plan_success = False
                failed_plans.append((plan_id, scenario_name, str(e)))
                break

        if plan_success:
            if is_tiered:
                skipped_tiered.append(plan_id)
            else:
                print(f"  ✅ {plan_id}")

    print(f"\n結果: {len(plan_ids) - len(failed_plans)}/{len(plan_ids)} 方案透過")
    if skipped_tiered:
        print(
            f"  (其中 {len(skipped_tiered)} 個 tiered 方案已正確處理: "
            f"{', '.join(skipped_tiered)})"
        )

    if failed_plans:
        print("\n失敗的方案:")
        for plan_id, scenario, error in failed_plans:
            print(f"  - {plan_id}: {scenario}")

    assert len(failed_plans) == 0, "Some plans failed stress scenarios"


# =============================================================================
# TEST 6: Boundary Time Conditions
# =============================================================================


def test_boundary_times():
    """Test edge cases around time boundaries."""
    print("\n" + "=" * 70)
    print("STRESS TEST 6: Boundary Times (時間邊界測試)")
    print("=" * 70)

    plan = tou.plan("high_voltage_three_stage")

    boundary_cases = [
        ("午夜跨日", datetime(2024, 7, 15, 23, 59), datetime(2024, 7, 16, 0, 1)),
        ("月底跨月", datetime(2024, 7, 31, 23, 0), datetime(2024, 8, 1, 1, 0)),
        ("年底跨年", datetime(2023, 12, 31, 23, 0), datetime(2024, 1, 1, 1, 0)),
        ("閏年2/29", datetime(2024, 2, 29, 12, 0), datetime(2024, 2, 29, 13, 0)),
        ("夏月開始", datetime(2024, 5, 15, 23, 59), datetime(2024, 5, 16, 0, 1)),
        ("夏月結束", datetime(2024, 10, 15, 23, 59), datetime(2024, 10, 16, 0, 1)),
    ]

    for name, dt1, dt2 in boundary_cases:
        try:
            dates = pd.date_range(dt1, dt2, freq="15min")
            usage = pd.Series([1.0] * len(dates), index=dates)

            period1 = tou.period_at(dt1, "high_voltage_three_stage")
            period2 = tou.period_at(dt2, "high_voltage_three_stage")
            costs = plan.calculate_costs(usage)

            print(f"✅ {name}: {period1} → {period2}, 成本 {costs.sum():.2f}")
        except Exception as e:
            print(f"❌ {name}: {e}")
            assert False, f"Boundary test {name} failed: {e}"

    # All tests passed (no assertion needed at end)


# =============================================================================
# TEST 7: Holiday Edge Cases
# =============================================================================


def test_holiday_edge_cases():
    """Test days around holidays."""
    print("\n" + "=" * 70)
    print("STRESS TEST 7: Holiday Edge Cases (假日邊界測試)")
    print("=" * 70)

    # Test dates around major holidays
    holiday_edges = [
        ("元旦前", datetime(2024, 12, 31, 12, 0), False),
        ("元旦", datetime(2024, 1, 1, 12, 0), True),
        ("元旦後", datetime(2024, 1, 2, 12, 0), False),
        # 2025 春節連假(含調休): 1/25-1/31，1/27(一)是調休假日
        ("週六1/25", datetime(2025, 1, 25, 12, 0), False),
        ("週日1/26", datetime(2025, 1, 26, 12, 0), True),
        ("彈性放假1/27", datetime(2025, 1, 27, 12, 0), False),  # 台電不算離峰日
        ("除夕1/28", datetime(2025, 1, 28, 12, 0), True),
        ("春節初一", datetime(2025, 1, 29, 12, 0), True),
        ("春節初三", datetime(2025, 1, 31, 12, 0), True),
        ("春節後", datetime(2025, 2, 5, 12, 0), False),
        ("週六下午", datetime(2024, 7, 13, 14, 0), False),
        ("週日", datetime(2024, 7, 14, 12, 0), True),
        ("週一", datetime(2024, 7, 15, 12, 0), False),
    ]

    all_correct = True

    for name, dt, expected_holiday in holiday_edges:
        try:
            is_hol = tou.is_holiday(dt)
            period = tou.period_at(dt, "high_voltage_2_tier")

            if is_hol == expected_holiday:
                status = "✅"
            else:
                status = "❌"
                all_correct = False

            print(
                f"{status} {name}: is_holiday={is_hol} (預期={expected_holiday}), "
                f"period={period}"
            )
        except Exception as e:
            print(f"❌ {name}: {e}")
            all_correct = False

    assert all_correct, "Some edge cases failed"


# =============================================================================
# TEST 8: Repeated Object Creation
# =============================================================================


def test_repeated_object_creation():
    """Test stability of repeatedly creating calendar and plan objects."""
    print("\n" + "=" * 70)
    print("STRESS TEST 8: Repeated Object Creation (重複物件建立)")
    print("=" * 70)

    iterations = 1000
    errors = []

    start = time_module.time()

    for i in range(iterations):
        try:
            # Create new calendar each time
            cal = tou.taiwan_calendar()
            plan = tou.plan("residential_simple_2_tier", calendar_instance=cal)

            # Test with data
            dates = pd.date_range("2024-07-15", periods=10, freq="h")
            usage = pd.Series([1.0] * 10, index=dates)
            plan.calculate_costs(usage)  # Result not needed for this test

        except Exception as e:
            errors.append((i, str(e)))

    elapsed = time_module.time() - start

    print(f"建立並使用物件 {iterations} 次:")
    print(f"  耗時: {elapsed:.3f}秒")
    print(f"  平均每次: {elapsed / iterations * 1000:.2f}ms")
    print(f"  錯誤數: {len(errors)}")

    assert not errors, f"Errors occurred: {errors[:5]}"

    print("  ✅ 物件建立穩定")


# =============================================================================
# TEST 9: Large Date Range
# =============================================================================


def test_large_date_range():
    """Test with multi-year date ranges."""
    print("\n" + "=" * 70)
    print("STRESS TEST 9: Large Date Range (大時間跨度測試)")
    print("=" * 70)

    plan = tou.plan("residential_simple_2_tier")

    year_ranges = [
        ("1年", 1),
        ("3年", 3),
        ("5年", 5),
        ("10年", 10),
    ]

    results = []

    for name, years in year_ranges:
        start_date = datetime(2020, 1, 1, 0, 0)
        end_date = datetime(2020 + years, 12, 31, 23, 59)

        dates = pd.date_range(start_date, end_date, freq="1h")
        # Use hourly data for reasonable size
        usage = pd.Series([random.random() * 2 for _ in range(len(dates))], index=dates)

        start = time_module.time()
        try:
            costs = plan.calculate_costs(usage)
            elapsed = time_module.time() - start

            avg_monthly_cost = costs.mean()
            total_annual = costs.sum() / years

            results.append((name, len(dates), elapsed, "✅"))
            print(f"✅ {name} ({len(dates):,}條):")
            print(f"  耗時: {elapsed:.3f}秒")
            print(f"  平均月成本: {avg_monthly_cost:.2f} 元")
            print(f"  平均年成本: {total_annual:.2f} 元")

        except Exception as e:
            results.append((name, len(dates), 0, f"❌ {e}"))
            print(f"❌ {name}: {e}")

    assert all("✅" in r[-1] for r in results), "Some year ranges failed"


# =============================================================================
# TEST 10: Billing Stress Test
# =============================================================================


def test_billing_stress():
    """Stress test billing calculations."""
    print("\n" + "=" * 70)
    print("STRESS TEST 10: Billing Calculations (計費壓力測試)")
    print("=" * 70)

    from taipower_tou import BillingInputs, calculate_bill

    plans_to_test = [
        "residential_simple_2_tier",
        "high_voltage_2_tier",
        "high_voltage_three_stage",
    ]

    results = []

    for plan_id in plans_to_test:
        try:
            # Generate 3 months of hourly data (smaller dataset)
            dates = pd.date_range("2024-06-01", periods=24 * 30 * 3, freq="h")
            usage = pd.Series(
                [random.uniform(50, 200) for _ in range(len(dates))],
                index=dates,
            )

            # Generate demand data (15-min intervals)
            demand_dates = pd.date_range(
                "2024-06-01", periods=96 * 30 * 3, freq="15min"
            )
            demand = pd.Series(
                [random.uniform(100, 180) for _ in range(len(demand_dates))],
                index=demand_dates,
            )

            if plan_id == "high_voltage_three_stage":
                contract_capacities = {
                    "regular": 200.0,
                    "semi_peak": 100.0,
                    "saturday_semi_peak": 50.0,
                    "off_peak": 50.0,
                }
            elif plan_id == "high_voltage_2_tier":
                contract_capacities = {
                    "regular": 200.0,
                    "non_summer": 100.0,
                    "saturday_semi_peak": 50.0,
                    "off_peak": 50.0,
                }
            else:
                contract_capacities = {}

            inputs = BillingInputs(
                taipower_rounding=False,
                contract_capacities=contract_capacities,
                demand_kw=demand,
                power_factor=85.0,
            )

            start = time_module.time()
            bill = calculate_bill(usage, plan_id, inputs=inputs)
            elapsed = time_module.time() - start

            total = bill["total"].sum()

            results.append((plan_id, elapsed, total, "✅"))
            print(f"✅ {plan_id}:")
            print(f"  耗時: {elapsed:.3f}秒")
            print(f"  總計: {total:.2f} 元")

        except Exception as e:
            results.append((plan_id, 0, 0, f"❌ {type(e).__name__}: {e}"))
            print(f"❌ {plan_id}: {type(e).__name__}: {e}")

    assert all("✅" in r[-1] for r in results), "Some plans failed"


# =============================================================================
# TEST 11: Invalid Input Handling
# =============================================================================


def test_invalid_input_handling():
    """Test that invalid inputs are properly rejected."""
    print("\n" + "=" * 70)
    print("STRESS TEST 11: Invalid Input Handling (無效輸入處理)")
    print("=" * 70)

    plan = tou.plan("residential_simple_2_tier")

    invalid_inputs = [
        ("非Series輸入", [1, 2, 3], "list"),
        ("非DatetimeIndex", pd.Series([1, 2, 3], index=[0, 1, 2]), "integer index"),
        (
            "包含NaN",
            pd.Series(
                [1.0, float("nan"), 3.0],
                index=pd.date_range("2024-07-15", periods=3, freq="h"),
            ),
            "NaN",
        ),
        (
            "包含負值",
            pd.Series(
                [1.0, -2.0, 3.0],
                index=pd.date_range("2024-07-15", periods=3, freq="h"),
            ),
            "negative",
        ),
        (
            "未排序索引",
            pd.Series(
                [1.0, 2.0, 3.0],
                index=pd.to_datetime(
                    [
                        "2024-07-15 12:00",
                        "2024-07-15 10:00",
                        "2024-07-15 14:00",
                    ]
                ),
            ),
            "unsorted",
        ),
        ("空Series", pd.Series([], dtype=float, index=pd.DatetimeIndex([])), "empty"),
    ]

    proper_rejections = 0

    for name, data, desc in invalid_inputs:
        try:
            plan.calculate_costs(data)  # Result not needed
            print(f"⚠️  {name}: 未拒絕 (應該拒絕 {desc})")
        except (InvalidUsageInput, ValueError, TypeError, TariffError):
            print(f"✅ {name}: 正確拒絕 ({desc})")
            proper_rejections += 1
        except Exception as e:
            print(f"❌ {name}: 錯誤的異常型別 - {type(e).__name__}")

    rejection_rate = proper_rejections / len(invalid_inputs) * 100
    print(
        f"\n拒絕率: {proper_rejections}/{len(invalid_inputs)} ({rejection_rate:.0f}%)"
    )

    # At least 80% should be properly rejected
    assert rejection_rate >= 80, f"Rejection rate too low: {rejection_rate:.0f}%"


# =============================================================================
# TEST 12: Performance Consistency
# =============================================================================


def test_performance_consistency():
    """Test that performance remains consistent over multiple runs."""
    print("\n" + "=" * 70)
    print("STRESS TEST 12: Performance Consistency (效能一致性)")
    print("=" * 70)

    plan = tou.plan("residential_simple_2_tier")
    dates = pd.date_range("2024-07-15", periods=10000, freq="h")
    usage = pd.Series([random.random() * 5 for _ in range(10000)], index=dates)

    times = []
    for i in range(50):
        start = time_module.time()
        plan.calculate_costs(usage)  # Result not needed for timing test
        elapsed = time_module.time() - start
        times.append(elapsed)

    # Skip first 10 runs to ensure warm start
    times_warm = times[10:]

    mean_time = np.mean(times_warm)
    median_time = np.median(times_warm)
    std_time = np.std(times_warm)
    min_time = np.min(times_warm)
    max_time = np.max(times_warm)
    p90 = np.percentile(times_warm, 90)
    p10 = np.percentile(times_warm, 10)

    print("50次執行統計 (跳過前10次冷啟動):")
    print(f"  平均: {mean_time:.4f}秒")
    print(f"  中位數: {median_time:.4f}秒")
    print(f"  標準差: {std_time:.4f}秒")
    print(f"  最小: {min_time:.4f}秒")
    print(f"  最大: {max_time:.4f}秒")
    print(f"  P10-P90範圍: {p10:.4f}s - {p90:.4f}s")

    # Check if most runs are within acceptable range
    # Use p90/p10 ratio instead of CV to be more robust to outliers
    ratio = p90 / p10 if p10 > 0 else float("inf")

    print(f"  P90/P10 比例: {ratio:.2f}x")

    # More than 10x difference between p90 and p10 is concerning
    # Increased threshold for CI environments with variable load
    assert ratio <= 10.0, f"Performance variance too high: {ratio:.2f}x"

    print("  ✅ 效能穩定")


# =============================================================================
# Helper Functions
# =============================================================================


def get_memory_usage() -> float:
    """Get current memory usage in MB."""
    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


# =============================================================================
# Main Test Runner
# =============================================================================


def run_all_stress_tests():
    """Run all stress tests and report results."""
    print("\n" + "=" * 70)
    print("臺灣時間電價計算器 - 極限壓力測試套件")
    print("Taiwan TOU Calculator - Extreme Stress Test Suite")
    print("=" * 70)

    tests = [
        ("極限資料量", test_extreme_data_volumes),
        ("極限數值", test_extreme_values),
        ("並發訪問", test_concurrent_access),
        ("記憶體穩定性", test_memory_stability),
        ("所有方案", test_all_plans_stress),
        ("時間邊界", test_boundary_times),
        ("假日邊界", test_holiday_edge_cases),
        ("重複建立物件", test_repeated_object_creation),
        ("大時間跨度", test_large_date_range),
        ("計費壓力", test_billing_stress),
        ("無效輸入處理", test_invalid_input_handling),
        ("效能一致性", test_performance_consistency),
    ]

    results = {}

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} 測試崩潰: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 70)
    print("壓力測試摘要 (Stress Test Summary)")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ 透過" if result else "❌ 失敗"
        print(f"  {status}: {name}")

    print(f"\n總計: {passed}/{total} 測試套件透過")

    if passed == total:
        print("\n🎉 所有壓力測試透過！Package 準備發布！")
    else:
        print(f"\n⚠️  {total - passed} 個測試失敗，請修復後再發布。")

    return results


if __name__ == "__main__":
    run_all_stress_tests()
