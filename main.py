"""
FastAPI main application module.

Before:
    - Ensure that the MySQL server is running on localhost.
    - OpenWeatherMap API key in .env file as API_KEY_OpenWeatherMap

Execute:
    - uvicorn main:app --reload
"""

from fastapi import Request, FastAPI, HTTPException
import mysql.connector
from fastapi.responses import JSONResponse
import os

app = FastAPI()

# -------------------------- #
# -------- HELLO WORLD ----- #
# -------------------------- #

@app.get("/")
def root():
    return {"message": "Hello World!"}

