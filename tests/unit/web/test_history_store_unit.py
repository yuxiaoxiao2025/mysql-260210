from unittest.mock import MagicMock, mock_open, patch

from src.web.utils.history_store import HistoryStore


def _store():
    with patch("pathlib.Path.mkdir"):
        return HistoryStore(history_file="history.json")


def test_load_returns_empty_when_file_missing():
    store = _store()
    with patch("pathlib.Path.exists", return_value=False):
        assert store.load() == []


def test_load_reads_json_when_file_exists():
    store = _store()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data='[{"query":"q1"}]')):
            assert store.load() == [{"query": "q1"}]


def test_load_returns_empty_when_json_invalid():
    store = _store()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="not-json")):
            assert store.load() == []


def test_save_writes_json_and_returns_true():
    store = _store()
    writer = mock_open()
    with patch("builtins.open", writer):
        assert store.save([{"query": "q1"}]) is True


def test_save_returns_false_on_exception():
    store = _store()
    with patch("builtins.open", side_effect=OSError("denied")):
        assert store.save([{"query": "q1"}]) is False


def test_add_entry_appends_and_trims_to_100():
    store = _store()
    history = [{"timestamp": str(i), "query": f"q{i}", "selected_tables": [], "generated_sql": None} for i in range(100)]
    store.load = MagicMock(return_value=history)
    captured = {}

    def _save(data):
        captured["data"] = data
        return True

    store.save = MagicMock(side_effect=_save)
    ok = store.add_entry("new-query", ["users"], "SELECT 1")
    assert ok is True
    assert len(captured["data"]) == 100
    assert captured["data"][-1]["query"] == "new-query"
    assert captured["data"][0]["query"] == "q1"


def test_get_latest_returns_reverse_order():
    store = _store()
    store.load = MagicMock(
        return_value=[
            {"timestamp": "1", "query": "q1"},
            {"timestamp": "2", "query": "q2"},
            {"timestamp": "3", "query": "q3"},
        ]
    )
    result = store.get_latest(limit=2)
    assert result == [{"timestamp": "3", "query": "q3"}, {"timestamp": "2", "query": "q2"}]


def test_clear_delegates_to_save_empty_list():
    store = _store()
    store.save = MagicMock(return_value=True)
    assert store.clear() is True
    store.save.assert_called_once_with([])


def test_restore_session_returns_entry_when_found():
    store = _store()
    store.load = MagicMock(return_value=[{"timestamp": "t1", "query": "q1"}, {"timestamp": "t2", "query": "q2"}])
    assert store.restore_session("t2") == {"timestamp": "t2", "query": "q2"}


def test_restore_session_returns_none_when_missing():
    store = _store()
    store.load = MagicMock(return_value=[{"timestamp": "t1", "query": "q1"}])
    assert store.restore_session("missing") is None
