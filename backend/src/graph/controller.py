from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any

from src.agents.document_agent import document_agent
from src.agents.analytics_agent import analytics_agent
from src.agents.sanity_agent import sanity_agent


# ---------------------------
# Define Graph State Schema
# ---------------------------

class LeaseState(TypedDict, total=False):
    file_path: str
    source_filename: str
    source_s3_key: str
    raw_text: str
    raw_text_original: str
    translation_meta: Dict[str, Any]
    structured_data: Dict[str, Any]
    analytics_result: Dict[str, Any]
    sanity_flags: list
    lease_id: int
    execution_log: list
    user_query: str
    chat_history: list
    chat_response: str


# ---------------------------
# Build Graph
# ---------------------------

builder = StateGraph(LeaseState)

builder.add_node("document", document_agent)
builder.add_node("analytics", analytics_agent)
builder.add_node("sanity", sanity_agent)

builder.set_entry_point("document")

builder.add_edge("document", "analytics")
builder.add_edge("analytics", "sanity")
builder.add_edge("sanity", END)

# ---------------------------
# Compile Graph
# ---------------------------

graph = builder.compile()
