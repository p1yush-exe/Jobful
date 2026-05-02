from fastapi import status


def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "jobful-api"}
