import json
import httpx
import pytest
from pluma.ai import ask


def factory(handler):
    def create(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(handler), **kwargs)
    return create


def test_openai_context_is_bounded():
    def handle(request):
        assert request.url == 'https://api.example.org/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer secret'
        body = json.loads(request.content)
        assert len(body['messages'][1]['content']) < 24200
        assert body['max_tokens'] == 2048
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Olá'}}]})
    assert ask('custom', 'https://api.example.org/v1', 'model', 'secret', 'pergunta',
               'x' * 50000, client_factory=factory(handle)) == 'Olá'


def test_anthropic():
    def handle(request):
        assert request.headers['x-api-key'] == 'secret'
        assert 'authorization' not in request.headers
        assert request.url.path == '/v1/messages'
        return httpx.Response(200, json={'content': [{'type': 'text', 'text': 'Resposta'}]})
    assert ask('Anthropic', 'https://api.example.org/v1', 'model', 'secret',
               'oi', client_factory=factory(handle)) == 'Resposta'


def test_redirect_never_forwards_key():
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(302, headers={'Location': 'https://other.org'})
    with pytest.raises(ValueError, match='HTTP 302'):
        ask('custom', 'https://api.example.org/v1', 'model', 'secret', 'oi', client_factory=factory(handle))
    assert len(requests) == 1


def test_error_does_not_echo_response():
    def handle(request):
        return httpx.Response(401, text='secret secret secret')
    with pytest.raises(ValueError) as error:
        ask('custom', 'https://api.example.org/v1', 'model', 'secret', 'oi', client_factory=factory(handle))
    assert 'secret' not in str(error.value)


def test_response_limit():
    def handle(request):
        return httpx.Response(200, content=b'x' * 2_000_001)
    with pytest.raises(ValueError, match='2 MB'):
        ask('custom', 'https://api.example.org/v1', 'model', '', 'oi', client_factory=factory(handle))


def test_streaming_with_split_unicode_and_bounded_history():
    text = 'data: {"choices":[{"delta":{"content":"Olá "}}]}\n\ndata: {"choices":[{"delta":{"content":"mundo"}}]}\n\ndata: [DONE]\n\n'
    def handle(request):
        body = json.loads(request.content)
        assert body['stream']
        assert body['messages'][-2]['content'] == 'anterior'
        return httpx.Response(200, content=text.encode())
    tokens = []
    answer = ask('custom', 'https://api.example.org/v1', 'model', '', 'oi',
                 history=[{'role': 'user', 'content': 'anterior'}],
                 on_chunk=tokens.append, client_factory=factory(handle))
    assert answer == 'Olá mundo'
    assert ''.join(tokens) == answer


def test_cancel_and_deadline():
    def handle(request):
        return httpx.Response(200, json={'choices': [{'message': {'content': 'x'}}]})
    with pytest.raises(ValueError, match='cancelada'):
        ask('custom', 'https://api.example.org/v1', 'model', '', 'oi',
            cancelled=lambda: True, client_factory=factory(handle))
    with pytest.raises(ValueError, match='Prazo'):
        ask('custom', 'https://api.example.org/v1', 'model', '', 'oi',
            deadline=0, client_factory=factory(handle))
