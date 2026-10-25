"""Unit tests for the replaceable LLMProvider interface and mock/real implementations."""

from __future__ import annotations

import json
import httpx
import pytest
from pydantic import BaseModel

from artemis.llm.provider import (
    GeminiLLMProvider,
    LLMError,
    LLMProvider,
    MockLLMProvider,
    get_llm_provider,
)


class SampleSchema(BaseModel):
    name: str
    score: float
    tags: list[str]


class TestMockLLMProvider:
    def test_mock_provider_default_response(self) -> None:
        provider = MockLLMProvider(default_response="Custom static output")
        res = provider.generate("Tell me about distributed consensus.")
        assert res == "Custom static output"
        assert len(provider.call_history) == 1
        assert provider.call_history[0]["prompt"] == "Tell me about distributed consensus."

    def test_mock_provider_canned_responses(self) -> None:
        provider = MockLLMProvider(canned_responses={
            "raft": "Raft is a leader-based consensus algorithm.",
            "paxos": "Paxos achieves consensus through two phases.",
        })
        assert provider.generate("Explain Raft.") == "Raft is a leader-based consensus algorithm."
        assert provider.generate("Explain Paxos.") == "Paxos achieves consensus through two phases."
        # Unmatched falls back to heuristic
        unmatched = provider.generate("Explain compilers.")
        assert isinstance(unmatched, str)

    def test_mock_provider_generate_structured_success(self) -> None:
        valid_json = json.dumps({"name": "Distributed System", "score": 0.95, "tags": ["raft", "paxos"]})
        provider = MockLLMProvider(default_response=valid_json)

        obj = provider.generate_structured("Extract concepts", SampleSchema)
        assert isinstance(obj, SampleSchema)
        assert obj.name == "Distributed System"
        assert obj.score == 0.95
        assert obj.tags == ["raft", "paxos"]

    def test_mock_provider_generate_structured_handles_markdown_code_fences(self) -> None:
        fenced_json = "```json\n{\"name\": \"Fenced System\", \"score\": 0.88, \"tags\": [\"fenced\"]}\n```"
        provider = MockLLMProvider(default_response=fenced_json)

        obj = provider.generate_structured("Extract concepts", SampleSchema)
        assert obj.name == "Fenced System"
        assert obj.score == 0.88

    def test_mock_provider_generate_structured_malformed_json_raises_llm_error(self) -> None:
        broken_json = "{ invalid json here... }}"
        provider = MockLLMProvider(default_response=broken_json)

        with pytest.raises(LLMError, match="Failed to parse LLM response into schema"):
            provider.generate_structured("Extract concepts", SampleSchema)

    def test_mock_provider_simulated_error(self) -> None:
        provider = MockLLMProvider(raise_error=RuntimeError("Simulated LLM service outage"))
        with pytest.raises(RuntimeError, match="Simulated LLM service outage"):
            provider.generate("Prompt")


class TestGeminiLLMProvider:
    def test_gemini_missing_api_key_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        provider = GeminiLLMProvider(api_key=None)
        with pytest.raises(LLMError, match="GEMINI_API_KEY is not set"):
            provider.generate("Hello Gemini")

    def test_gemini_successful_mocked_request(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "key=fake-test-key" in str(request.url)
            body = json.loads(request.content)
            assert "contents" in body
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "Gemini generated research response."}]
                            }
                        }
                    ]
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = GeminiLLMProvider(api_key="fake-test-key", client=client)
        result = provider.generate("Analyze this paper")
        assert result == "Gemini generated research response."


class TestLLMFactory:
    def test_get_mock_provider(self) -> None:
        p = get_llm_provider("mock")
        assert isinstance(p, MockLLMProvider)

    def test_get_gemini_provider(self) -> None:
        p = get_llm_provider("gemini", api_key="test-key")
        assert isinstance(p, GeminiLLMProvider)

    def test_unsupported_provider_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_provider("unsupported_model_abc")
