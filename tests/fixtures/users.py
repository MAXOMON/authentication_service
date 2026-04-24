from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_tables import User
from app.utils import get_password_hash
from tests.fixtures.constants import USER_EMAIL, USER_PASSWORD


async def create_user(
    session: AsyncSession,
    user_email=USER_EMAIL,
    user_password=USER_PASSWORD,
    is_active=True,
    version=0,
) -> User:
    user = User(
        email=user_email,
        hashed_password=get_password_hash(user_password),
        is_active=is_active,
        version=version,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
