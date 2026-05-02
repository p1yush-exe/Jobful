from pathlib import Path


_QUERIES_ROOT = Path(__file__).resolve().parent / "queries"


def load_query(*parts: str) -> str:
    query_path = _QUERIES_ROOT.joinpath(*parts)
    return query_path.read_text(encoding="utf-8")