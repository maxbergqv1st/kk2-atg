from sqlalchemy import Boolean, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.utils.config import config

engine = create_engine(config.db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Starter(Base):
    __tablename__ = "starters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String, index=True)
    game_type: Mapped[str | None] = mapped_column(String, nullable=True)
    track: Mapped[str | None] = mapped_column(String, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    horse_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horse_name: Mapped[str | None] = mapped_column(String, nullable=True)
    horse_age: Mapped[float | None] = mapped_column(Float, nullable=True)
    driver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String, nullable=True)
    finish_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    race_time_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    won: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scratched: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

# skapar tabellen om den inte finns (körs vid import)
Base.metadata.create_all(bind=engine)
