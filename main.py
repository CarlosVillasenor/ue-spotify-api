"""
FastAPI main application module.

Before:
    - Ensure that the MySQL server is running on localhost.

Execute:
    - uvicorn main:app --reload --env-file .env
"""

from urllib.parse import urlencode
from fastapi.responses import RedirectResponse
from fastapi import Request, FastAPI, HTTPException, Query
import mysql.connector
from fastapi.responses import JSONResponse
from configuration.connections import DatabaseConnection
import os
from configuration.settings import required_env
from pydantic import BaseModel, Field

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

@app.post("/users")
async def post_user(request: Request):
    # NOTE: Modularized DB connection
    mydb = DatabaseConnection(
        host=required_env("databaseHost"),
        user=required_env("databaseUser"),
        password=required_env("databasePassword"),
        database=required_env("databaseName"),
    )

    mydb_connection = await mydb.get_db_connection()
    mycursor = mydb_connection.cursor()
    data = await request.json()
    username = data["username"]
    age = data["age"]

    mycursor.execute(
        f"INSERT INTO users (username, age) VALUES ('{username}', '{age}');"
    )
    mydb_connection.commit()  # permanently saves the changes
    return JSONResponse(
        content={"message": "User added successfully"},
        status_code=201,
    )

class UserCreate(BaseModel):
    username: str
    age: int = Field(..., ge=0, le=120)

@app.post("/users-validation")
async def post_user_validation(user: UserCreate):
    mydb = DatabaseConnection(
        host=required_env("databaseHost"),
        user=required_env("databaseUser"),
        password=required_env("databasePassword"),
        database=required_env("databaseName"),
    )
    mydb_connection = await mydb.get_db_connection()
    mycursor = mydb_connection.cursor()  # multiple requests cannot share the same cursor simultaneously
    username = user.username
    age = user.age
    mycursor.execute(f'INSERT INTO `users`(username, age) VALUES ("{username}",{age});')
    mydb_connection.commit()
    return JSONResponse(content={"message": "User added successfully"}, status_code=201)


@app.put("/users/{user_id}")
async def update_user(user_id: int, request: Request):
    mydb = DatabaseConnection(
        host=required_env("databaseHost"),
        user=required_env("databaseUser"),
        password=required_env("databasePassword"),
        database=required_env("databaseName"),
    )
    mydb_connection = await mydb.get_db_connection()
    mycursor = mydb_connection.cursor()
    data = await request.json()
    username = data.get("username")
    age = data.get("age")
    update_fields = []
    if username:
        update_fields.append(f'username="{username}"')
    if age:
        update_fields.append(f"age={age}")
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_query = f'UPDATE `users` SET {", ".join(update_fields)} WHERE id={user_id};'
    mycursor.execute(update_query)
    mydb_connection.commit()
    if mycursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return JSONResponse(
        content={"message": "User updated successfully"}, status_code=200
    )

#-------- SPOTIFY MANAGEMENT ----- #

@app.get("/login")
async def login():
    params = {
        "response_type": "code",
        "client_id": required_env("SPOTIFY_CLIENT_ID"),
        "scope": "user-read-private user-read-email",
        "redirect_uri": required_env("SPOTIFY_REDIRECT_URI"),
    }

    spotify_url = (
        "https://accounts.spotify.com/authorize?"
        + urlencode(params)
    )

    return RedirectResponse(url=spotify_url)

@app.get("/spotify/callback")
async def spotify_callback(
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        return {"error": error}

    if not code:
        return {"error": "Spotify did not return an authorization code"}

    return {"message": "Spotify authorization succeeded"}
