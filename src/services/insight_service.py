"""Deterministic, data-supported management insights."""

from __future__ import annotations

from src.models.planning import ManagementInsight, VarianceRow


ACTION_BY_DRIVER = {
    "Price": "Check promotional depth, discounting and realized ticket price.",
    "Volume": "Review traffic, conversion and same-store efficiency by market.",
    "Mix": "Shift the portfolio toward higher-margin brands and regions.",
    "Opex": "Review selling and distribution expenses against the operating plan.",
}


def make_insights(rows: list[VarianceRow]) -> list[ManagementInsight]:
    adverse = [row for row in rows if row.revenue_variance is not None and row.revenue_variance < 0]
    adverse.sort(key=lambda row: abs(row.revenue_variance or 0), reverse=True)
    insights = []
    for row in adverse[:2]:
        driver = row.primary_driver or "Volume"
        driver_amount = {"Price": row.price_amount, "Volume": row.volume_amount, "Mix": row.mix_amount}.get(driver)
        if driver == "Opex" and row.operating_expense_actual is not None and row.operating_expense_budget is not None:
            driver_amount = row.operating_expense_actual - row.operating_expense_budget
        gap_text = "not available" if row.forecast_gap is None else f"RMB {row.forecast_gap:,.1f}m"
        insights.append(ManagementInsight(
            title=f"Watch: {row.business_unit} is below YTD plan",
            business_unit=row.business_unit,
            severity="watch",
            message=f"YTD revenue is RMB {abs(row.revenue_variance or 0):,.1f}m below budget ({abs(row.revenue_variance_pct or 0):.1%}). The largest identified driver is {driver}; FY forecast gap is {gap_text}.",
            driver=driver,
            driver_amount=driver_amount,
            forecast_gap=row.forecast_gap,
            action=ACTION_BY_DRIVER[driver],
        ))
    return insights
