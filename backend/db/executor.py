from collections.abc import Sequence

from psycopg2.extensions import connection as Connection


def fetch_one(connection: Connection, query: str, params: Sequence[object]) -> dict[str, object] | None:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        columns = [column.name for column in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(zip(columns, row, strict=False))


def fetch_one_commit(connection: Connection, query: str, params: Sequence[object]) -> dict[str, object] | None:
    row = fetch_one(connection, query, params)
    connection.commit()
    return row


def fetch_all(connection: Connection, query: str, params: Sequence[object]) -> list[dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        columns = [column.name for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def execute(connection: Connection, query: str, params: Sequence[object]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
    connection.commit()
