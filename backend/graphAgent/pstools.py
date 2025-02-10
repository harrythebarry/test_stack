import os
from langchain_core.tools import tool


def create_files(file_data):
    for item in file_data.get('response', []):
        file_path = item['file_path']
        file_content = item['file_content']
       
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # Write content to file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(file_content)
       
        print(f"File created: {file_path}")

# # Example usage
# data = {
#     "response": [
#         {
#             "file_path": "calculator_app/main.py",
#             "file_content": "from fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n..."
#         },
#         {
#             "file_path": "calculator_app/tests/test_calculator.py",
#             "file_content": "from fastapi.testclient import TestClient\nfrom calculator_app.main import app\n..."
#         },
#         {
#             "file_path": "calculator_app/database.py",
#             "file_content": "import sqlite3\nfrom datetime import datetime\n..."
#         }
#     ]
# }
 
# create_files(data)