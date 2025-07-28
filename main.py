from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from logger_config import setup_logging, get_logger
from routes.redis_routes.redis_routes import router as redis_router
from routes.frida_routes.auth_router import router as auth_router
from routes.frida_routes.logger_router import router as logger_router  
from routes.ai_router.ai_routes import router as ai_router

# Инициализация логирования
import os

log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level)
logger = get_logger(__name__)

app = FastAPI(
    title="Core API",
    description="API для работы с Redis, Telegram ботом Фридой и AI запросами",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(redis_router)
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(logger_router)


@app.get("/")
async def root():
    """Главная страница API."""
    logger.info("Root endpoint accessed")
    return {
        "message": "Core API работает",
        "version": "1.0.0",
        "services": {"redis": "/redis", "telegram": "/telegram", "ai": "/ai"},
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Проверка состояния API."""
    logger.debug("Health check requested")
    return {"status": "healthy", "message": "API работает нормально"}


if __name__ == "__main__":
    logger.info("Starting Core API server on host=0.0.0.0, port=8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
