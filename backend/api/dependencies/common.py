from collections.abc import Generator

from fastapi import HTTPException, status

from db.connection import create_connection


def get_db_connection() -> Generator:
    try:
        connection = create_connection()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available",
        ) from error

    try:
        yield connection
    finally:
        connection.close()
