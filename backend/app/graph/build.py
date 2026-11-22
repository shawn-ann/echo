from typing import Any

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    make_explain_node,
    make_fluency_node,
    make_locate_node,
    make_minimal_node,
    minimal_passthrough_node,
    reset_correction_node,
    resolve_target_node,
    route_after_validate,
    route_node,
    validate_errors_node,
)
from app.graph.state import CorrectionState
from app.services.llm_client import LLMClient


def build_graph(client: LLMClient, checkpointer: Any = None):
    graph = StateGraph(CorrectionState)
    graph.add_node("route", route_node)
    graph.add_node("reset_correction", reset_correction_node)
    graph.add_node("error_locate", make_locate_node(client))
    graph.add_node("validate_errors", validate_errors_node)
    graph.add_node("minimal_edit", make_minimal_node(client))
    graph.add_node("minimal_passthrough", minimal_passthrough_node)
    graph.add_node("native_fluency", make_fluency_node(client))
    graph.add_node("resolve_target", resolve_target_node)
    graph.add_node("explain", make_explain_node(client))

    graph.set_entry_point("route")
    graph.add_conditional_edges(
        "route",
        lambda state: state["intent"],
        {
            "correct": "reset_correction",
            "followup": "resolve_target",
        },
    )
    graph.add_edge("reset_correction", "error_locate")
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
    graph.add_edge("resolve_target", "explain")
    graph.add_edge("minimal_edit", END)
    graph.add_edge("minimal_passthrough", END)
    graph.add_edge("native_fluency", END)
    graph.add_edge("explain", END)
    return graph.compile(checkpointer=checkpointer)
