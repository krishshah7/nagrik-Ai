"""
ai_agents.py
All AI logic for Nagrik AI lives in this one file, kept simple on purpose:

  Phase 2 - Generative AI
      classify_complaint()   -> category / severity / summary / suggested action
      rewrite_complaint()    -> cleans up a citizen's raw complaint text
      translate_complaint()  -> translates text into another language
      citizen_guidance()     -> answers "how do I..." questions

  Phase 3 - RAG
      knowledge_agent_answer() -> answers questions using municipal documents
                                  stored in data/municipal_docs/

  Phase 4 - Agentic AI
      run_agent() -> a Router decides whether a chat message should go to the
                      Complaint Agent, the Knowledge Agent, or the Analytics
                      Agent, built with LangGraph.

If GEMINI_API_KEY is not set in .env, every function below still works using
simple rule-based / keyword fallbacks, so the app never crashes without a key.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_AI = bool(GEMINI_API_KEY)

model = None
if USE_AI:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")


def _ask_gemini(prompt: str):
    """Send a prompt to Gemini. Returns None if AI is disabled or the call fails."""
    if not USE_AI:
        return None
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[ai_agents] Gemini error: {e}")
        return None


def _extract_json(text):
    """Pull a JSON object out of a model response, even if wrapped in ```json fences."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("json", "", 1)
    try:
        return json.loads(cleaned)
    except Exception:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start:end + 1])
            except Exception:
                return None
    return None


# ---------------------------------------------------------------------------
# PHASE 2 - Generative AI
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "Road Damage": ["pothole", "road", "street", "asphalt", "footpath"],
    "Drainage": ["drain", "sewage", "waterlogging", "flood", "manhole"],
    "Garbage": ["garbage", "trash", "waste", "dump", "litter"],
    "Streetlight": ["streetlight", "street light", "lamp post", "electricity pole"],
    "Water Supply": ["water supply", "no water", "pipeline", "tap water"],
    "Illegal Construction": ["illegal construction", "encroachment", "unauthorized building"],
}


def _fallback_classify(text: str) -> dict:
    """Rule-based backup used only when no Gemini API key is configured."""
    text_l = text.lower()
    category = "Other"
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text_l for k in keywords):
            category = cat
            break
    severity = "High" if any(w in text_l for w in ["huge", "severe", "urgent", "dangerous", "major"]) else "Medium"
    return {
        "category": category,
        "severity": severity,
        "summary": text.strip()[:150],
        "suggested_action": f"Forward to the {category} department for inspection.",
    }


def classify_complaint(text: str) -> dict:
    """Complaint Agent core logic (Phase 2 + reused in Phase 4)."""
    prompt = f"""You are a civic complaint triage assistant for an Indian municipal corporation.
Read the citizen's complaint and reply with ONLY a JSON object (no markdown, no extra text)
in exactly this shape:
{{
  "category": "<one of Road Damage, Drainage, Garbage, Streetlight, Water Supply, Illegal Construction, Other>",
  "severity": "<Low, Medium, or High>",
  "summary": "<one-sentence summary>",
  "suggested_action": "<one-sentence recommended next step for the municipal team>"
}}

Complaint: "{text}"
"""
    data = _extract_json(_ask_gemini(prompt))
    return data if data else _fallback_classify(text)


def rewrite_complaint(text: str) -> str:
    """Rewrites a citizen's raw complaint into clear, formal language."""
    prompt = (
        "Rewrite the following civic complaint in clear, polite, formal English, "
        f"keeping all the original facts. Return only the rewritten text:\n\n{text}"
    )
    result = _ask_gemini(prompt)
    return result.strip() if result else text


def translate_complaint(text: str, target_language: str = "Hindi") -> str:
    """Translates complaint text / a summary into another language."""
    prompt = f"Translate the following text into {target_language}. Return only the translation:\n\n{text}"
    result = _ask_gemini(prompt)
    return result.strip() if result else f"(AI not configured - translation unavailable)\n{text}"


def citizen_guidance(question: str) -> str:
    """Answers general 'how do I report X' civic process questions."""
    prompt = f"""You are a helpful civic assistant for Indian municipal corporation citizens.
Answer the citizen's question about civic processes clearly and briefly, in 3-5 sentences.

Question: {question}
"""
    result = _ask_gemini(prompt)
    if result:
        return result.strip()
    return "AI guidance is unavailable right now (no GEMINI_API_KEY configured). Please contact your local ward office directly."


# ---------------------------------------------------------------------------
# PHASE 3 - RAG over municipal documents
# ---------------------------------------------------------------------------

DOCS_FOLDER = os.path.join(os.path.dirname(__file__), "data", "municipal_docs")
_vector_store = None


def _load_documents():
    chunks = []
    if not os.path.isdir(DOCS_FOLDER):
        return chunks
    for filename in sorted(os.listdir(DOCS_FOLDER)):
        if filename.endswith(".txt"):
            with open(os.path.join(DOCS_FOLDER, filename), "r", encoding="utf-8") as f:
                text = f.read()
            for para in text.split("\n\n"):
                para = para.strip()
                if para:
                    chunks.append(para)
    return chunks


def _get_vector_store():
    """Builds (once) and caches a FAISS index over the municipal documents."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    if not USE_AI:
        return None
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_community.vectorstores import FAISS
        from langchain.docstore.document import Document

        chunks = _load_documents()
        if not chunks:
            return None
        docs = [Document(page_content=c) for c in chunks]
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)
        _vector_store = FAISS.from_documents(docs, embeddings)
        return _vector_store
    except Exception as e:
        print(f"[ai_agents] Could not build FAISS vector store, falling back to keyword search: {e}")
        return None


def _keyword_search(query: str, top_k: int = 3):
    """Fallback search used when FAISS / embeddings are unavailable."""
    chunks = _load_documents()
    query_words = set(query.lower().split())
    scored = []
    for c in chunks:
        score = len(query_words & set(c.lower().split()))
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]] or chunks[:top_k]


def knowledge_agent_answer(query: str) -> str:
    """Knowledge Agent: retrieve relevant document chunks, then ask Gemini to answer."""
    store = _get_vector_store()
    if store:
        context = "\n\n".join(r.page_content for r in store.similarity_search(query, k=3))
    else:
        context = "\n\n".join(_keyword_search(query))

    if not context:
        return "I couldn't find anything about that in the municipal documents on file."

    if not USE_AI:
        return f"(AI not configured - showing the most relevant document excerpt instead)\n\n{context[:500]}"

    prompt = f"""Answer the citizen's question using ONLY the context below.
If the answer is not in the context, say you don't have that information on file.

Context:
{context}

Question: {query}
"""
    answer = _ask_gemini(prompt)
    return answer.strip() if answer else context[:500]


# ---------------------------------------------------------------------------
# PHASE 4 - Agentic AI (Complaint / Knowledge / Analytics agents + Router)
# ---------------------------------------------------------------------------

def analytics_agent_answer(query: str, stats: dict) -> str:
    """Analytics Agent: answers questions using pre-fetched statistics.
    The LLM only interprets and presents numbers that Flask already computed
    with safe SQLAlchemy queries - it never writes or runs raw SQL itself."""
    if not USE_AI:
        return (
            "(AI not configured - raw stats)\n"
            f"Total complaints: {stats.get('total_complaints')}\n"
            f"By ward: {stats.get('ward_counts')}\n"
            f"By category: {stats.get('category_counts')}\n"
            f"By status: {stats.get('status_counts')}"
        )
    prompt = f"""You are an analytics assistant for a municipal complaints system.
Use ONLY the statistics below to answer the question in 2-4 sentences.

Statistics (JSON): {json.dumps(stats)}

Question: {query}
"""
    answer = _ask_gemini(prompt)
    return answer.strip() if answer else "Could not generate an analytics answer right now."


def _complaint_response(query: str) -> str:
    result = classify_complaint(query)
    return (
        f"This looks like a **{result['category']}** issue with **{result['severity']}** severity.\n"
        f"Summary: {result['summary']}\n"
        f"Suggested action: {result['suggested_action']}\n\n"
        "Go to 'Submit Complaint' to file this officially."
    )


def _route_query(query: str) -> str:
    """Router: decides which agent should handle a chat message."""
    if USE_AI:
        prompt = f"""Classify the message below into exactly one label:
"knowledge"  - questions about rules, schemes, government processes, "who is responsible for..."
"analytics"  - questions about complaint counts, wards, categories, reports, statistics
"complaint"  - the user is describing a new civic problem to report

Message: "{query}"
Respond with only the single label word.
"""
        label = _ask_gemini(prompt)
        if label:
            label = label.strip().lower()
            if label in ("knowledge", "analytics", "complaint"):
                return label
    # keyword fallback
    q = query.lower()
    if any(w in q for w in ["how many", "which ward", "report", "total", "count", "statistics"]):
        return "analytics"
    if any(w in q for w in ["how can i", "how do i", "who is responsible", "rule", "scheme", "process"]):
        return "knowledge"
    return "complaint"


def _run_agent_plain(query: str, stats: dict) -> str:
    """Same 3-agent logic as the LangGraph version, used if langgraph isn't installed."""
    route = _route_query(query)
    if route == "complaint":
        return _complaint_response(query)
    if route == "knowledge":
        return knowledge_agent_answer(query)
    return analytics_agent_answer(query, stats)


try:
    from typing import TypedDict
    from langgraph.graph import StateGraph, END

    class AgentState(TypedDict):
        query: str
        stats: dict
        route: str
        answer: str

    def _router_node(state):
        state["route"] = _route_query(state["query"])
        return state

    def _complaint_node(state):
        state["answer"] = _complaint_response(state["query"])
        return state

    def _knowledge_node(state):
        state["answer"] = knowledge_agent_answer(state["query"])
        return state

    def _analytics_node(state):
        state["answer"] = analytics_agent_answer(state["query"], state["stats"])
        return state

    _graph = StateGraph(AgentState)
    _graph.add_node("router", _router_node)
    _graph.add_node("complaint_agent", _complaint_node)
    _graph.add_node("knowledge_agent", _knowledge_node)
    _graph.add_node("analytics_agent", _analytics_node)
    _graph.set_entry_point("router")
    _graph.add_conditional_edges(
        "router",
        lambda s: s["route"],
        {
            "complaint": "complaint_agent",
            "knowledge": "knowledge_agent",
            "analytics": "analytics_agent",
        },
    )
    _graph.add_edge("complaint_agent", END)
    _graph.add_edge("knowledge_agent", END)
    _graph.add_edge("analytics_agent", END)
    _compiled_graph = _graph.compile()

    def run_agent(query: str, stats: dict) -> str:
        """Router Agent entry point (LangGraph): User -> Router -> one of 3 agents."""
        result = _compiled_graph.invoke({"query": query, "stats": stats, "route": "", "answer": ""})
        return result["answer"]

except ImportError:
    def run_agent(query: str, stats: dict) -> str:
        """Fallback router used only if the langgraph package isn't installed."""
        return _run_agent_plain(query, stats)
