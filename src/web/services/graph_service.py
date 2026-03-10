"""
Knowledge Graph Service for Knowledge Graph Explorer.

Provides graph building and subgraph extraction functionality.
"""

import logging
from typing import List, Dict, Any, Tuple

import networkx as nx

from src.metadata.schema_indexer import SchemaIndexer
from src.metadata.models import KnowledgeGraph, TableMetadata, ForeignKeyRelation

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Service for building and querying knowledge graphs."""

    def __init__(self, schema_indexer: SchemaIndexer):
        """Initialize with SchemaIndexer.

        Args:
            schema_indexer: SchemaIndexer instance for graph data.
        """
        self.schema_indexer = schema_indexer
        self._graph: nx.MultiDiGraph = None

    def _build_graph(self) -> nx.MultiDiGraph:
        """Build NetworkX graph from KnowledgeGraph metadata."""
        # Load knowledge graph from graph_store
        kg = self.schema_indexer.graph_store.load_graph()

        if kg is None:
            logger.warning("No knowledge graph found, returning empty graph")
            return nx.MultiDiGraph()

        # Create NetworkX directed graph
        G = nx.MultiDiGraph()

        # Add table nodes
        for table in kg.tables:
            G.add_node(
                table.table_name,
                table_comment=table.comment or "",
                columns=[c.name for c in table.columns]
            )

        # Add foreign key edges (iterate through all tables)
        for table in kg.tables:
            for fk in table.foreign_keys:
                G.add_edge(
                    table.table_name,
                    fk.referenced_table,
                    relationship="foreign_key",
                    from_column=fk.column_name,
                    to_column=fk.referenced_column
                )

        return G

    def build_graph(self) -> nx.MultiDiGraph:
        """Build and return the NetworkX graph.

        Returns:
            NetworkX MultiDiGraph representing the knowledge graph.
        """
        self._graph = self._build_graph()
        return self._graph

    @property
    def graph(self) -> nx.MultiDiGraph:
        """Get the full NetworkX graph, building if necessary."""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def get_neighbors(self, table_name: str) -> List[str]:
        """Get direct neighbors of a table in the graph.

        Args:
            table_name: Name of the table.

        Returns:
            List of neighbor table names.
        """
        G = self.graph
        if table_name not in G:
            return []
        return list(G.neighbors(table_name))

    def get_subgraph_for_tables(
        self,
        table_names: List[str],
        radius: int = 1
    ) -> Dict[str, List[Dict]]:
        """Get subgraph with selected tables and their neighbors.

        Args:
            table_names: List of table names to get subgraph for.
            radius: Number of hops to include (default 1).

        Returns:
            Dict with 'nodes' and 'edges' lists for visualization.
        """
        G = self.graph

        # Handle empty input
        if not table_names:
            return {"nodes": [], "edges": []}

        # Get ego graph with specified radius (includes neighbors)
        nodes_to_include = set(table_names)
        for _ in range(radius):
            new_nodes = set()
            for table in nodes_to_include:
                if table in G:
                    new_nodes.update(G.neighbors(table))
            nodes_to_include.update(new_nodes)

        # Filter to only existing nodes
        nodes_to_include = nodes_to_include & set(G.nodes())
        if not nodes_to_include:
            return {"nodes": [], "edges": []}

        # Create subgraph
        subgraph = G.subgraph(nodes_to_include)

        # Convert to node/edge dicts for visualization
        nodes = [
            {
                "id": node,
                "label": node,
                **G.nodes[node]
            }
            for node in subgraph.nodes()
        ]

        edges = [
            {
                "id": f"{u}->{v}",
                "source": u,
                "target": v,
                **d
            }
            for u, v, d in subgraph.edges(data=True)
        ]

        return {"nodes": nodes, "edges": edges}