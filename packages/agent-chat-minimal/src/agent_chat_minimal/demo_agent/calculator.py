"""Calculator reference agent: arbitrary-agent example (#13)."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph import StateGraph

from .agent_factory import make_tool_agent


@tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@tool
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


CALCULATOR_TOOLS = [add, subtract, multiply, divide]

CALCULATOR_SYSTEM_PROMPT = (
    "You are a calculator assistant. "
    "For any arithmetic request, call the appropriate tool "
    "(add, subtract, multiply, divide) and reply with the result."
)


def make_calculator_agent(
    model: str | BaseChatModel = "openai:gpt-4o-mini",
    checkpointer=None,
) -> StateGraph:
    """Build the calculator agent for any provider model spec/instance."""
    return make_tool_agent(
        model, list(CALCULATOR_TOOLS), CALCULATOR_SYSTEM_PROMPT, checkpointer
    )
