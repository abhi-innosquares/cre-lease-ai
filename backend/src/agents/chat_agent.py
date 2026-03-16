from langchain_openai import ChatOpenAI
import json
from typing import Any

from src.utils.currency import format_currency_amount


# create a single LLM instance when the module loads to avoid repeated setup cost
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0,  # Lower temperature for faster, more deterministic responses
    max_tokens=500  # limit output size
)


def chat_agent(state: dict):

    raw_text = state.get("raw_text", "")
    user_query = state.get("user_query", "")
    chat_history = state.get("chat_history", [])
    structured_data = state.get("structured_data", {})

    # Format chat history for context
    history_context = ""
    if chat_history and isinstance(chat_history, list):
        history_lines = ["Earlier in our conversation:"]
        for msg in chat_history[-3:]:  # Keep only last 3 exchanges to reduce size
            role = "You" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")[:100]  # further shorten content size
            history_lines.append(f"{role}: {content}")
        history_context = "\n".join(history_lines) + "\n\n"

    # Extract key lease details for quick reference
    key_details = ""
    if structured_data:
        original_display = structured_data.get("base_rent_display") or format_currency_amount(
            structured_data.get("base_rent"), structured_data.get("currency")
        )
        normalized_display = structured_data.get("normalized_base_rent_display") or format_currency_amount(
            structured_data.get("normalized_base_rent"), structured_data.get("normalized_currency")
        )
        key_details = f"""
Key Lease Information:
- Tenant: {structured_data.get('tenant_name', 'Not specified')}
- Location: {structured_data.get('property_address', 'Not specified')}
- Commencement: {structured_data.get('commencement_date', 'Not specified')}
- Expiration: {structured_data.get('expiration_date', 'Not specified')}
- Annual Base Rent: {original_display}
- Normalized Base Rent ({structured_data.get('normalized_currency', 'portfolio basis')}): {normalized_display}
\n"""

    prompt = f"""
    You are a knowledgeable lease analysis expert. Answer questions about the lease in a natural, conversational way.
    
    TONE GUIDELINES:
    - Be friendly and helpful, like talking to a colleague
    - Use natural language and complete sentences
    - Show understanding of the user's needs
    - Provide context and explanations, not just data
    - Use phrases like "I see here that...", "Based on the lease...", "Looking at this..."
    - If rent is discussed, mention both the original currency and the normalized portfolio-basis amount when available
    - Avoid robotic or formal language
    
    {history_context}{key_details}
    
    Lease Document (excerpt):
    {raw_text[:800]}  # further reduce excerpt length for speed
    
    Question from user:
    {user_query}
    
    Provide a natural, helpful answer strictly based on the lease content. If information is missing, acknowledge that politely.
    """

    response = llm.invoke(prompt)

    state["chat_response"] = response.content
    state["chat_history"] = chat_history  # Pass history forward

    return state
