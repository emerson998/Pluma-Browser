import pytest
from pluma.video import youtube_id, floating_url, is_youtube, YOUTUBE_NOADS, AD_KEYS

ID = 'dQw4w9WgXcQ'


@pytest.mark.parametrize('url', [
    f'https://www.youtube.com/watch?v={ID}',
    f'https://m.youtube.com/watch?feature=share&v={ID}&t=30',
    f'https://youtu.be/{ID}?si=abc',
    f'https://www.youtube.com/shorts/{ID}',
    f'https://www.youtube-nocookie.com/embed/{ID}',
    f'https://www.youtube.com/live/{ID}',
])
def test_youtube_id_formats(url):
    assert youtube_id(url) == ID


@pytest.mark.parametrize('url', [
    'https://www.youtube.com/', 'https://www.youtube.com/watch?v=short',
    f'https://notyoutube.com/watch?v={ID}', f'https://youtube.com.evil.org/watch?v={ID}',
    'https://vimeo.com/123',
])
def test_not_a_youtube_video(url):
    assert youtube_id(url) is None


def test_floating_url_keeps_position_and_other_sites():
    assert floating_url(f'https://youtu.be/{ID}', 75.9) == f'https://www.youtube.com/watch?v={ID}&t=75s'
    assert floating_url(f'https://www.youtube.com/watch?v={ID}&list=x') == f'https://www.youtube.com/watch?v={ID}'
    assert floating_url('https://vimeo.com/123', 10) == 'https://vimeo.com/123'
    assert is_youtube('https://music.youtube.com/') and not is_youtube('https://example.org')


def test_ad_script_is_scoped_and_prunes_ad_fields():
    assert '%KEYS%' not in YOUTUBE_NOADS
    assert 'youtube(-nocookie)?' in YOUTUBE_NOADS
    for key in AD_KEYS:
        assert key in YOUTUBE_NOADS
