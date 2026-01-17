"""Business outcomes tracking and DORA correlation analysis.

This module provides functionality to:
1. Track business metrics (revenue, customer satisfaction, incidents, etc.)
2. Correlate DORA metrics with business outcomes
3. Calculate ROI of engineering improvements
4. Generate business impact insights
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any
import math


def calculate_correlation(x_values: list[float], y_values: list[float]) -> float | None:
    """Calculate Pearson correlation coefficient between two series.
    
    Returns a value between -1 and 1, or None if calculation isn't possible.
    """
    if len(x_values) != len(y_values) or len(x_values) < 3:
        return None
    
    n = len(x_values)
    
    # Filter out None values
    pairs = [(x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    
    x_vals = [p[0] for p in pairs]
    y_vals = [p[1] for p in pairs]
    n = len(x_vals)
    
    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n
    
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
    
    sum_sq_x = sum((x - mean_x) ** 2 for x in x_vals)
    sum_sq_y = sum((y - mean_y) ** 2 for y in y_vals)
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    
    if denominator == 0:
        return None
    
    return numerator / denominator


def interpret_correlation(corr: float | None, metric1: str, metric2: str) -> str:
    """Generate human-readable interpretation of correlation."""
    if corr is None:
        return f"Insufficient data to correlate {metric1} with {metric2}"
    
    abs_corr = abs(corr)
    direction = "positively" if corr > 0 else "negatively"
    
    if abs_corr >= 0.7:
        strength = "strongly"
    elif abs_corr >= 0.4:
        strength = "moderately"
    elif abs_corr >= 0.2:
        strength = "weakly"
    else:
        return f"No significant correlation between {metric1} and {metric2}"
    
    return f"{metric1} is {strength} {direction} correlated with {metric2} (r={corr:.2f})"


def calculate_business_impact(
    dora_before: dict[str, float],
    dora_after: dict[str, float],
    business_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Calculate the estimated business impact of DORA metric improvements.
    
    Uses industry research to estimate business value:
    - Elite performers deploy 973x more frequently than low performers
    - Elite performers have 6,570x faster lead time
    - Elite performers have 3x lower change failure rate
    - Elite performers recover 6,570x faster from failures
    
    Research source: DORA State of DevOps Report
    """
    context = business_context or {}
    annual_revenue = context.get("annual_revenue", 1_000_000)  # Default $1M
    avg_incident_cost = context.get("avg_incident_cost", 5_000)  # Default $5K per incident
    engineer_hourly_rate = context.get("engineer_hourly_rate", 75)  # Default $75/hr
    team_size = context.get("team_size", 10)
    
    impacts = []
    total_annual_savings = 0
    
    # Deployment Frequency Impact
    df_before = dora_before.get("deployment_frequency", 0)
    df_after = dora_after.get("deployment_frequency", 0)
    if df_before > 0 and df_after > df_before:
        df_improvement = ((df_after - df_before) / df_before) * 100
        # More deployments = faster time-to-market, estimated 0.5% revenue boost per 10% improvement
        revenue_impact = annual_revenue * (df_improvement / 10) * 0.005
        total_annual_savings += revenue_impact
        impacts.append({
            "metric": "Deployment Frequency",
            "before": df_before,
            "after": df_after,
            "improvement_pct": df_improvement,
            "estimated_value": revenue_impact,
            "insight": f"Increased deployment frequency by {df_improvement:.1f}%, enabling faster feature delivery"
        })
    
    # Lead Time Impact
    lt_before = dora_before.get("avg_lead_time_minutes", 0)
    lt_after = dora_after.get("avg_lead_time_minutes", 0)
    if lt_before > 0 and lt_after < lt_before:
        lt_improvement = ((lt_before - lt_after) / lt_before) * 100
        # Time saved per deployment * deployments per year
        time_saved_hours = (lt_before - lt_after) / 60 * df_after * 52  # Weekly deployments annualized
        labor_savings = time_saved_hours * engineer_hourly_rate
        total_annual_savings += labor_savings
        impacts.append({
            "metric": "Lead Time",
            "before": lt_before,
            "after": lt_after,
            "improvement_pct": lt_improvement,
            "estimated_value": labor_savings,
            "insight": f"Reduced lead time by {lt_improvement:.1f}%, saving {time_saved_hours:.0f} engineering hours annually"
        })
    
    # Change Failure Rate Impact
    cfr_before = dora_before.get("change_failure_rate", 0)
    cfr_after = dora_after.get("change_failure_rate", 0)
    if cfr_before > 0 and cfr_after < cfr_before:
        cfr_improvement = ((cfr_before - cfr_after) / cfr_before) * 100
        # Fewer failures = fewer incidents
        incidents_prevented = (cfr_before - cfr_after) * df_after * 52  # Annual deployments
        incident_savings = incidents_prevented * avg_incident_cost
        total_annual_savings += incident_savings
        impacts.append({
            "metric": "Change Failure Rate",
            "before": cfr_before,
            "after": cfr_after,
            "improvement_pct": cfr_improvement,
            "estimated_value": incident_savings,
            "insight": f"Reduced failure rate by {cfr_improvement:.1f}%, preventing ~{incidents_prevented:.0f} incidents annually"
        })
    
    # MTTR Impact
    mttr_before = dora_before.get("mttr_minutes", 0)
    mttr_after = dora_after.get("mttr_minutes", 0)
    if mttr_before > 0 and mttr_after < mttr_before:
        mttr_improvement = ((mttr_before - mttr_after) / mttr_before) * 100
        # Faster recovery = less downtime cost
        downtime_saved_hours = (mttr_before - mttr_after) / 60 * cfr_after * df_after * 52
        downtime_cost_per_hour = annual_revenue / (365 * 24)  # Revenue per hour
        downtime_savings = downtime_saved_hours * downtime_cost_per_hour
        total_annual_savings += downtime_savings
        impacts.append({
            "metric": "Mean Time to Recovery",
            "before": mttr_before,
            "after": mttr_after,
            "improvement_pct": mttr_improvement,
            "estimated_value": downtime_savings,
            "insight": f"Reduced recovery time by {mttr_improvement:.1f}%, minimizing downtime impact"
        })
    
    return {
        "impacts": impacts,
        "total_annual_savings": total_annual_savings,
        "roi_summary": f"Estimated annual value of improvements: ${total_annual_savings:,.0f}",
        "methodology": "Based on DORA research and industry benchmarks"
    }


