from fastapi import FastAPI

from app.config import config

app = FastAPI(title="secure-devops-platform", version=config.version)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


@app.get("/")
def root():
    return {"service": "secure-devops-platform", "version": config.version}
