from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from api.agent.context import Context
from api.agent.state import InputState, State
from api.agent.tools import get_tools
from api.agent.utils import load_chat_model
from db.code_serarch_layer import CodeSearchService


def build_graph(query_service: CodeSearchService, context: Context | None = None, repo_id: str | None = None):
    ctx = context or Context()

    # Give the LLM the search_code tool so it knows it can search Neo4j.
    # If repo_id is set, all tools are scoped to that repository.
    tools = get_tools(query_service, repo_id=repo_id)
    llm = load_chat_model(ctx.model).bind_tools(tools)

    def LLM_Node(state: State):
        # Build the system prompt with the current time, then send the
        # full conversation history to the LLM.
        # The LLM returns either:
        #   - AIMessage with tool_calls → it wants to search something
        #   - AIMessage with content    → it has a final answer
        repo_context = (
            f"\n\n---\nActive repository: **{repo_id}** — all tools are already scoped to this repo."
            if repo_id
            else "\n\n---\nNo repository selected — searches run across the entire graph."
        )
        system_prompt = ctx.system_prompt.format(system_time=datetime.now(tz=UTC).isoformat()) + repo_context
        response: AIMessage = llm.invoke([{"role": "system", "content": system_prompt}, *state.messages])

        # Safety: if we've hit the recursion limit and the LLM still wants
        # to call a tool, stop it and return a fallback message instead.
        if state.is_last_step and response.tool_calls:
            return {"messages": [AIMessage(id=response.id, content="Could not find an answer within the allowed steps.")]}

        return {"messages": [response]}

    def should_continue(state: State) -> Literal["tools", "__end__"]:
        # Read the last message (what llm_node just returned).
        # If the LLM called a tool → go to the tools node to execute it.
        # If the LLM wrote a final answer → stop.
        last = state.messages[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "__end__"

    builder = StateGraph(State, input_schema=InputState)

    # Register the two nodes (boxes in the flowchart).
    # "llm_node" → runs the LLM
    # "tools"      → runs whatever tool the LLM asked for (e.g. search_code)
    builder.add_node("llm_node", LLM_Node)
    builder.add_node("tools", ToolNode(tools))

    # Entry point — every invocation starts here.
    # Example: user asks "where is auth handled?" → first stop is llm_node
    builder.add_edge("__start__", "llm_node")

    # After llm_node runs, ask should_continue() what to do next.
    # Example A: LLM returned tool_calls=["search_code"] → should_continue returns "tools"
    # Example B: LLM returned a plain text answer         → should_continue returns "__end__"
    builder.add_conditional_edges("llm_node", should_continue)

    # After tools runs, always go back to llm_node.
    # Example: search_code returned "FirebaseAuthMiddleware → api/middleware/firebase_auth.py:25"
    #          → LLM reads that result and now writes the final answer
    builder.add_edge("tools", "llm_node")

    return builder.compile(name="BugViper Agent")
