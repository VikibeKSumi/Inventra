import os
from dotenv import load_dotenv
from datetime import datetime, timezone
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field 
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row

from config.config import config
from workflow.workflow import InventraGraph
from capabilities.capabilities import CapabilityService
from capabilities.repository.sqlite_repository import SQLiteRepository
from capabilities.repository.clock import Clock 

load_dotenv()

LLM_MODEL_NAME = config.llm_model_name
DB_PATH = config.db_path
CHECKPOINT_DB_PATH = os.getenv("DATABASE_URL", config.checkpoint_path)

app = FastAPI(title="Inventra assistant")
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    model=LLM_MODEL_NAME
)

repository = SQLiteRepository(
    db_path=DB_PATH
)
clock = Clock(
    as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)
)
service = CapabilityService(
    repository=repository,
    clock=clock,
    config=config
)

conn = Connection.connect(CHECKPOINT_DB_PATH, autocommit=True, row_factory=dict_row)
checkpointer = PostgresSaver(conn)
checkpointer.setup() 

inventra = InventraGraph(
    llm=llm,
    service=service,
    config=config,
    checkpointer=checkpointer
)    
graph = inventra.build_graph()



class ChatRequest(BaseModel):
    user_query: str = Field(description="")
    thread_id: str = Field(description="")

class ClarifyInterrupt(BaseModel):
    question: str = Field(description="")
    thread_id: str = Field(description="")
    interrupt_type: str = "clarify"

class ApproveInterrupt(BaseModel):
    proposal: str = Field(description="")
    details: dict = Field(description="")
    options: list = Field(description="")
    thread_id: str = Field(description="")
    interrupt_type: str = "approve"

class ResumeRequest(BaseModel):
    thread_id : str = Field(description="")
    resume_answer: Optional[str] = Field(default=None, description="")
    decision: Optional[str] = Field(default=None, description="")
    approver: Optional[str] = Field(default=None, description="")
    comment: Optional[str] = Field(default=None, description="")
    interrupt_type: str = Field(description="")

class CaseResult(BaseModel):
    thread_id: str
    terminal_reason: Optional[str] = None
    inventory_status: Optional[str] = None
    inventory_explanation: Optional[str] = None
    replenishment_status: Optional[str] = None
    replenishment_proposal: Optional[str] = None
    purchase_request_id: Optional[str] = None
    decline_reason: Optional[str] = None

@app.get("/")
def health():
    return {
        "status check": "ok"
    }

def to_response(response: dict, thread_id: str):
    if "__interrupt__" in response:
        payload = response["__interrupt__"][0].value
        if "question" in payload:
            return ClarifyInterrupt(
                question=payload.get("question"),
                thread_id=thread_id,
            )
        return ApproveInterrupt(
            proposal=payload.get("proposal"),
            details=payload.get("details"),
            options=payload.get("options"),
            thread_id=thread_id,
        )

    return CaseResult(
        thread_id=thread_id,
        terminal_reason=response.get("terminal_reason"),
        inventory_status=response.get("inventory_status"),
        inventory_explanation=response.get("inventory_explanation"),
        replenishment_status=response.get("replenishment_status"),
        replenishment_proposal=response.get("replenishment_proposal"),
        purchase_request_id=response.get("purchase_request_id"),
        decline_reason=response.get("decline_reason"),
    )


@app.post("/chat")
def chat(request: ChatRequest):
    try: 
        initial_state = {
            "messages": [HumanMessage(content=request.user_query)]
        }

        graph_config = {"configurable": {"thread_id": request.thread_id}}

        response = graph.invoke(input=initial_state, config=graph_config)
        return to_response(response, request.thread_id)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resume")
def resume(request: ResumeRequest):

    try:
        graph_config = {"configurable": {"thread_id": request.thread_id}}
    
        if request.interrupt_type == "clarify":
            resume_payload = {
                "answer": request.resume_answer
            }
        elif request.interrupt_type == "approve":
            resume_payload = {
                "decision": request.decision,
                "approver": request.approver,
                "comment": request.comment
            }
        else:
            raise HTTPException(status_code=400, detail=f"unknown interrupt_type: {request.interrupt_type}")

        response = graph.invoke(input=Command(resume=resume_payload), config=graph_config)
        return to_response(response, request.thread_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))