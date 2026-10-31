from langgraph.graph import StateGraph, END

from app.services.dispute_state import DisputeState
from app.services.dispute_nodes import analyze_dispute_node

graph_builder = StateGraph(DisputeState)

graph_builder.add_node("analyze_dispute", analyze_dispute_node)

graph_builder.set_entry_point("analyze_dispute")
graph_builder.add_edge("analyze_dispute", END)

dispute_graph = graph_builder.compile()
