from typing import AsyncGenerator

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings


DATABASE_URL = URL.create(
    drivername=settings.DB_DRIVER_NAME,
    username=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
    host=settings.POSTGRES_IP_ADDRESS,
    port=settings.POSTGRES_PORT,
    database=settings.POSTGRES_DB,
)

engine = create_async_engine(
    DATABASE_URL, connect_args={"command_timeout": 5}, echo=True, future=True
)


async def get_session() -> AsyncGenerator:
    async_session = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
