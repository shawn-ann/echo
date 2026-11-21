from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    make_fluency_node,
    make_locate_node,
    make_minimal_node,
    minimal_passthrough_node,
    route_after_validate,
    validate_errors_node,
)
from app.graph.state import CorrectionState
from app.services.llm_client import LLMClient


def build_graph(client: LLMClient):
    graph = StateGraph(CorrectionState)
    graph.add_node("error_locate", make_locate_node(client))
    graph.add_node("validate_errors", validate_errors_node)
    graph.add_node("minimal_edit", make_minimal_node(client))
    graph.add_node("minimal_passthrough", minimal_passthrough_node)
    graph.add_node("native_fluency", make_fluency_node(client))

    graph.set_entry_point("error_locate")
    graph.add_edge("error_locate", "validate_errors")
    graph.add_conditional_edges(
        "validate_errors",
        route_after_validate,
        {
            "minimal_edit": "minimal_edit",
            "minimal_passthrough": "minimal_passthrough",
        },
    )
    graph.add_edge("validate_errors", "native_fluency")
    graph.add_edge("minimal_edit", END)
    graph.add_edge("minimal_passthrough", END)
    graph.add_edge("native_fluency", END)
    return graph.compile()
