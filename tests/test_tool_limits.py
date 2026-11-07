import pytest
from pydantic import ValidationError

from mcp_web_engine.mcp_tools import ExtractMarkdownInput, FetchUrlInput, WebSearchInput


@pytest.mark.parametrize('model', [FetchUrlInput, ExtractMarkdownInput])
@pytest.mark.parametrize('value', [-1, 0, 16 * 1024 * 1024 + 1])
def test_payload_limit_must_be_bounded_positive(model, value):
    with pytest.raises(ValidationError):
        model(url='https://example.com', max_bytes=value)


def test_search_limit_cannot_be_null():
    with pytest.raises(ValidationError):
        WebSearchInput(query='example', limit=None)


def test_query_length_bounded():
    with pytest.raises(ValidationError):
        WebSearchInput(query='q' * 4097)
