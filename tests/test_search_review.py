"""Offline search-provider regressions; no external requests."""
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from mcp_web_engine import web_engine as engine
from mcp_web_engine.mcp_tools import WebSearchInput


def backend(monkeypatch, payload, *, html=False):
    calls = []
    async def request(url, *args, **kwargs):
        calls.append(url)
        body = payload.encode() if html else json.dumps(payload).encode()
        return SimpleNamespace(status_code=200, encoding='utf-8', headers={}), body, url
    monkeypatch.setattr(engine, '_bounded_request', request)
    monkeypatch.setattr(engine.settings, 'ALLOW_DDG_FALLBACK', False)
    return calls


@pytest.mark.parametrize('base,expected', [
    ('https://search.example/base/?token=x', '/base/search'),
    ('https://search.example/base/search?token=x#ignored', '/base/search'),
])
@pytest.mark.asyncio
async def test_search_base_path_and_parameters(monkeypatch, base, expected):
    calls = backend(monkeypatch, {'results': []})
    monkeypatch.setattr(engine.settings, 'SEARXNG_URL', base)
    await engine.execute_web_search('a & b')
    parts = urlsplit(calls[0])
    assert parts.path == expected
    assert parts.fragment == ''
    assert parse_qs(parts.query) == {'token': ['x'], 'q': ['a & b'], 'format': ['json']}


@pytest.mark.parametrize('payload', [{}, {'error': 'backend failed'}, {'results': None}, {'results': {}}, []])
@pytest.mark.asyncio
async def test_invalid_backend_is_not_success(monkeypatch, payload):
    backend(monkeypatch, payload)
    assert (await engine.execute_web_search('test'))['error'] == 'SEARXNG_UNAVAILABLE'


@pytest.mark.asyncio
async def test_malformed_entries_do_not_hide_valid_results(monkeypatch):
    backend(monkeypatch, {'results': [None, 4, {'url': 'javascript:alert(1)'},
        {'url': 'https://example.com/a', 'title': 'Good', 'content': 'Text'},
        {'url': 'https://example.com/b', 'title': ['bad']}]})
    result = await engine.execute_web_search('test', 1)
    assert result['count'] == 1
    assert result['results'][0]['url'] == 'https://example.com/a'
    assert result['results'][0]['rank'] == 1


@pytest.mark.parametrize('query,limit', [('  ', 1), ('a', 1), ('x'*4097, 1), ('test', 0), ('test', 26), ('test', True), ('test', '2')])
@pytest.mark.asyncio
async def test_direct_search_validation_precedes_network(monkeypatch, query, limit):
    calls = backend(monkeypatch, {'results': []})
    with pytest.raises(HTTPException):
        await engine.execute_web_search(query, limit)
    assert calls == []


@pytest.mark.parametrize('kwargs', [{'query': '  '}, {'query': 'test', 'limit': True}, {'query': 'test', 'limit': '2'}])
def test_mcp_search_validation(kwargs):
    with pytest.raises(ValidationError):
        WebSearchInput(**kwargs)


@pytest.mark.asyncio
async def test_ddg_decodes_wrapper_once_and_rejects_unsafe_links(monkeypatch):
    backend(monkeypatch, '''<a class="result__a" href="javascript:alert(1)">Bad</a>
    <a class="result__a" href="https://[malformed">Malformed</a>
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3a%2f%2fexample.com%2fa%252Fb%3Fx%3Da%2526b">Good</a>
    <a class="result__a" href="https://example.org/?uddg=https%3A%2F%2Fevil.example">Direct</a>''', html=True)
    result = await engine.execute_ddg_fallback('test', 2)
    assert [r['url'] for r in result['results']] == ['https://example.com/a%2Fb?x=a%26b', 'https://example.org/?uddg=https%3A%2F%2Fevil.example']


@pytest.mark.asyncio
async def test_failed_ddg_is_distinguishable_from_empty_success(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise HTTPException(502)
    monkeypatch.setattr(engine, '_bounded_request', unavailable)
    assert (await engine.execute_ddg_fallback('test'))['error'] == 'DDG_UNAVAILABLE'
