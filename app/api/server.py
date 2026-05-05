from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import get_checkpoint_state, resume_hitl_pipeline, run_full_pipeline, run_manual_polish, start_hitl_pipeline
from app.core.config import settings
from app.services.json_memory import list_sessions, load_session
from app.services.technical_doc_rag import search_technical_doc
from app.services.vector_store import vector_store
from scripts.ingest_rag import load_documents


class PipelineRunRequest(BaseModel):
    jd_text: str = Field(..., min_length=1, description="目标岗位 JD")
    personal_stack: str = Field(..., min_length=1, description="候选人技术栈")
    target_level: str = Field("中级", description="目标职级")
    human_constraints: Dict[str, Any] = Field(default_factory=dict, description="开局人工约束")
    attack_human_decision: Dict[str, Any] = Field(default_factory=dict, description="攻防阶段人工决策")
    session_id: Optional[str] = Field(default=None, description="可选会话 ID")


class PipelineResumeRequest(BaseModel):
    session_id: str = Field(..., description="LangGraph checkpoint thread_id")
    resume_value: Dict[str, Any] = Field(..., description="传给 interrupt 的恢复值")


class ManualPolishRequest(BaseModel):
    session_id: str = Field(..., description="基于哪个历史会话做单点补打磨")
    focus: str = Field(..., description="架构/性能/线上故障/部署运维/团队协作")
    manual_input: str = Field("", description="用户补充的真实经历或强化要求")


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=20)


class TechnicalDocSearchRequest(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    query: str = Field(..., min_length=1, description="技术文档检索问题")
    limit: int = Field(5, ge=1, le=20)


app = FastAPI(
    title=settings.app_name,
    description="不依赖 Streamlit 的 Multi-Agent 简历项目闭环打磨 HTTP API",
    version="0.1.0",
)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "rag": vector_store.health(),
    }


@app.post("/api/v1/pipeline/run")
def run_pipeline(request: PipelineRunRequest) -> Dict[str, Any]:
    try:
        state = run_full_pipeline(request.model_dump(exclude_none=True))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent 流程执行失败: {type(exc).__name__}: {exc}") from exc
    if "__interrupt__" in state:
        return {
            "status": "interrupted",
            "session_id": state.get("session_id") or request.session_id,
            "interrupts": [getattr(item, "value", item) for item in state.get("__interrupt__", [])],
        }
    return {
        "status": "completed",
        "session_id": state.get("session_id"),
        "iteration_round": state.get("iteration_round"),
        "rag_context": state.get("rag_context", []),
        "final_output": state.get("final_output", {}),
        "logs": state.get("logs", []),
    }


@app.post("/api/v1/pipeline/start-hitl")
def start_pipeline_hitl(request: PipelineRunRequest) -> Dict[str, Any]:
    try:
        return start_hitl_pipeline(request.model_dump(exclude_none=True))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HITL 流程启动失败: {type(exc).__name__}: {exc}") from exc


@app.post("/api/v1/pipeline/resume")
def resume_pipeline_hitl(request: PipelineResumeRequest) -> Dict[str, Any]:
    try:
        return resume_hitl_pipeline(request.session_id, request.resume_value)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HITL 流程恢复失败: {type(exc).__name__}: {exc}") from exc


@app.get("/api/v1/pipeline/checkpoints/{session_id}")
def pipeline_checkpoint(session_id: str) -> Dict[str, Any]:
    try:
        return get_checkpoint_state(session_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"checkpoint 不存在或已过期: {type(exc).__name__}: {exc}") from exc


@app.post("/api/v1/manual-polish")
def manual_polish(request: ManualPolishRequest) -> Dict[str, Any]:
    try:
        base_state = load_session(request.session_id)
        state = run_manual_polish(base_state, request.focus, request.manual_input)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"补打磨失败: {type(exc).__name__}: {exc}") from exc
    return {
        "session_id": state.get("session_id"),
        "manual_polish_output": state.get("manual_polish_output", {}),
        "logs": state.get("logs", []),
    }


@app.get("/api/v1/sessions")
def sessions() -> List[Dict[str, str]]:
    return list_sessions()


@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str) -> Dict[str, Any]:
    try:
        return load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/rag/search")
def rag_search(request: RagSearchRequest) -> Dict[str, Any]:
    return {"query": request.query, "hits": vector_store.search(request.query, limit=request.limit)}


@app.post("/api/v1/technical-doc/search")
def technical_doc_search(request: TechnicalDocSearchRequest) -> Dict[str, Any]:
    try:
        state = load_session(request.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    technical_doc = state.get("technical_doc", {})
    return {
        "session_id": request.session_id,
        "query": request.query,
        "technical_doc_version": technical_doc.get("version"),
        "hits": search_technical_doc(request.query, request.session_id, technical_doc, limit=request.limit),
    }


@app.get("/api/v1/rag/health")
def rag_health() -> Dict[str, Any]:
    return vector_store.health()


@app.post("/api/v1/rag/ingest")
def rag_ingest() -> Dict[str, Any]:
    try:
        docs = load_documents()
        inserted = vector_store.insert_documents(docs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG 入库失败: {type(exc).__name__}: {exc}") from exc
    return {"status": "ok", "loaded_chunks": len(docs), "inserted_chunks": inserted, "rag": vector_store.health()}
