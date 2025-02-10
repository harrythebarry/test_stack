from .state import AgentState
from .workflow2 import (
    system_planner, code_architect_backend, code_architect_frontend, 
    generate_backend_code, generate_frontend_code, regenerate_backend_code, regenerate_frontend_code, 
    change_analyzer, change_planner_be, change_planner_fe
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph          
from .utils import determine_starting_node


workflow = StateGraph(AgentState)

# Step 1: Ensure 'my_node' is the first node


# Step 2: Add remaining nodes
workflow.add_node("system_planner", system_planner)

workflow.add_node("code_architect_backend", code_architect_backend)
workflow.add_node("code_architect_frontend", code_architect_frontend)

workflow.add_node("generate_backend_code", generate_backend_code)
workflow.add_node("generate_frontend_code", generate_frontend_code)

workflow.add_node("change_analyzer", change_analyzer)

workflow.add_node("change_planner_be", change_planner_be)
workflow.add_node("change_planner_fe", change_planner_fe)

workflow.add_node("regenerate_backend_code", regenerate_backend_code)
workflow.add_node("regenerate_frontend_code", regenerate_frontend_code)


# Step 3: Set 'my_node' as the entry point
# Step 4: Add a conditional edge FROM 'my_node' to determine the second node
workflow.set_conditional_entry_point(
    determine_starting_node,  # This function decides the next step
    {
        "system_planner": "system_planner",
        "change_analyzer": "change_analyzer"
    }
)


# Step 5: Keep the existing edges
workflow.add_edge("system_planner", "code_architect_backend")
workflow.add_edge("code_architect_backend", "generate_backend_code")
workflow.add_edge("generate_backend_code", "code_architect_frontend")
workflow.add_edge("code_architect_frontend", "generate_frontend_code")


workflow.add_edge("change_analyzer", "change_planner_be")
workflow.add_edge("change_planner_be", "regenerate_backend_code")
workflow.add_edge("regenerate_backend_code", "change_planner_fe")
workflow.add_edge("change_planner_fe", "regenerate_frontend_code")





checkpointer = MemorySaver()

# Step 6: Function to get the workflow with a store
def get_workflow(checkpointer):
    app = workflow.compile(checkpointer=checkpointer)
    return app
