from app.services.llm.client import LLMService


def test_llm_service_resolves_default_model() -> None:
    service = LLMService()
    config = service.resolve_config(None)
    assert config.provider == "openrouter"
    assert config.model is not None
