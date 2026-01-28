# API User-Friendliness Review

I have carefully reviewed the `tou_calculator` API and identified several areas where the user experience could be improved. This report outlines the key findings and provides recommendations.

## Executive Summary

The current API is **functional but "expert-friendly" rather than "user-friendly"**. It assumes the user is comfortable with Pandas, knows exactly which inputs are required for each rate plan, and handles data preparation manually. The most critical issue is the **lack of validation for missing inputs**, which can lead to widely incorrect bills (e.g., $0 basic fee for High Voltage) without any warning.

## Key Findings

### 1. Silent Failures & Missing Validation (Critical)
*   **Issue**: Complex plans (like `high_voltage_2_tier`) require specific `BillingInputs` (e.g., `contract_capacity_kw`). If a user calls `calculate_bill(usage, "high_voltage_2_tier")` without providing these inputs, the API **silently succeeds** with a basic fee of $0.
*   **Impact**: Users may get widely inaccurate results and not know it. A high voltage connection with 0 capacity is impossible in reality.
*   **Evidence**: Verified via test script. High voltage bill calculated with 0 basic cost.

### 2. High Barrier to Entry (Pandas Dependency)
*   **Issue**: The primary entry point `calculate_bill` enforces `pd.Series` with a `pd.DatetimeIndex`.
*   **Impact**: Developers not using Pandas (e.g., building a simple web app or using standard Python lists/dicts) must learn and install Pandas just to use the library.
*   **Recommendation**: overload `calculate_bill` to accept simpler types (e.g., `list[float]` with a start date and frequency) or provide a `calculate_bill_simple_types` helper.

### 3. Complex Input Data Structures
*   **Issue**: `BillingInputs` is a large dataclass with many optional fields. It is not clear which fields are relevant for which plan.
*   **Impact**: Users have to guess or read source code to know that `contract_capacities` dictionary is needed for TOU plans, while `contract_capacity_kw` might be used for others.
*   **Recommendation**: Introduce specific input classes for different plan types (e.g., `HighVoltageInputs`, `ResidentialInputs`) or validate inputs against the tailored plan requirements at runtime.

### 4. Confusing Plan IDs
*   **Issue**: `available_plans()` returns "display names" (e.g., `"表燈非時間-營業用 Business Tiered"`), but `calculate_bill` expects "Plan IDs" (e.g., `"lighting_business_tiered"`).
*   **Mitigation**: The system does have fuzzy matching logic (`_normalize_plan_name`), which is clever but opaque.
*   **Risk**: If the fuzzy matching guesses wrong, the user might get a different plan than expected without knowing.
*   **Recommendation**: Cleanly separate `list_plan_ids()` (for API use) and `list_plan_names()` (for UI display).

### 5. Silent "Zero" on Typos
*   **Issue**: `BillingInputs.basic_fee_inputs` is a dictionary. If a user typos a key (e.g., `"househol"` instead of `"household"`), `get()` returns 0.0, and the fee is omitted.
*   **Impact**: Under-billing without errors.
*   **Recommendation**: Validate keys in `basic_fee_inputs` against the plan's known fee items.

## Recommendations for Improvement

1.  **Add Input Validation**:
    *   In `calculate_bill`, check if the selected plan requires contract capacity. If so, raise `InvalidUsageInput` if it's missing.
    *   Warn if usage resolution doesn't match the plan's expectations (partially implemented but could be stricter).

2.  **Simplify Entry Points**:
    *   Allow passing a `dict` or JSON-like object for `usage` and `inputs`.
    *   Example: `calculate_bill(usage=[1.1, 1.2...], start="2024-01-01", freq="15min", plan="...")`.

3.  **Strict Mode**:
    *   Add a `strict=True` flag to `BillingInputs` or the calculator to raise errors on unknown keys or missing fields.

4.  **Type-Safe Helpers**:
    *   Instead of a generic `BillingInputs`, provide factory methods or specific classes: `BillingInputs.for_high_voltage(capacity=100)`.
