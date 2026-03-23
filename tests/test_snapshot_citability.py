from app.models.discovery import PageProfile, SiteSignals
from app.utils.heuristics import assess_citability


def test_assess_citability_uses_best_snapshot_page() -> None:
    homepage = {
        "title": "Example Co",
        "meta_description": "Homepage description",
        "canonical": "https://example.com/",
        "h1": "Example homepage",
        "headings": [{"level": "h1", "text": "Example homepage"}],
        "word_count": 180,
    }
    page_profiles = {
        "service": PageProfile(
            page_type="service",
            final_url="https://example.com/services/geo",
            title="GEO service page",
            meta_description="Clear service description",
            canonical="https://example.com/services/geo",
            headings=[
                {"level": "h1", "text": "GEO service"},
                {"level": "h2", "text": "What we do"},
                {"level": "h2", "text": "FAQ"},
                {"level": "h2", "text": "Proof"},
            ],
            word_count=900,
            has_faq=True,
            has_author=True,
            has_publish_date=True,
            has_quantified_data=True,
            answer_first=True,
            information_density_score=82,
            chunk_structure_score=88,
            entity_signals=SiteSignals(company_name_detected=True),
        )
    }

    result = assess_citability(homepage, page_profiles)
    assert result["best_page_citability"]["page_key"] == "service"
    assert result["score"] >= 70
    assert result["citation_probability"] == "HIGH"


def test_assess_citability_keeps_backward_compatible_signals() -> None:
    homepage = {
        "title": "Example",
        "meta_description": "Example description",
        "canonical": "https://example.com/",
        "h1": "Example heading",
        "headings": [{"level": "h1", "text": "Example heading"}],
        "word_count": 260,
    }

    result = assess_citability(homepage)
    assert "score" in result
    assert "signals" in result
    assert "homepage_citability" in result
    assert "best_page_citability" in result
