"""Tests for LLM client initialization and header setup."""

import os
import pytest
from src.llm.client import LLMClient


def test_anthropic_client_defaults():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    client = LLMClient(provider="anthropic")
    assert "claude" in client.model
    assert "anthropic-version" in client._headers


def test_openrouter_client_defaults():
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    client = LLMClient(provider="openrouter")
    assert "gemma" in client.model
    assert "Authorization" in client._headers


def test_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMClient(provider="nonexistent")


def test_custom_model():
    client = LLMClient(provider="anthropic", model="claude-opus-4-7")
    assert client.model == "claude-opus-4-7"
