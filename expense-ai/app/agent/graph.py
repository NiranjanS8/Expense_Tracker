"""The bounded LangGraph workflow.

One graph, no autonomous loop: context is loaded, intent is classified, at most a
few allowlisted read-only tools are called, and every path ends at
``persist_and_trace``. Routing is deterministic code, so model output can never
widen the allowlist or choose a user.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import AgentNodes
from app.agent.policies import DATA_INTENT, DRAFT_INTENT
from app.agent.state import AgentContext, AgentState

CompiledAgentGraph = CompiledStateGraph[AgentState, AgentContext, AgentState, AgentState]


def build_agent_graph(nodes: AgentNodes, *, max_tool_calls: int) -> CompiledAgentGraph:
    def after_classify(state: AgentState) -> str:
        intent = state.get("intent")
        if intent == DATA_INTENT:
            return "plan"
        if intent == DRAFT_INTENT:
            return "compose_draft"
        return "compose_answer"

    def after_plan(state: AgentState) -> str:
        if state.get("tool_call") is not None:
            return "validate_arguments"
        # An answer to a data question with no retrieved figures is not grounded;
        # compose_answer replaces it with a deterministic refusal.
        if state.get("answer") and state.get("intent") == DATA_INTENT and not state.get("tool_result_json"):
            return "compose_answer"
        if state.get("answer"):
            return "persist_and_trace"
        return "compose_answer"

    def after_validate(state: AgentState) -> str:
        return "compose_answer" if state.get("tool_error") else "authorize_tool"

    def after_authorize(state: AgentState) -> str:
        return "compose_answer" if state.get("tool_error") else "execute_tool"

    def after_verify(state: AgentState) -> str:
        if state.get("tool_error"):
            return "compose_answer"
        if state.get("tool_calls_made", 0) >= max_tool_calls:
            return "compose_answer"
        return "plan"

    graph = StateGraph(AgentState, context_schema=AgentContext)
    graph.add_node("load_context", nodes.load_context)
    graph.add_node("classify_intent", nodes.classify_intent)
    graph.add_node("plan", nodes.plan)
    graph.add_node("validate_arguments", nodes.validate_arguments)
    graph.add_node("authorize_tool", nodes.authorize_tool)
    graph.add_node("execute_tool", nodes.execute_tool)
    graph.add_node("verify_result", nodes.verify_result)
    graph.add_node("compose_draft", nodes.compose_draft)
    graph.add_node("compose_answer", nodes.compose_answer)
    graph.add_node("persist_and_trace", nodes.persist_and_trace)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        after_classify,
        {
            "plan": "plan",
            "compose_draft": "compose_draft",
            "compose_answer": "compose_answer",
        },
    )
    graph.add_conditional_edges(
        "plan",
        after_plan,
        {
            "validate_arguments": "validate_arguments",
            "persist_and_trace": "persist_and_trace",
            "compose_answer": "compose_answer",
        },
    )
    graph.add_conditional_edges(
        "validate_arguments",
        after_validate,
        {"authorize_tool": "authorize_tool", "compose_answer": "compose_answer"},
    )
    graph.add_conditional_edges(
        "authorize_tool",
        after_authorize,
        {"execute_tool": "execute_tool", "compose_answer": "compose_answer"},
    )
    graph.add_edge("execute_tool", "verify_result")
    graph.add_conditional_edges(
        "verify_result",
        after_verify,
        {"plan": "plan", "compose_answer": "compose_answer"},
    )
    graph.add_edge("compose_answer", "persist_and_trace")
    graph.add_edge("compose_draft", "persist_and_trace")
    graph.add_edge("persist_and_trace", END)

    return graph.compile()
