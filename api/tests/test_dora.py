import datetime as dt

from app.dora import compute_dora_from_prs


def test_compute_dora_includes_cfr_and_mttr():
    day = dt.date(2024, 1, 2)
    prs = [
        {
            "title": "Feature A",
            "created_at": "2024-01-01T10:00:00Z",
            "merged_at": "2024-01-02T10:00:00Z",
            "labels": [],
        },
        {
            "title": "Revert bad change",
            "created_at": "2024-01-01T12:00:00Z",
            "merged_at": "2024-01-02T12:00:00Z",
            "labels": [
                {"name": "bug"},
            ],
        },
    ]

    metrics = compute_dora_from_prs(prs)
    assert day in metrics
    day_metrics = metrics[day]
    assert day_metrics["deployment_frequency"] == 2
    # One of two PRs counted as failure -> CFR 0.5
    assert abs(day_metrics["change_failure_rate"] - 0.5) < 1e-6
    # MTTR should use failure lead time (approx 24 hours = 1440 minutes)
    assert 1000 < day_metrics["mttr_minutes"] < 2000


def test_compute_dora_handles_empty():
    metrics = compute_dora_from_prs([])
    assert metrics == {}
