from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
    else:
        # Keep bootstrap superuser credentials in sync with current environment.
        verified = False
        if user.hashed_password:
            verified, _ = verify_password(
                settings.FIRST_SUPERUSER_PASSWORD, user.hashed_password
            )
        if (
            not verified
            or not user.is_superuser
            or not user.is_active
            or user.full_name is None
        ):
            user.hashed_password = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
            user.is_superuser = True
            user.is_active = True
            user.full_name = user.full_name or ""
            session.add(user)
            session.commit()