def get_dora_performance_level(metrics: dict[str, float]) -> dict[str, str]:
    """Classify DORA metrics into performance levels (Elite, High, Medium, Low)."""
    levels = {}
    
    # Deployment Frequency (per day)
    df = metrics.get("deployment_frequency", 0)
    if df >= 1:  # Multiple per day or daily
        levels["deployment_frequency"] = "Elite"
    elif df >= 0.14:  # Weekly
        levels["deployment_frequency"] = "High"
    elif df >= 0.033:  # Monthly
        levels["deployment_frequency"] = "Medium"
    else:
        levels["deployment_frequency"] = "Low"
    
    # Lead Time (minutes)
    lt = metrics.get("avg_lead_time_minutes", float('inf'))
    if lt <= 60:  # Less than 1 hour
        levels["lead_time"] = "Elite"
    elif lt <= 1440:  # Less than 1 day
        levels["lead_time"] = "High"
    elif lt <= 10080:  # Less than 1 week
        levels["lead_time"] = "Medium"
    else:
        levels["lead_time"] = "Low"
    
    # Change Failure Rate
    cfr = metrics.get("change_failure_rate", 1)
    if cfr <= 0.15:
        levels["change_failure_rate"] = "Elite"
    elif cfr <= 0.30:
        levels["change_failure_rate"] = "High"
    elif cfr <= 0.45:
        levels["change_failure_rate"] = "Medium"
    else:
        levels["change_failure_rate"] = "Low"
    
    # MTTR (minutes)
    mttr = metrics.get("mttr_minutes", float('inf'))
    if mttr <= 60:  # Less than 1 hour
        levels["mttr"] = "Elite"
    elif mttr <= 1440:  # Less than 1 day
        levels["mttr"] = "High"
    elif mttr <= 10080:  # Less than 1 week
        levels["mttr"] = "Medium"
    else:
        levels["mttr"] = "Low"
    
    # Overall level (most common or lowest)
    level_order = ["Low", "Medium", "High", "Elite"]
    level_values = [level_order.index(l) for l in levels.values()]
    avg_level = sum(level_values) / len(level_values)
    levels["overall"] = level_order[round(avg_level)]
    
    return levels


