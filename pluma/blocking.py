"""One Rust filtering engine shared across profiles; bounded downloads, no scriptlets."""
import hashlib
import threading
import time
from pathlib import Path

import adblock
from .core import BLOCKED_HOSTS, host_matches
from .storage import atomic_json

SOURCES = {
    'easylist': 'https://easylist.to/easylist/easylist.txt',
    'easyprivacy': 'https://easylist.to/easylist/easyprivacy.txt',
}
MAX_LIST_BYTES = 12_000_000


class FilterEngine:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.engine = None
        self.rebuild()

    def rebuild(self):
        filters = adblock.FilterSet()
        filters.add_filters(['||' + host + '^' for host in BLOCKED_HOSTS])
        for name in SOURCES:
            path = self.directory / (name + '.txt')
            if not path.exists():
                path = Path(__file__).parent / 'data/filters' / (name + '.txt')
            if path.exists() and path.stat().st_size <= MAX_LIST_BYTES:
                filters.add_filter_list(path.read_text(encoding='utf-8'))
        engine = adblock.Engine(filters)
        with self.lock:
            self.engine = engine

    def blocked(self, url, source, kind='other', allowed=()):
        from urllib.parse import urlsplit
        if host_matches(urlsplit(source).hostname or '', allowed):
            return False
        try:
            with self.lock:
                return self.engine.check_network_urls(url, source or url, kind).matched
        except (ValueError, RuntimeError):
            return False

    def cosmetic(self, url, classes=(), ids=(), allowed=()):
        from urllib.parse import urlsplit
        if host_matches(urlsplit(url).hostname or '', allowed):
            return []
        with self.lock:
            resources = self.engine.url_cosmetic_resources(url)
            selectors = set(resources.hide_selectors)
            if not resources.generichide:
                selectors.update(self.engine.hidden_class_id_selectors(list(classes)[:3000], list(ids)[:3000],
                                                                       resources.exceptions))
        # Only CSS selectors; never execute injected_script or remote scriptlets.
        return sorted(selectors)[:5000]

    def update(self, cancelled=lambda: False, client_factory=None):
        import httpx
        client_factory = client_factory or httpx.Client
        pending, metadata = {}, {}
        started = time.monotonic()
        with client_factory(timeout=15, follow_redirects=False, trust_env=True) as client:
            for name, url in SOURCES.items():
                chunks, size = [], 0
                with client.stream('GET', url) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        if cancelled() or time.monotonic() - started > 90:
                            raise ValueError('Atualização cancelada ou prazo excedido.')
                        size += len(chunk)
                        if size > MAX_LIST_BYTES:
                            raise ValueError('Lista excedeu o limite de tamanho.')
                        chunks.append(chunk)
                data = b''.join(chunks)
                text = data.decode('utf-8')
                if '[Adblock' not in text[:500] or len(text.splitlines()) < 10:
                    raise ValueError('Formato de lista inválido; listas anteriores preservadas.')
                pending[name] = text
                metadata[name] = {'source': url, 'bytes': size, 'sha256': hashlib.sha256(data).hexdigest()}
        # Validate both lists before replacing. Cache is data, never serialized executable state.
        fs = adblock.FilterSet()
        for text in pending.values():
            fs.add_filter_list(text)
        adblock.Engine(fs)
        self.directory.mkdir(parents=True, exist_ok=True)
        for name, text in pending.items():
            path = self.directory / (name + '.txt')
            tmp = path.with_suffix('.tmp')
            tmp.write_text(text, encoding='utf-8')
            tmp.replace(path)
        atomic_json(self.directory / 'metadata.json', {'updated': time.time(), 'lists': metadata})
        self.rebuild()
        return 'EasyList e EasyPrivacy atualizadas. Recarregue as páginas abertas.'
