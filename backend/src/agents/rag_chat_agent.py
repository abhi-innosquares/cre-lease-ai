from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from vector_store import load_vector_store


# ==============================
# GLOBAL STATE
# ==============================

VECTOR_CACHE: Dict[str, any] = {}
CHAT_MEMORY: Dict[str, List[Dict]] = {}
SESSION_ACTIVE_LEASE: Dict[str, Dict] = {}


# ==============================
# VECTORSTORE CACHE
# ==============================

def get_vectorstore(lease_id: str):

    if lease_id not in VECTOR_CACHE:
        VECTOR_CACHE[lease_id] = load_vector_store(lease_id)

    return VECTOR_CACHE[lease_id]


# ==============================
# LLM
# ==============================

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    streaming=True
)


# ==============================
# PROMPT
# ==============================

rag_prompt = PromptTemplate(
    input_variables=[
        "active_lease_id",
        "tenant_name",
        "history",
        "context",
        "question"
    ],
    template="""
You are an expert Commercial Lease Portfolio Assistant.

Your job is to analyze lease documents and portfolio data and answer questions accurately.

-------------------------
CRITICAL RULES
-------------------------

1. ONLY use the information provided in the context.
2. NEVER invent leases, tenants, clauses, dates, or financial terms.
3. If the information is not present in the context respond exactly with:

   "Not found in lease data."

4. If the user asks a follow-up question assume they are referring to the CURRENT ACTIVE LEASE unless they explicitly mention another lease.

5. DO NOT mention any lease that is not included in the provided context.

6. Always prioritize the lease identified as the ACTIVE LEASE.

7. If multiple leases are present clearly specify which lease the answer refers to.

-------------------------
ACTIVE LEASE
-------------------------

Lease ID: {active_lease_id}
Tenant Name: {tenant_name}

The user is currently asking questions about this lease unless specified otherwise.

-------------------------
CONVERSATION HISTORY
-------------------------

{history}

-------------------------
LEASE CONTEXT
-------------------------

{context}

-------------------------
USER QUESTION
-------------------------

{question}

-------------------------
ANSWER FORMAT
-------------------------

Answer:
Provide a clear explanation.

Lease Reference:
Specify lease ID and tenant name.

Citations:
Provide clause or section reference if available.

-------------------------
IMPORTANT
-------------------------

• Do NOT hallucinate information.
• If the answer is missing say exactly:
  "Not found in lease data."

"""
)


# ==============================
# MEMORY
# ==============================

def get_memory(session_id: str):

    if session_id not in CHAT_MEMORY:
        CHAT_MEMORY[session_id] = []

    return CHAT_MEMORY[session_id]


def format_history(history):

    lines = []

    for msg in history[-4:]:

        role = msg["role"]
        content = msg["content"]

        if role == "user":
            lines.append(f"User: {content}")
        else:
            lines.append(f"Assistant: {content}")

    return "\n".join(lines)


# ==============================
# ACTIVE LEASE STATE
# ==============================

def set_active_lease(session_id: str, lease_id: str, tenant_name: str):

    SESSION_ACTIVE_LEASE[session_id] = {
        "lease_id": lease_id,
        "tenant_name": tenant_name
    }


def get_active_lease(session_id: str):

    return SESSION_ACTIVE_LEASE.get(session_id, {
        "lease_id": "Unknown",
        "tenant_name": "Unknown"
    })


# ==============================
# PARALLEL RETRIEVAL
# ==============================

def retrieve_docs(lease_ids: List[str], question: str):

    def search_single(lease_id):

        vectorstore = get_vectorstore(lease_id)

        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 3,
                "fetch_k": 5
            }
        )

        docs = retriever.invoke(question)

        for doc in docs:
            doc.metadata["lease_id"] = lease_id

        return docs

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(search_single, lease_ids))

    docs = []

    for r in results:
        docs.extend(r)

    return docs[:3]


# ==============================
# CONTEXT BUILDER
# ==============================

def build_context(docs):

    blocks = []

    for doc in docs:

        lease_id = doc.metadata.get("lease_id", "Unknown Lease")
        clause = doc.metadata.get("clause", "Unknown Clause")

        text = doc.page_content[:250]

        block = f"""
Lease ID: {lease_id}
Clause: {clause}

{text}
"""

        blocks.append(block)

    return "\n\n".join(blocks)


# ==============================
# MAIN RAG CHAT
# ==============================

def rag_chat(
    session_id: str,
    lease_ids: List[str],
    question: str
):
    import time

    start = time.time()

    docs = retrieve_docs(lease_ids, question)
    print("Retrieval Time:", time.time() - start)

    start_llm = time.time()

    response = llm.invoke(prompt)

    print("LLM Time:", time.time() - start_llm)
    history = get_memory(session_id)

    history_text = format_history(history)

    # Active lease info
    active_lease = get_active_lease(session_id)

    active_lease_id = active_lease["lease_id"]
    tenant_name = active_lease["tenant_name"]

    # Retrieve docs
    docs = retrieve_docs(lease_ids, question)

    if not docs:

        return {
            "answer": "No relevant lease information found.",
            "citations": []
        }

    # Build context
    context = build_context(docs)

    # Create prompt
    prompt = rag_prompt.format(
        active_lease_id=active_lease_id,
        tenant_name=tenant_name,
        history=history_text,
        context=context,
        question=question
    )

    # LLM call
    response = llm.invoke(prompt)

    answer = response.content

    # Extract citations
    citations = []

    for doc in docs:

        citations.append({
            "lease_id": doc.metadata.get("lease_id"),
            "clause": doc.metadata.get("clause")
        })

    # Update memory
    history.append({
        "role": "user",
        "content": question
    })

    history.append({
        "role": "assistant",
        "content": answer
    })

    return {
        "answer": answer,
        "citations": citations
    }