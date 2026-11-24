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
from datetime import datetime, timedelta, timezone
import httpx

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
        "scope": "user-read-private user-read-email user-library-modify playlist-modify-private",
        "redirect_uri": required_env("SPOTIFY_REDIRECT_URI"),
        "show_dialog": "true",
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
        raise HTTPException(status_code=400, detail=f"Spotify authorization failed: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Spotify did not return an authorization code")

    client_id = required_env("SPOTIFY_CLIENT_ID")
    client_secret = required_env("SPOTIFY_CLIENT_SECRET")
    redirect_uri = required_env("SPOTIFY_REDIRECT_URI")

    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(client_id, client_secret),
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            profile_response = await client.get(
                "https://api.spotify.com/v1/me",
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}"
                },
            )
            profile_response.raise_for_status()
            profile = profile_response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Spotify request failed: {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not connect to Spotify: {exc}")

    spotify_account_id = profile.get("account_id")
    if not spotify_account_id:
        raise HTTPException(status_code=502, detail="Spotify profile did not include account_id")

    expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(seconds=tokens["expires_in"])
    )

    db = DatabaseConnection(
        host=required_env("databaseHost"),
        user=required_env("databaseUser"),
        password=required_env("databasePassword"),
        database=required_env("databaseName"),
    )
    connection = await db.get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO spotify_tokens
                (spotify_account_id, access_token, refresh_token,
                 token_type, expires_at, scope)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                access_token = VALUES(access_token),
                refresh_token = VALUES(refresh_token),
                token_type = VALUES(token_type),
                expires_at = VALUES(expires_at),
                scope = VALUES(scope)
            """,
            (
                spotify_account_id,
                tokens["access_token"],
                tokens["refresh_token"],
                tokens["token_type"],
                expires_at,
                tokens.get("scope", ""),
            ),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    return {
        "message": "Spotify account connected and tokens saved",
        "spotify_account_id": spotify_account_id,
        "expires_at": expires_at.isoformat(),
    }

@app.post("/spotify/refresh/{spotify_account_id}")
async def refresh_spotify_token(spotify_account_id: str):
    db = DatabaseConnection(
        host=required_env("databaseHost"),
        user=required_env("databaseUser"),
        password=required_env("databasePassword"),
        database=required_env("databaseName"),
    )
    connection = await db.get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT refresh_token FROM spotify_tokens WHERE spotify_account_id = %s",
            (spotify_account_id,),
        )
        saved = cursor.fetchone()

        if not saved:
            raise HTTPException(status_code=404, detail="Spotify account not found")

        refresh_token = (
            saved["refresh_token"] if isinstance(saved, dict) else saved[0]
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(
                    required_env("SPOTIFY_CLIENT_ID"),
                    required_env("SPOTIFY_CLIENT_SECRET"),
                ),
            )

        if response.is_error:
            raise HTTPException(status_code=502, detail=response.text)

        tokens = response.json()
        expires_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(seconds=tokens["expires_in"])
        )

        cursor.execute(
            """
            UPDATE spotify_tokens
            SET access_token = %s, refresh_token = %s, expires_at = %s
            WHERE spotify_account_id = %s
            """,
            (
                tokens["access_token"],
                tokens.get("refresh_token", refresh_token),
                expires_at,
                spotify_account_id,
            ),
        )
        connection.commit()

        return {
            "message": "Token refreshed",
            "expires_at": expires_at.isoformat(),
        }

    finally:
        cursor.close()
        connection.close()