from typing import List
from pydantic import BaseModel, Field
from .state import AgentState
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import os
from langchain_core.output_parsers import PydanticOutputParser
from .utils import parse_markdown_to_plaintext
from dotenv import load_dotenv


load_dotenv()

from langgraph.prebuilt import ToolNode
 
class SystemPlanner(BaseModel):
    planner_result: str = Field(
        description="Lays out a proper plan for the building the application. Returns string."
    )

 

 
class SystemPlanner(BaseModel):
    planner_result: str = Field(
        description="Lays out a proper plan for the building the application. Returns string."
    )
 
def system_planner(state: AgentState)->AgentState:
    """This lays out the foundation for building the application"""
    print("Entering system planner")
    query=state["query"][-1]
    # state["counter"]+=1
    
    system = """
        You are a **FastAPI and Next.js expert developer**. Your job is to create a step-by-step plan to generate code based on the user's query. You **do not write code** and only provide structured planning as a **Senior Engineer**.
       
        The plan should include:
            1. Analyzing the user's requirements in detail.
            2. Identifying key components required to build the application, breaking down the task into steps.
            3. Listing relevant FastAPI backend and Next.js frontend files that need modifications.
            4. Specifying backend FastAPI APIs and database interactions.
            5. Listing frontend Next.js UI components, API integrations, and navigation changes.
            6. Specifying dependencies, commands, and best practices.
            7. Providing a high-level sequence of execution steps.
        """
    human=f"Question: {query}"
    prompt=ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human)
        ]
    )
    llm=ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm=llm.with_structured_output(SystemPlanner)
    planner=prompt | structured_llm
    planner_agent_answer=planner.invoke({})
    # print("planner_result", planner_agent_answer)
    print("planner agent execution completed")
    state["planner_result"]=planner_agent_answer

    return state
 
class CodeArchitect(BaseModel):
    coding_tasks: str = Field(description="A detailed description of the coding tasks to be done for building the application asked by the user")
 
 
 
 
class BECodeArchitectResponse(BaseModel):
    # code_architect_backend_answer: str = Field (description = "Returns the tasks to be carried out by the backend coder")
    APIs: str = Field (description="Returns the APIs of needed ")
    Databases: str = Field (description="Returns schemas of the tables involved")
    ServerSideLogic: str = Field (description="Returns Business logic, data validation, error handling")
    BestPracticesAndExtras: str
    # Dockerfile: str
   
 
def code_architect_backend(state: AgentState):
    print("enterning code_architect_backend")
    plan=state["planner_result"]
    plan=str(plan)
    parser = PydanticOutputParser(pydantic_object=BECodeArchitectResponse)
    system = """
    You are a **FastAPI Backend Developer**. Your task is to analyze the provided system plan and provide a detailed backend architecture using FastAPI.
   
    Please structure your response as follows:
        1. **APIs**: List all endpoints, request/response schemas, and necessary headers.
        2. **Databases**: Define database schema, table relationships, and necessary indexes.
        3. **Server-Side Logic**: Outline business logic, error handling, authentication, and data validation strategies.
        4. **Best Practices**: Logging, security, caching, and performance optimizations.

 
    They system planner output is {plan}
    Please provide a concise yet detailed explanation for each point.
    Focus on clarity, completeness, and best practices.

   
    """
    human="Plan: {plan}"
    prompt=ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human)
        ]
    ).partial(format_instructions=parser.get_format_instructions())
 
    llm=ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm=llm.with_structured_output(BECodeArchitectResponse)
    be_planner=prompt | structured_llm
    be_planner_agent_answer=be_planner.invoke({"input": "Generate the backend code architecture as per the given plan", "plan":plan})
    # print("be_planner_agent_answer", be_planner_agent_answer)
    state["code_architect_backend_answer"]=be_planner_agent_answer
    print("be code architect agent execution completed")    
    return state
 
 
class BEPlannerAnswer(BaseModel):
    APIs: str
    Databases: str
    ServerSideLogic: str
    BestPracticesAndExtras: str
 
from langchain_core.output_parsers import StrOutputParser
 
