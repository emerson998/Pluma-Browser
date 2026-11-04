"""Pure policies, independent of Qt and network access."""
import ipaddress
from urllib.parse import urlsplit, quote_plus

# Original starter list. Not a substitute for full cosmetic filtering.
BLOCKED_HOSTS = frozenset("""doubleclick.net googlesyndication.com googleadservices.com
adservice.google.com adnxs.com adsrvr.org taboola.com outbrain.com criteo.com
criteo.net scorecardresearch.com quantserve.com amazon-adsystem.com
facebook.net hotjar.com hotjar.io mouseflow.com
clarity.ms ads.linkedin.com analytics.tiktok.com snap.licdn.com""".split())


def host_matches(host: str, domains) -> bool:
    parts = host.lower().rstrip('.').split('.')
    return any('.'.join(parts[i:]) in domains for i in range(len(parts)))


def should_block(url: str, first_party: str, allowed=(), enabled=True) -> bool:
    if not enabled or host_matches(urlsplit(first_party).hostname or '', allowed):
        return False
    return host_matches(urlsplit(url).hostname or '', BLOCKED_HOSTS)


def navigation_url(text: str) -> str:
    text = text.strip()
    if not text:
        return 'about:blank'
    if text == 'about:blank':
        return text
    if '://' in text or text.lower().startswith(('javascript:', 'data:', 'file:', 'mailto:')):
        parsed = urlsplit(text)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Use um endereço HTTP ou HTTPS sem credenciais.')
        return text
    if ' ' not in text and ('.' in text or text.startswith(('localhost', '[::1]'))):
        return navigation_url('https://' + text)
    return 'https://duckduckgo.com/?q=' + quote_plus(text)


def validate_endpoint(value: str) -> str:
    value = value.strip().rstrip('/')
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Endpoint inválido: não inclua credenciais, query ou fragmento.')
    loopback = parsed.hostname == 'localhost'
    try:
        loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback):
        raise ValueError('A API exige HTTPS; HTTP só é permitido no localhost.')
    return value


def lifecycle_action(idle_seconds: float, recommended: str, audible: bool, protected: bool, freeze_after=60, discard_after=300) -> str:
    if audible or protected:
        return 'active'
    if idle_seconds >= discard_after and recommended == 'discarded':
        return 'discarded'
    if idle_seconds >= freeze_after and recommended in ('frozen', 'discarded'):
        return 'frozen'
    return 'active'