async def upsert_business_metrics(pool, org_id: str, date: dt.date, metrics: dict[str, Any]) -> None:
    """Insert or update business metrics for a given date."""
    query = """
    INSERT INTO business_metrics (
        org_id, date, revenue, new_customers, customer_churn_rate,
        customer_satisfaction_score, support_tickets, avg_resolution_time_hours,
        incidents, incident_severity_avg, uptime_percentage,
        features_shipped, bug_reports, custom_metrics
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
    ON CONFLICT (org_id, date) DO UPDATE SET
        revenue = COALESCE(EXCLUDED.revenue, business_metrics.revenue),
        new_customers = COALESCE(EXCLUDED.new_customers, business_metrics.new_customers),
        customer_churn_rate = COALESCE(EXCLUDED.customer_churn_rate, business_metrics.customer_churn_rate),
        customer_satisfaction_score = COALESCE(EXCLUDED.customer_satisfaction_score, business_metrics.customer_satisfaction_score),
        support_tickets = COALESCE(EXCLUDED.support_tickets, business_metrics.support_tickets),
        avg_resolution_time_hours = COALESCE(EXCLUDED.avg_resolution_time_hours, business_metrics.avg_resolution_time_hours),
        incidents = COALESCE(EXCLUDED.incidents, business_metrics.incidents),
        incident_severity_avg = COALESCE(EXCLUDED.incident_severity_avg, business_metrics.incident_severity_avg),
        uptime_percentage = COALESCE(EXCLUDED.uptime_percentage, business_metrics.uptime_percentage),
        features_shipped = COALESCE(EXCLUDED.features_shipped, business_metrics.features_shipped),
        bug_reports = COALESCE(EXCLUDED.bug_reports, business_metrics.bug_reports),
        custom_metrics = COALESCE(EXCLUDED.custom_metrics, business_metrics.custom_metrics);
    """
    async with pool.acquire() as conn:
        await conn.execute(
            query,
            org_id,
            date,
            metrics.get("revenue"),
            metrics.get("new_customers"),
            metrics.get("customer_churn_rate"),
            metrics.get("customer_satisfaction_score"),
            metrics.get("support_tickets"),
            metrics.get("avg_resolution_time_hours"),
            metrics.get("incidents", 0),
            metrics.get("incident_severity_avg"),
            metrics.get("uptime_percentage"),
            metrics.get("features_shipped"),
            metrics.get("bug_reports"),
            json.dumps(metrics.get("custom_metrics", {}))
        )


