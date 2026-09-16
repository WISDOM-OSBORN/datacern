"""Provider ordering and failover tests with stubbed LLM clients."""

import pytest
from langchain_core.messages import HumanMessage

import datacern.config.providers as providers_mod
from datacern.config.providers import _extract_text, call_llm, provider_order


class _Resp:
    def __init__(self, content):
        self.content = content


def test_provider_order_respects_preference(monkeypatch):
    monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER_PREFERENCE", "openai")
    assert provider_order() == ["openai", "gemini", "groq", "openrouter"]
    monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER_PREFERENCE", "gemini")
    assert provider_order() == ["gemini", "openai", "groq", "openrouter"]
    monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER_PREFERENCE", "groq")
    assert provider_order() == ["groq", "gemini", "openai", "openrouter"]
    monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER_PREFERENCE", "auto")
    assert provider_order() == ["gemini", "openai", "groq", "openrouter"]


def test_extract_text_handles_blocks():
    assert _extract_text("  hello  ") == "hello"
    assert _extract_text([{"type": "text", "text": "hi"}]) == "hi"
    assert _extract_text(["a", "b"]) == "a\nb"


def test_call_llm_fails_over(monkeypatch):
    calls = []
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setattr(providers_mod.config, key, "test-key")

    class FailLLM:
        def invoke(self, messages):
            calls.append("fail")
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

    class GoodLLM:
        def invoke(self, messages):
            calls.append("good")
            return _Resp("OK")

    monkeypatch.setattr(
        providers_mod, "get_llm", lambda provider: FailLLM() if provider == "gemini" else GoodLLM()
    )
    monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER_PREFERENCE", "gemini")
    assert call_llm([HumanMessage(content="hi")]) == "OK"
    assert calls == ["fail", "good"]


def test_call_llm_fails_over_chain(monkeypatch):
    calls = []
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setattr(providers_mod.config, key, "test-key")

    class FailLLM:
        def invoke(self, messages):
            calls.append("fail")
            raise RuntimeError("429 quota exceeded")

    class GoodLLM:
        def invoke(self, messages):
            calls.append("good")
            return _Resp("OK")

    def _get(provider):
        return GoodLLM() if provider == "openrouter" else FailLLM()

    monkeypatch.setattr(providers_mod, "get_llm", _get)
    monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER_PREFERENCE", "gemini")
    assert call_llm([HumanMessage(content="hi")]) == "OK"
    assert calls == ["fail", "fail", "fail", "good"]


def test_call_llm_raises_when_all_fail(monkeypatch):
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setattr(providers_mod.config, key, "test-key")

    class FailLLM:
        def invoke(self, messages):
            raise RuntimeError("429 quota exceeded")

    monkeypatch.setattr(providers_mod, "get_llm", lambda provider: FailLLM())
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        call_llm([HumanMessage(content="hi")])
