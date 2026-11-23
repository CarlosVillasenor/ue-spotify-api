"""
FastAPI main application module.

Before:
    - Ensure that the MySQL server is running on localhost.

Execute:
    - uvicorn main:app --reload
"""

from fastapi import Request, FastAPI, HTTPException
import mysql.connector
from fastapi.responses import JSONResponse
from configuration.connections import DatabaseConnection
import os
from configuration.settings import required_env

app = FastAPI()

# -------- HELLO MOM ----- #

@app.get("/")
def root():
    return {"message": "Hello Mom!"}

# -------- USER MANAGEMENT ----- #

@app.get("/users")
async def get_users():
    db = DatabaseConnection(
        host=required_env("databaseHost"),
        user=required_env("databaseUser"),
        password=required_env("databasePassword"),
        database=required_env("databaseName"),
    )

    connection = await db.get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

