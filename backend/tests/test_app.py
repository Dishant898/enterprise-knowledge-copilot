from enterprise_knowledge_copilot.main import app


def test_app_is_created() -> None:
    assert app.title == "Enterprise Knowledge Copilot API"