def custom_cleaned_planner_answer(be_planner_agent_answer: BEPlannerAnswer) -> dict:
    return {
        "APIs": parse_markdown_to_plaintext(be_planner_agent_answer.APIs),
        "Databases": parse_markdown_to_plaintext(be_planner_agent_answer.Databases),
        "ServerSideLogic": parse_markdown_to_plaintext(be_planner_agent_answer.ServerSideLogic),
        "BestPracticesAndExtras": parse_markdown_to_plaintext(be_planner_agent_answer.BestPracticesAndExtras)
    }
 
# Define the backend response structure
class BECode(BaseModel):
    file_path: str = Field(..., description="Path to the file in the backend or frontend structure.")
    file_content: str = Field(..., description="Content of the file.")
 
class BECodeResponse(BaseModel):
    response : List[BECode]
 
 
# Define the frontend response structure
class FrontendCode(BaseModel):
    file_path: str = Field(..., description="Path to the file in the backend or frontend structure.")
    file_content: str = Field(..., description="Content of the file.")
 
class FrontendCodeResponse(BaseModel):
    response : List[FrontendCode]
 
 
def generate_backend_code(state: AgentState) -> AgentState:
    print("Entering generate_backend_code")
 
    raw_answer = state["code_architect_backend_answer"]
    cleaned = custom_cleaned_planner_answer(raw_answer)
    backend_tasks_str = " , ".join(str(value) for value in cleaned.values())
    be_port=state["be_port"]
 
    system = """
        You are a **FastAPI Backend Developer** responsible for enhancing and maintaining an existing FastAPI backend service.

        ### **Context**
        You are inside the `/app` directory, which serves as the main backend directory. The current project structure is as follows:
        /app 
        ├── main.py # Main FastAPI application entry point 
        ├── prestart.sh # Startup script for pre-initialization tasks
        
        ### **Instructions**
        - **Do not create another `/app` directory**; all files should be placed directly inside this existing structure.
        - Implement modular services, database models, and API endpoints **inside `/app`**.
        - Ensure API routes are structured and organized.
        - Follow best practices for **security, validation, logging, and maintainability**.
        - Add a proper `requirements.txt` file for dependencies.
        - The backend service should run on port `{be_port}`.
        - Implement the given backend tasks: `{backend_tasks_str}`.

        ### **Guidelines**
        - **Modify `main.py` if necessary**, but it must remain the primary entry point.
        - Organize API routes and business logic in a structured manner.
        - If necessary, create additional directories inside `/app` for services, models, or utilities.
        - Ensure a scalable and maintainable backend architecture.

    """
 
    human = "Generate a backend code structure for the given tasks: {backend_tasks_str}"
 
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
 
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(BECodeResponse)
 
    backend_code_agent = prompt | structured_llm
    backend_code_answer = backend_code_agent.invoke({"backend_tasks_str": backend_tasks_str, "be_port":be_port})
 
    state["backend_code"] = backend_code_answer.dict()
     
 
    print("Backend code generation completed")
    return state
 
 
class FECodeArchitectResponse(BaseModel):
    frontend_tasks: str
 
 
class FECodeArchitectResponse(BaseModel):
    """Defines the structured response for frontend tasks."""
    frontend_tasks: str = Field(..., description="List of frontend tasks needed")
 
