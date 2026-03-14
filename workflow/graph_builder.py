from typing import Any

import networkx as nx


class WorkflowGraphBuilder:
    def build(self, plan: dict[str, Any]) -> nx.DiGraph:
        graph = nx.DiGraph()
        steps = plan.get("steps", [])

        node_ids: list[str] = []
        for index, step in enumerate(steps, start=1):
            node_id = step.get("id") or f"step_{index}"
            node_ids.append(node_id)
            graph.add_node(node_id, **step)

        for index, step in enumerate(steps, start=1):
            current = step.get("id") or f"step_{index}"
            depends_on = step.get("depends_on", [])

            if depends_on:
                for dependency in depends_on:
                    graph.add_edge(dependency, current)
            elif index > 1:
                previous = node_ids[index - 2]
                graph.add_edge(previous, current)

        return graph
