from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    """Health endpoint."""
    return {"status": "ok"}


class Service:
    def run(self) -> None:
        pass
