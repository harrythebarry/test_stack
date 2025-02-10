from typing import List, TypedDict, Annotated
from langchain_core.messages import AnyMessage
import operator
import json
 
from pydantic import BaseModel, Field
 
 
class BECode(BaseModel):
    file_path: str = Field(..., description="Path to the file in the backend or frontend structure.")
    file_content: str = Field(..., description="Content of the file.")
 
class BECodeResponse(BaseModel):
    response : List[BECode]
    dockerfile : str
 
 
# Define the frontend response structure
class FrontendCode(BaseModel):
    file_path: str = Field(..., description="Path to the file in the backend or frontend structure.")
    file_content: str = Field(..., description="Content of the file.")
 
class FrontendCodeResponse(BaseModel):
    response : List[FrontendCode]
    dockerfile : str
 
class UnitChangeDetail(BaseModel):
    File_path: str
    change: str


class ChangeDetail(BaseModel):
    changes : List[UnitChangeDetail]
 
 
class AgentState(TypedDict):
    thread_id:str
    query:Annotated[list[AnyMessage], operator.add]
    changes_analyzed:str
    stack_text: str
    be_task:str
    fe_task:str
    be_port:int
    fe_port:int
    evaluator:str
    planner_result:str
    git_log_text:str
    files_text: str
    code_architect_backend_answer:json
    code_architect_frontend_answer:str
    backend_code:BECodeResponse
    frontend_code:FrontendCodeResponse
    counter: int = Field(default=0, description="Counter for the number of times the system planner has been run.")
    change_details_be: ChangeDetail
    change_details_fe: ChangeDetail
    # backend_routes:List(str)
    


