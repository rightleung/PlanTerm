"""Deterministic, data-supported management insights."""

from __future__ import annotations

from src.models.planning import ManagementInsight, VarianceRow


ACTION_BY_DRIVER = {
    "Price": "Check promotional depth, discounting and realized ticket price.",
    "Volume": "Review traffic, conversion and same-store efficiency by market.",
    "Mix": "Shift the portfolio toward higher-margin brands and regions.",
    "Gross Margin": "Review markdowns, sourcing and gross-margin realization against plan.",
    "Opex": "Review selling and distribution expenses against the operating plan.",
}


def make_insights(rows: list[VarianceRow]) -> list[ManagementInsight]:
    adverse = [row for row in rows if row.revenue_variance is not None and row.revenue_variance < 0]
    adverse.sort(key=lambda row: abs(row.revenue_variance or 0), reverse=True)
    insights = []
    for row in adverse[:2]:
        revenue_driver = row.primary_driver or "None identified"
        driver = row.profit_driver or "Volume"
        driver_amount = row.profit_driver_amount
        gap_text = "not available" if row.forecast_gap is None else f"RMB {row.forecast_gap:,.1f}m"
        insights.append(ManagementInsight(
            title=f"Watch: {row.business_unit} is below YTD plan",
            business_unit=row.business_unit,
            severity="watch",
            message=f"YTD revenue is RMB {abs(row.revenue_variance or 0):,.1f}m below budget ({abs(row.revenue_variance_pct or 0):.1%}). Revenue driver: {revenue_driver}. Operating Profit driver: {driver} (RMB {abs(driver_amount or 0):,.1f}m effect); FY forecast gap is {gap_text}.",
            driver=driver,
            driver_amount=driver_amount,
            revenue_driver=revenue_driver,
            profit_driver=row.profit_driver,
            profit_driver_amount=row.profit_driver_amount,
            forecast_gap=row.forecast_gap,
            action=ACTION_BY_DRIVER[driver],
        ))
    return insights
