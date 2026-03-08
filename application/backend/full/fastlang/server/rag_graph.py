from typing import TypedDict, List

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from tools.web_rag.retrieval_manager import RETRIEVAL_MANAGER
from tools.config import CONFIG_STORE


class RAGState(TypedDict):
    messages: List[BaseMessage]
    thread_id: str
    user_id: str


def build_enforced_rag_graph(model_name: str, checkpointer):
    """
    Build a LangGraph where retrieval is always executed
    before the LLM generates a response.
    """

    llm = ChatOpenAI(model=model_name)

    def retrieve_node(state: RAGState):
        config = CONFIG_STORE.get("web_rag") or {"embedding_provider": "fastembed"}

        retriever = RETRIEVAL_MANAGER.get_retriever(
            config=config,
            user_id=state["user_id"],
            k=5,
        )

        # Use latest user message as query
        user_messages = [m for m in state["messages"] if m.type == "human"]
        if not user_messages:
            return state

        query = user_messages[-1].content
        docs = retriever.invoke(query)

        context_text = "\n\n".join([d.page_content for d in docs])

        system_msg = SystemMessage(
            content=f"Use the following retrieved context to answer:\n\n{context_text}"
        )

        state["messages"] = [system_msg] + state["messages"]
        return state

    def llm_node(state: RAGState):
        response = llm.invoke(state["messages"])
        state["messages"].append(response)
        return state

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("llm", llm_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "llm")
    graph.add_edge("llm", END)

    return graph.compile(checkpointer=checkpointer)
