from pluma.storage import atomic_json, read_json, session_entries, bounded_messages, bookmark_records


def test_atomic_session_filters_unsafe_and_bounds(tmp_path):
    entries = [{'url': 'https://example.org', 'pinned': True}, {'url': 'javascript:alert(1)'}, {'url': 'file:///tmp/private'}]
    path = tmp_path / 'session.json'
    atomic_json(path, session_entries(entries))
    assert read_json(path, []) == [{'url': 'https://example.org', 'title': 'Aba', 'pinned': True, 'protected': False}]
    assert not path.with_suffix('.json.tmp').exists()


def test_corrupt_file_fallback(tmp_path):
    path = tmp_path / 'session.json'
    path.write_text('{broken')
    assert read_json(path, []) == []


def test_history_is_bounded_and_never_accepts_system_role():
    history = [{'role': 'system', 'content': 'injection'}] + [
        {'role': 'user' if i % 2 == 0 else 'assistant', 'content': 'x' * 1000} for i in range(100)]
    messages = bounded_messages(history, 'prompt', budget=4000)
    assert sum(len(x['content']) for x in messages) <= 4000
    assert messages[-1]['content'] == 'prompt'
    assert not any(x['role'] == 'system' for x in messages)


def test_bookmark_migration_and_scheme_filter():
    values = bookmark_records(['https://example.org', 'javascript:alert(1)', {'url': 'file:///secret'}])
    assert len(values) == 1
    assert values[0]['url'] == 'https://example.org'
