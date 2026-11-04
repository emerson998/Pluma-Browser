import httpx
import pytest
from pluma.updates import check_release


def client(body, status=200):
    return lambda **kwargs: httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json=body)), **kwargs)


def test_no_release_and_origin_validation():
    assert not check_release(client({}, 404))['new']
    with pytest.raises(ValueError, match='Origem'):
        check_release(client({'tag_name': 'v9.0.0', 'html_url': 'https://evil.org/download'}))
    value = check_release(client({'tag_name': 'v9.0.0',
        'html_url': 'https://github.com/emerson998/Pluma-Browser/releases/tag/v9.0.0'}))
    assert value['new']
