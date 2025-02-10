
from .graph_connections import get_workflow
from .redis_implement import RedisSaver


def agent_orchestrator(query: str, thread: str, be_port: str, fe_port: str):
    redis_host = "localhost"
    redis_port = 6379
    redis_db = 0
        
    message = {"query": [query], "fe_port": fe_port, "be_port": be_port}
    config = {"configurable": {"thread_id": thread}}
    
    try:
        with RedisSaver.from_conn_info(host=redis_host, port=redis_port, db=redis_db) as checkpointer:

            # Initialize workflow with checkpointing
            app = get_workflow(checkpointer)
            response = app.invoke(message, config)
            
            # Retrieve checkpoint information
            latest_checkpoint = checkpointer.get(config)
            latest_checkpoint_tuple = checkpointer.get_tuple(config)
            checkpoint_tuples = list(checkpointer.list(config))
            
            # # Print checkpoint info (optional)
            # print(f"Latest checkpoint: {latest_checkpoint}")
            # print(f"Latest checkpoint tuple: {latest_checkpoint_tuple}")
            # print(f"All checkpoint tuples: {checkpoint_tuples}")
            
            # Print response
            if response:
                return [response["backend_code"], response["frontend_code"]]
            else:
                print("No response received.")
    
    except Exception as e:
        print(f"Error: {e}")


