"""Small atomic stores. No history or session writes in private mode."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

MAX_TABS = 100


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def read_json(path, default):
    try:
        path = Path(path)
        if path.stat().st_size > 2_000_000:
            return default
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def session_entries(entries):
    result = []
    for entry in entries[:MAX_TABS] if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        url = entry.get('url', '')
        if isinstance(url, str) and len(url) <= 8192 and urlsplit(url).scheme in ('https', 'http'):
            result.append({'url': url, 'title': str(entry.get('title', 'Aba'))[:200],
                           'pinned': bool(entry.get('pinned')), 'protected': bool(entry.get('protected'))})
    return result


def bounded_messages(history, prompt, context='', budget=48000):
    messages = []
    if context:
        prompt += '\n<PAGINA_NAO_CONFIAVEL>\n' + context[:24000] + '\n</PAGINA_NAO_CONFIAVEL>'
    remaining = max(0, budget - len(prompt))
    for entry in reversed(history[-12:]):
        if entry.get('role') not in ('user', 'assistant'):
            continue
        content = str(entry.get('content', ''))
        if len(content) > remaining:
            break
        messages.insert(0, {'role': entry['role'], 'content': content})
        remaining -= len(content)
    return messages + [{'role': 'user', 'content': prompt}]


def bookmark_records(value):
    # Migrate 0.1's URL-only favorites.
    records = []
    for item in value if isinstance(value, list) else []:
        item = {'url': item, 'title': item, 'folder': ''} if isinstance(item, str) else item
        if isinstance(item, dict) and urlsplit(str(item.get('url', ''))).scheme in ('http', 'https'):
            records.append({key: str(item.get(key, ''))[:8192] for key in ('title', 'url', 'folder')})
    return records[:2000]
