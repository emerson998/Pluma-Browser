"""On-demand release checks. Never executes downloaded binaries."""
import platform
from urllib.parse import urlsplit
import httpx
from packaging.version import Version, InvalidVersion
from . import __version__

REPOSITORY = 'emerson998/Pluma-Browser'
RELEASES_URL = 'https://github.com/' + REPOSITORY + '/releases'
API_URL = 'https://api.github.com/repos/' + REPOSITORY + '/releases/latest'


def check_release(client_factory=httpx.Client):
    with client_factory(timeout=10, follow_redirects=False) as client:
        with client.stream('GET', API_URL, headers={'Accept': 'application/vnd.github+json'}) as response:
            if response.status_code == 404:
                return {'new': False, 'message': 'Ainda não há uma release publicada.'}
            response.raise_for_status()
            data = b''
            for part in response.iter_bytes():
                data += part
                if len(data) > 1_000_000:
                    raise ValueError('Metadados excederam o limite.')
    import json
    release = json.loads(data)
    try:
        new = Version(release['tag_name'].lstrip('v')) > Version(__version__)
    except (InvalidVersion, KeyError):
        raise ValueError('Versão da release inválida.') from None
    url = release.get('html_url', '')
    if urlsplit(url).netloc != 'github.com' or not url.startswith(RELEASES_URL + '/tag/'):
        raise ValueError('Origem da release inválida.')
    return {'new': new, 'message': 'Nova versão: ' + release['tag_name'] if new else 'Você está na versão mais recente.',
            'url': url}
