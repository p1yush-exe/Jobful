from pathlib import Path


def load_sql(path: str) -> str:
    sql_path = Path(__file__).resolve().parents[2] / "database" / "queries" / path
    return sql_path.read_text(encoding="utf-8")
