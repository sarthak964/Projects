from langgraph.graph import StateGraph, END

from app.services.verification_state import VerificationState
from app.services.verification_nodes import (
    check_checklist_node,
    decide_node,
    summarize_node,
    flag_incomplete_node,
)

graph_builder = StateGraph(VerificationState)

graph_builder.add_node("check_checklist", check_checklist_node)
graph_builder.add_node("decide", decide_node)
graph_builder.add_node("summarize", summarize_node)
graph_builder.add_node("flag_incomplete", flag_incomplete_node)


def route_after_decide(state: VerificationState) -> str:
    return "summarize" if state["all_addressed"] else "flag_incomplete"


graph_builder.set_entry_point("check_checklist")
graph_builder.add_edge("check_checklist", "decide")

graph_builder.add_conditional_edges(
    "decide",
    route_after_decide,
    {
        "summarize": "summarize",
        "flag_incomplete": "flag_incomplete",
    },
)

graph_builder.add_edge("summarize", END)
graph_builder.add_edge("flag_incomplete", END)

verification_graph = graph_builder.compile()
