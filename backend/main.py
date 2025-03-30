from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
import sqlite3
import time
import threading
import queue
import pandas as pd
import json
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI()

# CORS Middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup (SQLite)
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY, 
                    status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales_data (
                    id INTEGER PRIMARY KEY, 
                    task_id INTEGER,
                    company TEXT,
                    car_model TEXT,
                    date_of_sale TEXT,
                    price REAL)''')
    conn.commit()
    conn.close()

init_db()

# TaskRequest model to validate task creation data
class TaskRequest(BaseModel):
    start_date: str
    end_date: str
    brands: list

# Task creation and processing logic
task_queue = queue.Queue()
tasks = {}

def process_task(task_id, start_date, end_date, brands):
    time.sleep(5)  # Simulated delay
    tasks[task_id] = "In Progress"

    # Load JSON and CSV data
    with open("data.json") as f:
        json_data = json.load(f)
    json_df = pd.DataFrame(json_data)
    csv_df = pd.read_csv("data.csv")

    # Merge datasets and filter by date and brand
    combined_df = pd.concat([json_df, csv_df])
    combined_df = combined_df[(combined_df["date_of_sale"] >= start_date) & (combined_df["date_of_sale"] <= end_date)]
    combined_df = combined_df[combined_df["company"].isin(brands)]

    # Add task_id column before saving to database
    combined_df["task_id"] = task_id

    conn = sqlite3.connect("database.db")
    combined_df.to_sql("sales_data", conn, if_exists="append", index=False)
    conn.close()

    tasks[task_id] = "Completed"

def task_worker():
    while True:
        task_id, start_date, end_date, brands = task_queue.get()
        process_task(task_id, start_date, end_date, brands)
        task_queue.task_done()

task_thread = threading.Thread(target=task_worker, daemon=True)
task_thread.start()

# Task Creation - Open to all
@app.post("/tasks")
def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    task_id = len(tasks) + 1
    tasks[task_id] = "Pending"
    task_queue.put((task_id, request.start_date, request.end_date, request.brands))
    return {"task_id": task_id, "status": "Pending"}

# Task listing - Open to all
@app.get("/tasks")
def get_tasks():
    return tasks

# Task Data Retrieval - Open to all (No authentication required)
@app.get("/tasks/{task_id}")
def get_task_data(task_id: int):
    conn = sqlite3.connect("database.db")
    df = pd.read_sql_query(f"SELECT * FROM sales_data WHERE task_id={task_id}", conn)
    conn.close()
    return df.to_dict(orient="records")
