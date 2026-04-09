from app.services.audit.scoring import ScoringService


def test_status_mapping() -> None:
    service = ScoringService()
    assert service.status_from_score(10) == "critical"
    assert service.status_from_score(30) == "poor"
    assert service.status_from_score(50) == "fair"
    assert service.status_from_score(70) == "good"
    assert service.status_from_score(90) == "strong"