async def get_business_metrics(pool, org_id: str, range_days: int = 30) -> list[dict]:
    """Retrieve business metrics for the specified period."""
    query = """
    SELECT date, revenue, new_customers, customer_churn_rate,
           customer_satisfaction_score, support_tickets, avg_resolution_time_hours,
           incidents, incident_severity_avg, uptime_percentage,
           features_shipped, bug_reports, custom_metrics
    FROM business_metrics
    WHERE org_id = $1 AND date >= (CURRENT_DATE - $2 * INTERVAL '1 day')
    ORDER BY date ASC;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, org_id, range_days)
    return [dict(row) for row in rows]


async def compute_correlations(pool, org_id: str, range_days: int = 90) -> dict[str, Any]:
    """Compute correlations between DORA metrics and business outcomes."""
    # Get DORA metrics (aggregated across all repos)
    dora_query = """
    SELECT date,
           AVG(deployment_frequency) as deployment_frequency,
           AVG(avg_lead_time_minutes) as avg_lead_time_minutes,
           AVG(change_failure_rate) as change_failure_rate,
           AVG(mttr_minutes) as mttr_minutes
    FROM dora_metrics
    WHERE date >= (CURRENT_DATE - $1 * INTERVAL '1 day')
    GROUP BY date
    ORDER BY date ASC;
    """
    
    business_query = """
    SELECT date, revenue, customer_satisfaction_score, incidents,
           customer_churn_rate, uptime_percentage
    FROM business_metrics
    WHERE org_id = $1 AND date >= (CURRENT_DATE - $2 * INTERVAL '1 day')
    ORDER BY date ASC;
    """
    
    async with pool.acquire() as conn:
        dora_rows = await conn.fetch(dora_query, range_days)
        business_rows = await conn.fetch(business_query, org_id, range_days)
    
    # Convert to dicts indexed by date
    dora_by_date = {row["date"]: dict(row) for row in dora_rows}
    business_by_date = {row["date"]: dict(row) for row in business_rows}
    
    # Find common dates
    common_dates = sorted(set(dora_by_date.keys()) & set(business_by_date.keys()))
    
    if len(common_dates) < 7:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 7 days of overlapping data. Found {len(common_dates)} days.",
            "correlations": {},
            "insights": []
        }
    
    # Extract aligned series
    df_values = [dora_by_date[d]["deployment_frequency"] for d in common_dates]
    lt_values = [dora_by_date[d]["avg_lead_time_minutes"] for d in common_dates]
    cfr_values = [dora_by_date[d]["change_failure_rate"] for d in common_dates]
    mttr_values = [dora_by_date[d]["mttr_minutes"] for d in common_dates]
    
    revenue_values = [business_by_date[d]["revenue"] for d in common_dates]
    satisfaction_values = [business_by_date[d]["customer_satisfaction_score"] for d in common_dates]
    incident_values = [business_by_date[d]["incidents"] for d in common_dates]
    churn_values = [business_by_date[d]["customer_churn_rate"] for d in common_dates]
    uptime_values = [business_by_date[d]["uptime_percentage"] for d in common_dates]
    
    # Calculate correlations
    correlations = {
        "df_revenue": calculate_correlation(df_values, revenue_values),
        "df_satisfaction": calculate_correlation(df_values, satisfaction_values),
        "leadtime_revenue": calculate_correlation(lt_values, revenue_values),
        "leadtime_satisfaction": calculate_correlation(lt_values, satisfaction_values),
        "cfr_incidents": calculate_correlation(cfr_values, incident_values),
        "cfr_churn": calculate_correlation(cfr_values, churn_values),
        "mttr_satisfaction": calculate_correlation(mttr_values, satisfaction_values),
        "mttr_uptime": calculate_correlation(mttr_values, uptime_values),
    }
    
    # Generate insights
    insights = []
    
    if correlations["df_revenue"] and correlations["df_revenue"] > 0.3:
        insights.append({
            "type": "positive",
            "insight": interpret_correlation(correlations["df_revenue"], "Deployment Frequency", "Revenue"),
            "recommendation": "Continue investing in deployment automation to drive revenue growth"
        })
    
    if correlations["cfr_incidents"] and correlations["cfr_incidents"] > 0.3:
        insights.append({
            "type": "warning",
            "insight": interpret_correlation(correlations["cfr_incidents"], "Change Failure Rate", "Incidents"),
            "recommendation": "Improve testing and code review processes to reduce production incidents"
        })
    
    if correlations["mttr_satisfaction"] and correlations["mttr_satisfaction"] < -0.3:
        insights.append({
            "type": "positive",
            "insight": "Faster incident recovery correlates with higher customer satisfaction",
            "recommendation": "Invest in observability and incident response automation"
        })
    
    if correlations["leadtime_satisfaction"] and correlations["leadtime_satisfaction"] < -0.3:
        insights.append({
            "type": "positive",
            "insight": "Shorter lead times correlate with better customer satisfaction",
            "recommendation": "Focus on reducing cycle time through smaller batches and automation"
        })
    
    return {
        "status": "success",
        "period": {
            "start": str(common_dates[0]),
            "end": str(common_dates[-1]),
            "days": len(common_dates)
        },
        "correlations": correlations,
        "insights": insights
    }