def code_architect_frontend(state: AgentState)-> AgentState:
    """
    This function provides a detailed list of frontend tasks to be undertaken
    based on the planner's output (query) and the backend plan (be_plan).
    """
    print("entering code architect fe")
 
    # 1. Extract data from state
    query = state["planner_result"]
    be_plan = state["code_architect_backend_answer"]
 
    # 2. Create a Pydantic parser for the FECodeArchitectResponse
    parser = PydanticOutputParser(pydantic_object=FECodeArchitectResponse)
 
    # 3. Construct the system and human messages, embedding the necessary text
    system = """
    You are a **Next.js Frontend Developer**. Your job is to analyze the system plan and backend architecture to generate a detailed list of frontend tasks.
    - Identify necessary UI components and layouts.
    - Determine API integrations and state management.
    - Define necessary form validations, authentication flows, and routing.
    - Ensure best practices in responsiveness, performance, and accessibility.
 
    ---
    System Planner's Output (Query): {query}
 
    Backend Plan: {be_plan}
    ---
 
    Now, please specify all required frontend functionalities, pages, components,
    integrations, validations, and any other UI/UX elements needed.
    Be specific in your explanation.
 
    The output should be in markdown format.
    """
 
    human = "Please outline the frontend tasks in detail."
 
    # 4. Build a ChatPromptTemplate
    prompt = (
        ChatPromptTemplate
        .from_messages([("system", system), ("human", human)])
        .partial(format_instructions=parser.get_format_instructions())
    )
 
    # 5. Create the model and link it to the Pydantic structured output
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(FECodeArchitectResponse)
 
    # 6. Pipe the prompt into the structured LLM
    fe_planner_agent = prompt | structured_llm
 
    # 7. Invoke with a single dictionary argument to satisfy the “input” key
    code_architect_frontend_answer = fe_planner_agent.invoke({
        "query": query, "be_plan":be_plan
    })
 
    # 8. Store the result in state
    state["code_architect_frontend_answer"] = code_architect_frontend_answer.frontend_tasks
 
    print("code_architect_frontend completed")
    return state

class DockerCompose(BaseModel):
    docker_compose : str


def generate_docker_compose(state: AgentState) -> AgentState:
    print("Generating Docker Compose file...")

    backend_code = state["backend_code"]
    frontend_code = state["frontend_code"]
    
    be_port = state["be_port"]
    fe_port = state["fe_port"]
    
    thread_id = state["thread_id"]

    
    system_prompt = """
    You are a skilled DevOps engineer. Your task is to generate a valid `docker-compose.yml` file 
    for a full-stack application based on the provided frontend and backend code.

    **Instructions:**
    - The backend is a FastAPI application.
    - The frontend is a Next.js application.
    - The backend should run on port `{be_port}`.
    - The frontend should run on port `{fe_port}`.
    - Ensure both services are connected in the same Docker network.
    - Use `depends_on` to ensure the frontend starts after the backend.
    - Optimize the Docker Compose file for **local development**.
    - Ensure correct **environment variables** and **volume mounting**.
    
    **Backend Code:** {backend_code}
    **Frontend Code:** {frontend_code}
    """

    human_prompt = "Generate a valid `docker-compose.yml` file for the full-stack application."

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_prompt)])

    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(DockerCompose)

    docker_compose_agent = prompt | structured_llm
    docker_compose_answer = docker_compose_agent.invoke({
        "backend_code": backend_code, 
        "frontend_code": frontend_code,
        "be_port": be_port,
        "fe_port": fe_port
    })

    docker_compose_path = os.path.join(thread_id, "docker-compose.yml")

    os.makedirs(os.path.dirname(docker_compose_path), exist_ok=True)
    with open(docker_compose_path, "w", encoding="utf-8") as file:
        file.write(docker_compose_answer.docker_compose)

    print(f"✅ Docker Compose file saved at: {docker_compose_path}")
    return state


def generate_frontend_code(state: AgentState) -> AgentState:
    print("Entering frontend code generator")
 
    frontend_tasks = str(state["code_architect_frontend_answer"])
    backend_tasks = str(state["code_architect_backend_answer"])
    backend_code=str(state["backend_code"])
    fe_port=state["fe_port"]
 
    system = """
    You are a highly skilled frontend engineer dealing in Next.js tech stack. Your task is to generate a structured 
    frontend codebase for the frontend given requirements/tasks and the backend code.
    The frontend tasks are: {frontend_tasks}
    The backend code is: {backend_code}
    You are inside the `/frontend` directory of a Next.js project with the following structure:

    /frontend
    ├── src
    │   ├── app
    │   │   ├── page.js  # Main index page
    │   │   ├── layout.js
    │   │   ├── globals.css
    │   ├── components  # UI components
    │   ├── hooks  # Custom React hooks
    │   ├── lib  # API utilities and helpers
    │   ├── styles  # TailwindCSS styles
    
    **Instructions:**
    - Place new UI components in `src/components/`.
    - API integrations should go in `src/lib/`.
    - Modify `src/app/page.js` if needed.
    - Follow best practices for Next.js and TailwindCSS.
    - Assume you are inside `/frontend`.
    - Ensure best practices for responsive design, performance, and maintainability.
    - The frontend port is {fe_port}
    """
 
    human = "Generate a frontend code structure for the given tasks."
 
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
 
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(FrontendCodeResponse)
 
    frontend_code_agent = prompt | structured_llm
    frontend_code_answer = frontend_code_agent.invoke({"frontend_tasks": frontend_tasks, "backend_code":backend_code, "fe_port":fe_port})
 
    state["frontend_code"] = frontend_code_answer.dict()
    print("Frontend code generation completed")
    return state



