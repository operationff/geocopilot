"""Unit tests for AI adapter interface, ChatGPT adapter, and Perplexity adapter."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.ai_adapters.base import AIAdapterBase, AdapterResult
from app.services.ai_adapters.chatgpt import ChatGPTAdapter, _extract_brand_mentions
from app.services.ai_adapters.perplexity import PerplexityAdapter, _extract_brand_mentions as _perp_extract


# ---------------------------------------------------------------------------
# _extract_brand_mentions helpers
# ---------------------------------------------------------------------------

def test_extract_brand_mentions_found():
    text = "There are many options. Acme Corp is a great choice. It has good reviews."
    mentioned, position, context = _extract_brand_mentions(text, "Acme Corp")
    assert mentioned is True
    assert position == 2
    assert len(context) == 1
    assert "Acme Corp" in context[0]


def test_extract_brand_mentions_case_insensitive():
    text = "First sentence. acme corp appears here. End."
    mentioned, position, context = _extract_brand_mentions(text, "Acme Corp")
    assert mentioned is True
    assert position == 2


def test_extract_brand_mentions_multiple_occurrences():
    text = "Acme Corp leads the market. Others exist. Acme Corp has great support."
    mentioned, position, context = _extract_brand_mentions(text, "Acme Corp")
    assert mentioned is True
    assert position == 1
    assert len(context) == 2


def test_extract_brand_mentions_not_found():
    text = "There are many options available. None of them are relevant."
    mentioned, position, context = _extract_brand_mentions(text, "Acme Corp")
    assert mentioned is False
    assert position is None
    assert context == []


def test_extract_brand_mentions_empty_text():
    mentioned, position, context = _extract_brand_mentions("", "Acme Corp")
    assert mentioned is False
    assert position is None
    assert context == []


def test_extract_brand_mentions_empty_brand():
    mentioned, position, context = _extract_brand_mentions("Some text here.", "")
    assert mentioned is False


# ---------------------------------------------------------------------------
# AIAdapterBase is abstract
# ---------------------------------------------------------------------------

def test_base_adapter_is_abstract():
    with pytest.raises(TypeError):
        AIAdapterBase()  # type: ignore[abstract]


def test_base_adapter_concrete_subclass():
    class MyAdapter(AIAdapterBase):
        def query(self, prompt_text: str, brand_name: str) -> AdapterResult:
            return AdapterResult(
                raw_response="test",
                brand_mentioned=False,
                mention_position=None,
            )

    adapter = MyAdapter()
    result = adapter.query("prompt", "brand")
    assert isinstance(result, AdapterResult)


# ---------------------------------------------------------------------------
# ChatGPTAdapter with mocked OpenAI client
# ---------------------------------------------------------------------------

def _make_openai_response(content: str):
    """Build a minimal mock matching openai.ChatCompletion response shape."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@patch("app.services.ai_adapters.chatgpt.OpenAI")
def test_chatgpt_adapter_brand_mentioned(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response(
        "There are several solutions available. Acme Corp is one of the best options. "
        "It has strong market presence."
    )

    adapter = ChatGPTAdapter(api_key="test-key")
    result = adapter.query("What are the best solutions?", "Acme Corp")

    assert result.brand_mentioned is True
    assert result.mention_position == 2
    assert len(result.mention_context) == 1
    assert "Acme Corp" in result.mention_context[0]
    assert "Acme Corp is one of the best" in result.raw_response


@patch("app.services.ai_adapters.chatgpt.OpenAI")
def test_chatgpt_adapter_brand_not_mentioned(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response(
        "There are many options. You should consider multiple vendors. Research carefully."
    )

    adapter = ChatGPTAdapter(api_key="test-key")
    result = adapter.query("What are the best solutions?", "Acme Corp")

    assert result.brand_mentioned is False
    assert result.mention_position is None
    assert result.mention_context == []


@patch("app.services.ai_adapters.chatgpt.OpenAI")
def test_chatgpt_adapter_uses_correct_model(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response("response")

    adapter = ChatGPTAdapter(api_key="test-key", model="gpt-4o")
    adapter.query("prompt", "brand")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "gpt-4o"


@patch("app.services.ai_adapters.chatgpt.OpenAI")
def test_chatgpt_adapter_passes_prompt_as_user_message(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response("ok")

    adapter = ChatGPTAdapter(api_key="test-key")
    adapter.query("Best CRM tools?", "Acme Corp")

    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Best CRM tools?"


@patch("app.services.ai_adapters.chatgpt.OpenAI")
def test_chatgpt_adapter_empty_response(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response(None)

    adapter = ChatGPTAdapter(api_key="test-key")
    result = adapter.query("prompt", "Brand")

    assert result.raw_response == ""
    assert result.brand_mentioned is False


@patch("app.services.ai_adapters.chatgpt.OpenAI")
def test_chatgpt_adapter_result_is_adapter_result_instance(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response("Brand X is great.")

    adapter = ChatGPTAdapter(api_key="test-key")
    result = adapter.query("prompt", "Brand X")

    assert isinstance(result, AdapterResult)


# ---------------------------------------------------------------------------
# PerplexityAdapter with mocked OpenAI client
# ---------------------------------------------------------------------------

@patch("app.services.ai_adapters.perplexity.OpenAI")
def test_perplexity_adapter_brand_mentioned(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response(
        "There are several solutions. Acme Corp is widely recommended. It has great reviews."
    )

    adapter = PerplexityAdapter(api_key="test-key")
    result = adapter.query("What are the best solutions?", "Acme Corp")

    assert result.brand_mentioned is True
    assert result.mention_position == 2
    assert len(result.mention_context) == 1
    assert "Acme Corp" in result.mention_context[0]
    assert isinstance(result, AdapterResult)


@patch("app.services.ai_adapters.perplexity.OpenAI")
def test_perplexity_adapter_brand_not_mentioned(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response(
        "There are many options. You should research carefully. Consider multiple vendors."
    )

    adapter = PerplexityAdapter(api_key="test-key")
    result = adapter.query("What are the best solutions?", "Acme Corp")

    assert result.brand_mentioned is False
    assert result.mention_position is None
    assert result.mention_context == []


@patch("app.services.ai_adapters.perplexity.OpenAI")
def test_perplexity_adapter_uses_sonar_model_by_default(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response("ok")

    adapter = PerplexityAdapter(api_key="test-key")
    adapter.query("prompt", "brand")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "sonar"


@patch("app.services.ai_adapters.perplexity.OpenAI")
def test_perplexity_adapter_uses_correct_base_url(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response("ok")

    PerplexityAdapter(api_key="test-key")

    _, init_kwargs = mock_openai_cls.call_args
    assert init_kwargs.get("base_url") == "https://api.perplexity.ai"


@patch("app.services.ai_adapters.perplexity.OpenAI")
def test_perplexity_adapter_empty_response(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response(None)

    adapter = PerplexityAdapter(api_key="test-key")
    result = adapter.query("prompt", "Brand")

    assert result.raw_response == ""
    assert result.brand_mentioned is False


@patch("app.services.ai_adapters.perplexity.OpenAI")
def test_perplexity_adapter_passes_prompt_as_user_message(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_openai_response("ok")

    adapter = PerplexityAdapter(api_key="test-key")
    adapter.query("Best project management tools?", "Acme Corp")

    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Best project management tools?"
