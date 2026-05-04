from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.nodes import (
    attack_human_gate,
    architecture_cocreation_agent,
    compliance_risk_agent,
    iteration_repair_agent,
    jd_parser_agent,
    manual_polish_agent,
    resume_packaging_agent,
    senior_interviewer_agent,
    should_continue_iteration,
    scope_human_gate,
)
from app.agents.state import ResumePolishState
from app.services.json_memory import new_session_id, save_session


CHECKPOINTER = InMemorySaver()


def graph_config(session_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _interrupts(result: Dict[str, Any]) -> list[Dict[str, Any]]:
    values = []
    for item in result.get("__interrupt__", []) or []:
        value = getattr(item, "value", item)
        values.append(value)
    return values


def format_graph_response(session_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    interrupts = _interrupts(result)
    if interrupts:
        return {"status": "interrupted", "session_id": session_id, "interrupts": interrupts}
    save_session(result)
    return {"status": "completed", "session_id": session_id, "state": result}


@lru_cache(maxsize=1)
def build_resume_polish_graph():
    """六 Agent 主闭环：JD 解析 -> 架构共创 -> 简历包装 -> 攻防 -> 修复 -> 合规。"""

    graph = StateGraph(ResumePolishState)
    graph.add_node("jd_parser", jd_parser_agent)
    graph.add_node("human_scope_gate", scope_human_gate)
    graph.add_node("architecture_cocreation", architecture_cocreation_agent)
    graph.add_node("resume_packaging", resume_packaging_agent)
    graph.add_node("senior_interviewer", senior_interviewer_agent)
    graph.add_node("human_attack_gate", attack_human_gate)
    graph.add_node("iteration_repair", iteration_repair_agent)
    graph.add_node("compliance_risk", compliance_risk_agent)

    graph.add_edge(START, "jd_parser")
    graph.add_edge("jd_parser", "human_scope_gate")
    graph.add_edge("human_scope_gate", "architecture_cocreation")
    graph.add_edge("architecture_cocreation", "resume_packaging")
    graph.add_edge("resume_packaging", "senior_interviewer")
    graph.add_edge("senior_interviewer", "human_attack_gate")
    graph.add_edge("human_attack_gate", "iteration_repair")
    graph.add_conditional_edges(
        "iteration_repair",
        should_continue_iteration,
        {"continue": "senior_interviewer", "finish": "compliance_risk"},
    )
    graph.add_edge("compliance_risk", END)
    return graph.compile(checkpointer=CHECKPOINTER)


@lru_cache(maxsize=1)
def build_manual_polish_graph():
    graph = StateGraph(ResumePolishState)
    graph.add_node("manual_polish", manual_polish_agent)
    graph.add_edge(START, "manual_polish")
    graph.add_edge("manual_polish", END)
    return graph.compile(checkpointer=CHECKPOINTER)


def run_full_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    state: ResumePolishState = {
        "session_id": payload.get("session_id") or new_session_id(),
        "jd_text": payload["jd_text"],
        "personal_stack": payload["personal_stack"],
        "target_level": payload.get("target_level", "中级"),
        "human_constraints": payload.get("human_constraints", {}),
        "attack_human_decision": payload.get("attack_human_decision", {}),
        "iteration_round": 0,
        "iteration_history": [],
        "logs": [],
        "errors": [],
    }
    result = build_resume_polish_graph().invoke(state, config=graph_config(state["session_id"]))
    if "__interrupt__" in result:
        return {"session_id": state["session_id"], **result}
    save_session(result)
    return result


def start_hitl_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    session_id = payload.get("session_id") or new_session_id()
    state: ResumePolishState = {
        "session_id": session_id,
        "jd_text": payload["jd_text"],
        "personal_stack": payload["personal_stack"],
        "target_level": payload.get("target_level", "中级"),
        "human_constraints": payload.get("human_constraints", {}),
        "attack_human_decision": payload.get("attack_human_decision", {}),
        "iteration_round": 0,
        "iteration_history": [],
        "logs": [],
        "errors": [],
    }
    result = build_resume_polish_graph().invoke(state, config=graph_config(session_id))
    return format_graph_response(session_id, result)


def resume_hitl_pipeline(session_id: str, resume_value: Dict[str, Any]) -> Dict[str, Any]:
    result = build_resume_polish_graph().invoke(Command(resume=resume_value), config=graph_config(session_id))
    return format_graph_response(session_id, result)


def get_checkpoint_state(session_id: str) -> Dict[str, Any]:
    snapshot = build_resume_polish_graph().get_state(graph_config(session_id))
    return {
        "session_id": session_id,
        "next": list(snapshot.next or []),
        "values": snapshot.values,
        "metadata": snapshot.metadata,
    }


def run_manual_polish(base_state: Dict[str, Any], focus: str, manual_input: str) -> Dict[str, Any]:
    state = {**base_state, "manual_focus": focus, "manual_input": manual_input}
    session_id = state.get("session_id") or new_session_id()
    result = build_manual_polish_graph().invoke(state, config=graph_config(f"{session_id}:manual"))
    save_session(result)
    return result
