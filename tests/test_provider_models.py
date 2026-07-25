"""Provider contract tests that do not make network requests."""

from bloggen.providers.models import ChatMessage, ChatRequest


def test_chat_request_is_provider_neutral() -> None:
    request = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])

    assert request.messages[0].role == "user"
    assert request.model_dump()["messages"][0]["content"] == "Hello"
