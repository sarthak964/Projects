from langgraph.graph import StateGraph, END

from app.services.support_state import SupportState
from app.services.support_nodes import classify_support_message_node

graph_builder = StateGraph(SupportState)

graph_builder.add_node("classify", classify_support_message_node)

graph_builder.set_entry_point("classify")
graph_builder.add_edge("classify", END)

support_graph = graph_builder.compile()
