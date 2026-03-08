from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage

from api.agent.graph import build_graph
from api.agent.source_extractor import extract_sources
from api.models.rag import AskRequest, AskResponse
from api.routers.query import get_query_service
from db.code_serarch_layer import CodeSearchService

router = APIRouter()


@router.post("/answer", response_model=AskResponse)
async def answer(
    body: AskRequest,
    query_service: CodeSearchService = Depends(get_query_service),
) -> AskResponse:
    """
    ReAct agent endpoint — reasons over the codebase using Neo4j tools.
    The agent searches, explores, and synthesises a natural-language answer.
    Sources are extracted from tool outputs and returned alongside the answer.
    """
    try:
        agent = build_graph(query_service, repo_id=body.repo_id)
        result = await agent.ainvoke({"messages": [HumanMessage(content=body.question)]})
        messages = result["messages"]
        answer_text = messages[-1].content
        sources = extract_sources(messages)
        return AskResponse(answer=answer_text, sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