#------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------

# class ChangeTask(BaseModel):
#     file: str  # File name where the change is needed
#     description: str  # Description of the change
 
# class ChangePlannerResponse(BaseModel):
#     tasks: List[ChangeTask]  # List of tasks with file names and descriptions
 
# def change_planner(state: AgentState):
#     """Identifies necessary tasks for modifications"""
#     print("Executing Change Planner...")
 
#     if "user_query" not in state or not state["user_query"]:
#         raise KeyError("Missing 'user_query' in state. Please provide a valid user request.")
 
#     system_prompt = """
#     You are a senior full-stack engineer. A user has requested modifications to an existing codebase.
 
#     - Analyze the provided frontend and backend code.
#     - Identify which files need to be completely replaced instead of modifying sections.
#     - List tasks separately for each file that needs to be rewritten.
#     - Ensure each task is structured clearly and concisely.
#     """
 
#     user_prompt = """
#     Existing Frontend Code:
#     {frontend_code}
 
#     Existing Backend Code:
#     {backend_code}
 
#     User Requested Change:
#     {user_query}
 
#     Instructions:
#     - If a file requires modification, assume the entire file will be replaced with a new version.
#     - Only list files where changes are required.
#     """
 
 
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", system_prompt),
#         ("human", user_prompt)
#     ])
 
#     llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
#     structured_llm = llm.with_structured_output(ChangePlannerResponse)
 
    # planner_agent = prompt | structured_llm
    # planner_response = planner_agent.invoke({
    #     "frontend_code": state["frontend_code"],
    #     "backend_code": state["backend_code"],
    #     "user_query": state["user_query"]
    # })
 
    # if not planner_response.tasks:
    #     raise ValueError("Change Planner did not return any tasks. Check the input format or LLM response.")
 
    # state["change_tasks"] = planner_response.tasks
    # print("Change Planner Completed:", planner_response.tasks)
    # return state
 

class ChangesAnalyzed(BaseModel):
    ScopeofChange: str  
    TechnicalBreakdown: str 
    Dependencies:str
    ActionableTasks:str



