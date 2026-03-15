from __future__ import annotations

import logging
from pathlib import Path

import networkx as nx
from graphviz import Digraph
from graphviz.backend.execute import ExecutableNotFound

logger = logging.getLogger(__name__)


class WorkflowVisualizer:
    def __init__(self, output_dir: str = "workflow_diagrams") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def render(self, workflow_id: str, graph: nx.DiGraph) -> str:
        diagram = Digraph(name=f"workflow_{workflow_id}", format="png")

        for node_id, data in graph.nodes(data=True):
            label = f"{node_id}\n{data.get('agent', 'unknown')}"
            diagram.node(node_id, label=label)

        for source, target in graph.edges:
            diagram.edge(source, target)

        output_path = self._output_dir / f"{workflow_id}"
        try:
            rendered = diagram.render(filename=output_path.name, directory=str(self._output_dir), cleanup=True)
            return rendered
        except ExecutableNotFound:
            fallback_path = self._output_dir / f"{workflow_id}.dot"
            diagram.save(filename=fallback_path.name, directory=str(self._output_dir))
            logger.warning("Graphviz 'dot' binary not found. Saved DOT workflow file at %s", fallback_path)
            return str(fallback_path)