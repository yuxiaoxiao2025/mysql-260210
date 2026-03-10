import os
import socket
import sys
import time
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PYTEST_TMPDIR = PROJECT_ROOT / ".pytest_tmp"
PYTEST_TMPDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PYTEST_TMPDIR", str(PYTEST_TMPDIR))

if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.SimpleNamespace(session_state={})

if "networkx" not in sys.modules:
    class _NodeView:
        def __init__(self, graph):
            self._graph = graph

        def __call__(self):
            return list(self._graph._nodes.keys())

        def __getitem__(self, item):
            return self._graph._nodes[item]

        def __iter__(self):
            return iter(self._graph._nodes.keys())

    class _MultiDiGraph:
        def __init__(self):
            self._nodes = {}
            self._edges = []

        @property
        def nodes(self):
            return _NodeView(self)

        def add_node(self, node, **attrs):
            self._nodes[node] = attrs

        def add_edge(self, u, v, **attrs):
            if u not in self._nodes:
                self._nodes[u] = {}
            if v not in self._nodes:
                self._nodes[v] = {}
            self._edges.append((u, v, dict(attrs)))

        def neighbors(self, node):
            return [v for u, v, _ in self._edges if u == node]

        def subgraph(self, nodes):
            sub = _MultiDiGraph()
            node_set = set(nodes)
            for node in node_set:
                if node in self._nodes:
                    sub.add_node(node, **self._nodes[node])
            for u, v, attrs in self._edges:
                if u in node_set and v in node_set:
                    sub.add_edge(u, v, **attrs)
            return sub

        def edges(self, data=False):
            if data:
                return [(u, v, attrs) for u, v, attrs in self._edges]
            return [(u, v) for u, v, _ in self._edges]

        def has_edge(self, u, v):
            return any(eu == u and ev == v for eu, ev, _ in self._edges)

        def get_edge_data(self, u, v):
            payload = {}
            idx = 0
            for eu, ev, attrs in self._edges:
                if eu == u and ev == v:
                    payload[idx] = attrs
                    idx += 1
            return payload

        def number_of_nodes(self):
            return len(self._nodes)

        def number_of_edges(self):
            return len(self._edges)

        def __contains__(self, item):
            return item in self._nodes

    def _shortest_path(graph, source, target):
        queue = [(source, [source])]
        visited = set()
        while queue:
            node, path = queue.pop(0)
            if node == target:
                return path
            if node in visited:
                continue
            visited.add(node)
            for nxt in graph.neighbors(node):
                if nxt not in visited:
                    queue.append((nxt, path + [nxt]))
        raise ValueError("No path")

    sys.modules["networkx"] = types.SimpleNamespace(MultiDiGraph=_MultiDiGraph, shortest_path=_shortest_path)


@pytest.fixture(autouse=True)
def no_blocking_sleep(monkeypatch):
    def _sleep(*_args, **_kwargs):
        raise AssertionError("单元测试禁止使用 time.sleep")

    monkeypatch.setattr(time, "sleep", _sleep)


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def _blocked(*_args, **_kwargs):
        raise AssertionError("单元测试禁止真实网络请求")

    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def reset_streamlit_state():
    streamlit = sys.modules["streamlit"]
    streamlit.session_state = {}
    yield
    streamlit.session_state = {}
