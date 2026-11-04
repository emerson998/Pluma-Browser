import pytest
from pluma.core import navigation_url, should_block, validate_endpoint, lifecycle_action


@pytest.mark.parametrize('url', ['https://doubleclick.net/x', 'https://a.doubleclick.net/ad', 'https://GOOGLESYNDICATION.COM./a'])
def test_block_subdomains(url):
    assert should_block(url, 'https://example.org')


@pytest.mark.parametrize('url', ['https://notdoubleclick.net', 'https://doubleclick.net.example.org', 'https://example.org/?q=doubleclick.net'])
def test_no_false_domain_matches(url):
    assert not should_block(url, 'https://example.org')


def test_allowlist_and_switch():
    assert not should_block('https://doubleclick.net/ad', 'https://news.example.org', {'example.org'})
    assert should_block('https://doubleclick.net/ad', 'https://evil-example.org', {'example.org'})
    assert not should_block('https://doubleclick.net/ad', '', enabled=False)


@pytest.mark.parametrize('value', ['javascript:alert(1)', 'file:///etc/passwd', 'data:text/html,abc', 'https://u:p@example.org', 'ftp://example.org'])
def test_unsafe_navigation(value):
    with pytest.raises(ValueError):
        navigation_url(value)


def test_navigation():
    assert navigation_url('example.org') == 'https://example.org'
    assert navigation_url('olá mundo').endswith('ol%C3%A1+mundo')
    assert navigation_url('http://localhost:8080') == 'http://localhost:8080'


@pytest.mark.parametrize('url', ['http://remote.org/v1', 'https://u:p@host/v1', 'https://host/v1?key=x', 'file:///tmp/a'])
def test_endpoint_security(url):
    with pytest.raises(ValueError):
        validate_endpoint(url)


@pytest.mark.parametrize('url', ['https://api.example.org/v1', 'http://127.0.0.1:1234/v1', 'http://localhost:11434/v1', 'http://[::1]:1234/v1'])
def test_valid_endpoints(url):
    assert validate_endpoint(url + '/') == url


def test_lifecycle():
    assert lifecycle_action(30, 'discarded', False, False) == 'active'
    assert lifecycle_action(61, 'discarded', False, False) == 'frozen'
    assert lifecycle_action(301, 'discarded', False, False) == 'discarded'
    assert lifecycle_action(301, 'active', False, False) == 'active'
    assert lifecycle_action(301, 'discarded', True, False) == 'active'
    assert lifecycle_action(301, 'discarded', False, True) == 'active'
