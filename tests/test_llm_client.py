"""Tests for LLM client initialization."""

import os
import pytest
from src.llm.client import LLMClient


def test_client_defaults():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    client = LLMClient()
    assert client.model == "claude-opus-4-7"


def test_custom_model():
    client = LLMClient(model="claude-haiku-4-5")
    assert client.model == "claude-haiku-4-5"


def test_custom_timeout():
    client = LLMClient(timeout=60.0)
    assert client.timeout == 60.0
