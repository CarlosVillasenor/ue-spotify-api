from fastapi import HTTPException
import os

def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {name}",
        )
    return value