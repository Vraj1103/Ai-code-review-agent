import os

class Settings:
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")

settings = Settings()
