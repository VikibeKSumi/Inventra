import os
from uuid import uuid4
import logging
from rich.logging import RichHandler
from datetime import datetime, timezone
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row

from workflow.workflow import InventraGraph
from config.config import config
from capabilities.capabilities import CapabilityService
from capabilities.repository.sqlite_repository import SQLiteRepository
from capabilities.repository.clock import Clock

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s %(message)s",
    handlers=[RichHandler()]
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":

    try:
        logger.info("Inventra loading...")
        LLM_MODEL_NAME = config.llm_model_name
        DB_PATH = config.db_path
        CHECKPOINT_DB_PATH = os.getenv("DATABASE_URL", config.checkpoint_path)
        
        llm = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=LLM_MODEL_NAME
        )
        sql_repository = SQLiteRepository(
            db_path=DB_PATH
        )
        clock = Clock(
            as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)
        )

        service = CapabilityService(
            repository=sql_repository,
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

        while True:
            user_input = input("Enter a query: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                break
        
            print(f"Query:\n{user_input}")

            initial_state = {
                "messages": [
                    HumanMessage(content=user_input)
                ]}
            thread_id = uuid4().hex
            print("THREAD ID: ", thread_id)
            graph_config = {"configurable": {"thread_id": thread_id}}

            response = graph.invoke(
                input=initial_state,
                config=graph_config
            )

            while "__interrupt__" in response:
                payload = response["__interrupt__"][0].value

                if "question" in payload:
                    resume = {
                        "answer": input(f"{payload.get('question')}")
                    }
                else:
                    resume = {
                        "decision": input(f"""
                            The Proposal:\n                            
                            {payload.get('proposal')}\n\n
                            The Details:\n
                            {payload.get("details")}\n\n
                            Next Decision:\n
                            {payload.get('options')}
                        """),
                        "approver": input("Give the name of approver."),
                        "comment": ""
                    }
                response = graph.invoke(
                    input=Command(resume=resume),
                    config=graph_config 
                )
            print("Response: ")
            print(f"terminal_reason: {response.get('terminal_reason')}")
            print(f"replenishment_proposal: {response.get('replenishment_proposal')}")
            print(f"inventory_explanation: {response.get('inventory_explanation')}")
            print("-"*80)

    except Exception as e:
        logger.exception(f"{e}")


