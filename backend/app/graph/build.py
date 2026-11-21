from langgraph.graph import END, StateGraph

from app.graph.nodes import make_locate_node, validate_errors_node
from app.graph.state import CorrectionState
from app.services.llm_client import LLMClient


def build_graph(client: LLMClient):
    graph = StateGraph(CorrectionState)
    graph.add_node("error_locate", make_locate_node(client))
    graph.add_node("validate_errors", validate_errors_node)

    graph.set_entry_point("error_locate")
    graph.add_edge("error_locate", "validate_errors")
    graph.add_edge("validate_errors", END)
    return graph.compile()
