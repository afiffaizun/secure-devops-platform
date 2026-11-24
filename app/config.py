import os


class Config:
    port: int = int(os.getenv("PORT", "8080"))
    version: str = "0.1.0"


config = Config()