def change_analyzer(state:AgentState):
    print("Executing Change Analyzer...")
    user_query=state["query"][-1]

    
    system_prompt="""

    You are a senior full-stack developer responsible for analyzing user queries related to modifying an existing application's frontend (FE) and backend (BE) code. 
    The user's query describes the required changes or improvements. Your task is to break down the query, explore its implications, and extract precise details necessary to generate actionable modifications.
    User query: {user_query}

    Step 1: Self-Search Expansion of the User Query
    Given the user's query:
    1.Identify keywords and phrases that indicate the specific modifications required.
    2.Determine whether the requested changes impact the frontend, backend, or both.
    3.Analyze if any new functionalities, UI updates, API modifications, or database changes are involved.
    4.Clarify any implicit requirements the user might not have explicitly mentioned but are necessary for implementing the change.

    Step 2: Breaking Down the Query into Subtasks
    1.List the individual tasks or components that need to be modified.
    2.If the query involves UI changes, identify which frontend files, components, or stylesheets are affected.
    3.If the query involves backend logic or APIs, determine which endpoints, database models, or authentication flows are impacted.
    4.Specify dependencies between frontend and backend changes, ensuring a consistent user experience.

    Step 3: Asking Clarifying Questions (Self-Reflection)
    To ensure completeness, ask self-directed questions such as:

    1.Functional Changes: Does the query require adding, modifying, or removing existing functionality?
    2.User Interaction: Does it affect how users interact with the frontend (e.g., forms, buttons, modals, navigation)?
    3.Data Flow: Are there changes needed in API requests/responses, database schema, or data validation?
    4.Performance & Security: Are there any implications for performance optimization or security enhancements?
    5.Integration: Does it involve third-party services, authentication, or real-time updates?

    On the basis of the above, output  a Well-Structured Analysis
    After breaking down and analyzing the user query, generate a structured output containing:

    1.Scope of Change: A summary of whether the change is frontend, backend, or full-stack.
    2.Technical Breakdown: A list of functionalities and/or modules.
    3.Dependencies: Any related components that need adjustments.
    4.Actionable Tasks: Clearly defined steps to implement the changes.
    """
    user_prompt="""Analyze the changes needed based on the user query"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_prompt)
    ])
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(ChangesAnalyzed)
    analyzer_agent = prompt | structured_llm
    analyzer_response = analyzer_agent.invoke({"user_query": user_query})
 
    if not analyzer_response:
        raise ValueError("Change Planner did not return any tasks. Check the input format or LLM response.")
    analyzer_response=analyzer_response.ActionableTasks
    state["changes_analyzed"] = analyzer_response
    print("Change Planner Completed:", analyzer_response)
    return state



# ============================
# STEP 2: BE CHANGE PLANNER
# ============================

class UnitChangeDetail(BaseModel):
    File_path: str
    change: str


class ChangeDetail(BaseModel):
    changes : List[UnitChangeDetail]
 

 
def change_planner_be(state: AgentState):
    print("Executing Change planner...")
    backend_code=state["backend_code"]
    changes_analyzed=state["changes_analyzed"]
    system_prompt = """
    You are a senior backend engineer proficient in the FastAPI framework. Your task is to analyze the modification 
    query carefully and determine the exact functionality changes needed.

    ### **Backend Code Context:**
    The backend code you have is:
    {backend_code}

    ### **Task:**
    1. Extract relevant backend modules/functions from the backend code that align with the requested improvements.
    2. Identify files related to:
        - **API Endpoints** (Controllers, Routers)
        - **Business Logic** (Service Layer, Helper Functions)
        - **Database Models** (Schema Updates, Migrations)
        - **Configuration & Environment Variables**


    ### **For Each File Path, Provide:**
    - **What needs to be modified?**
    - **Why is this change required?**
    - **Are there dependencies on other files or modules?**
    - **Any new logic, API, or security enhancements needed?**
        """
 
    user_prompt = """
    The modification query is {changes_analyzed}. Give a revised BE code.
    """
 
 
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", user_prompt)])
 
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(ChangeDetail)
 
    identifier_agent = prompt | structured_llm
    identifier_response = identifier_agent.invoke({
        "backend_code":backend_code,
        "changes_analyzed":changes_analyzed

    })
 
 
    state["change_details_be"] = identifier_response
    print("Change Identifier Completed: __", state["change_details_be"])
   
    return state
 
 
# ============================
# STEP 3: BE CODE GENERATOR
# ============================
 



def regenerate_backend_code(state:AgentState) -> AgentState: 
    print("Entering regenerate_backend_code...")

    backend_code = state["backend_code"]  # Extract list of files with their paths and content
    print("type of backend_code", type(backend_code))

    print("change_details_be", state["change_details_be"])

    change_details_be = state["change_details_be"]

    print("type of change_details_be", type(change_details_be))

    backend_code = str(state["backend_code"])  # Extract list of files with their paths and contents
    change_details_be = str(state["change_details_be"])

    system_prompt = """
    You are a ** Senior FastAPI Backend Developer**. Your task is to update the existing backend code based on the 
    requested modifications.

    ### **Existing Backend Code Context:**
    The current backend files and their content are provided.

    {backend_code}

    ### **Modification Instructions:**
    - Update only the specified files in `change_details_be`.
    - Preserve all existing structure, imports, and formatting.
    - Ensure the modified code remains functional, secure, and scalable.
    - Do not alter files that are not listed in `change_details_be`.

    ### **Change Details:**
    {change_details_be}


    """

    user_prompt = """
    Update the following backend files based on the provided change details.
    """

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", user_prompt)])

    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(BECodeResponse)

    regenerator_agent = prompt | structured_llm
    updated_backend_code_response = regenerator_agent.invoke({
        "backend_code": backend_code,
        "change_details_be": change_details_be
    })

    print("Backend Code Regeneration Completed.")
    state["backend_code"]=updated_backend_code_response.dict()
    # Returning the updated backend code as a dictionary
    return state


# ============================
# STEP 4: FE CHANGE PLANNER
# ============================


def change_planner_fe(state: AgentState)->AgentState:
    print("Executing Change Planner for Frontend...")

    frontend_code = state["frontend_code"]
    changes_analyzed = state["changes_analyzed"]

    system_prompt = """
    You are a senior frontend engineer proficient in the Next.js framework. Your task is to analyze the modification 
    query carefully and determine the exact functionality changes needed.

    ### **Frontend Code Context:**
    The frontend code you have is:
    {frontend_code}

    ### **Task:**
    1. Extract relevant frontend components/pages/hooks from the frontend code that align with the requested improvements.
    2. Identify files related to:
        - **Pages (`pages/` directory)**
        - **Components (`components/` directory)**
        - **API Routes (`pages/api/` directory, if applicable)**
        - **State Management (Context API, Redux, Zustand, or React Query)**
        - **Styling (CSS Modules, Tailwind, SCSS, or Styled Components)**
        - **Routing (`next/router` or `app/router` if using Next.js App Router)**
        - **Server-Side Functions (if using `getServerSideProps`, `getStaticProps`, or `app/server`)**

    ### **Output Format:** 
    Return a dictionary where:
    - **Keys** → File paths that need modification.
    - **Values** → A detailed description of the required changes.

    ### **For Each File Path, Provide:**
    - **What needs to be modified?**
    - **Why is this change required?**
    - **Are there dependencies on other files, APIs, or components?**
    - **Any new UI elements, API calls, or optimizations needed?**

    Ensure that:
    - The code remains optimized for Next.js best practices.
    - Any client-side data fetching (`useEffect`, `fetch`, `SWR`) or SSR (`getServerSideProps`) is correctly handled.
    - Maintain UI consistency and accessibility (a11y).
    """

    user_prompt = """
    The modification query is {changes_analyzed}. Give a revised FE code.
    """

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", user_prompt)])

    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(ChangeDetail)

    identifier_agent = prompt | structured_llm
    identifier_response = identifier_agent.invoke({
        "frontend_code": frontend_code,
        "changes_analyzed": changes_analyzed
    })

    state["change_details_fe"] = identifier_response
    print("Frontend Change Identifier Completed:", identifier_response)

    return state


# ============================
# STEP 5: FE CODE GENERATOR
# ============================

def regenerate_frontend_code(state: AgentState) -> AgentState:
    print("Entering Frontend Code Regenerator...")

    frontend_code = state["frontend_code"]["response"]  # Extract list of existing frontend files
    change_details_fe = state["change_details_fe"]  # Extract required modifications

    system_prompt = """
    You are a highly skilled Next.js frontend engineer. Your task is to update the existing frontend codebase based on the requested modifications.

    ### **Existing Frontend Code Context:**
    The current frontend files and their content are provided.

    {frontend_code}

    ### **Modification Instructions:**
    - Modify only the specified files in `change_details_fe`.
    - Ensure that the updated code follows Next.js best practices.
    - Maintain proper API integration, state management, and UI consistency.
    - Preserve Tailwind CSS, CSS Modules, or SCSS styles if used.
    - Avoid breaking TypeScript/JSX syntax and ensure imports remain correct.

    ### **Change Details:**
    {change_details_fe}

    ### **Output Format:**
    Return an updated list of frontend files with modified content.
    """

    user_prompt = """
    Update the following frontend files based on the provided change details
    """

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", user_prompt)])

    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    structured_llm = llm.with_structured_output(FrontendCodeResponse)

    regenerator_agent = prompt | structured_llm
    updated_frontend_code_response = regenerator_agent.invoke({
        "frontend_code": frontend_code,
        "change_details_fe": change_details_fe
    })

    print("Frontend Code Regeneration Completed.")

    # Updating frontend_code in state with modified files
    state["frontend_code"] = updated_frontend_code_response.dict()
    
    return state