from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict


AgentName = Literal[
    "jd_parser",
    "human_scope_gate",
    "architecture_cocreation",
    "technical_doc_builder",
    "resume_packaging",
    "senior_interviewer",
    "human_attack_gate",
    "iteration_repair",
    "technical_doc_updater",
    "compliance_risk",
]


class ResumePolishState(TypedDict, total=False):
    """LangGraph 全局状态，所有 Agent 都只读写这份结构化上下文。"""

    session_id: str
    jd_text: str
    personal_stack: str
    target_level: str
    human_constraints: Dict[str, Any]
    attack_human_decision: Dict[str, Any]

    jd_profile: Dict[str, Any]
    rag_context: List[Dict[str, Any]]
    project_blueprint: Dict[str, Any]
    technical_doc: Dict[str, Any]
    technical_doc_history: Annotated[List[Dict[str, Any]], operator.add]
    technical_doc_rag_hits: List[Dict[str, Any]]
    resume_package: Dict[str, Any]
    attack_report: Dict[str, Any]
    iteration_round: int
    iteration_history: Annotated[List[Dict[str, Any]], operator.add]
    compliance_report: Dict[str, Any]
    final_output: Dict[str, Any]

    manual_focus: Optional[str]
    manual_input: Optional[str]
    manual_polish_output: Dict[str, Any]

    current_agent: AgentName
    logs: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
