import httpx
import pytest
from pluma.blocking import FilterEngine, SOURCES
from pluma.storage import read_json


def test_filter_rules_exceptions_types_and_cosmetics(tmp_path):
    tmp_path.joinpath('easylist.txt').write_text(
        '[Adblock Plus 2.0]\n||ads.example.org^\n@@||ads.example.org/allowed^\n'
        '/track.js$script\nexample.org##.sponsored\n##.generic-ad\n')
    engine = FilterEngine(tmp_path)
    assert engine.blocked('https://ads.example.org/banner', 'https://example.org', 'image')
    assert not engine.blocked('https://ads.example.org/allowed/x', 'https://example.org', 'image')
    assert engine.blocked('https://cdn.org/track.js', 'https://example.org', 'script')
    assert not engine.blocked('https://cdn.org/track.js', 'https://example.org', 'image')
    assert not engine.blocked('https://ads.example.org/banner', 'https://sub.example.org', 'image', {'example.org'})
    assert '.sponsored' in engine.cosmetic('https://example.org')
    assert '.generic-ad' in engine.cosmetic('https://example.org', classes=['generic-ad'])
    assert not engine.cosmetic('https://example.org', allowed={'example.org'})


def test_verified_list_update_preserves_cache_on_failure(tmp_path):
    engine = FilterEngine(tmp_path)
    text = '[Adblock Plus 2.0]\n' + '\n'.join('||ad' + str(i) + '.org^' for i in range(20))
    def client(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=text)), **kwargs)
    engine.update(client_factory=client)
    assert engine.blocked('https://ad1.org/a', 'https://example.org', 'image')
    assert len(read_json(tmp_path / 'metadata.json', {})['lists']) == 2
    old = (tmp_path / 'easylist.txt').read_bytes()
    def broken(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text='<html>wrong</html>')), **kwargs)
    with pytest.raises(ValueError):
        engine.update(client_factory=broken)
    assert (tmp_path / 'easylist.txt').read_bytes() == old


def test_cancellation(tmp_path):
    def client(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text='data')), **kwargs)
    with pytest.raises(ValueError):
        FilterEngine(tmp_path).update(cancelled=lambda: True, client_factory=client)
    assert not (tmp_path / 'easylist.txt').exists()
