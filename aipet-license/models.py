import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ActivationCode(Base):
    __tablename__ = "activation_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_days: Mapped[int] = mapped_column(Integer, default=365)
    status: Mapped[str] = mapped_column(String(20), default="unused")
    generated_by: Mapped[str] = mapped_column(String(20), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    licenses: Mapped[list["License"]] = relationship(back_populates="activation_code")

    @classmethod
    def generate_batch(cls, plan_code: str, count: int, valid_days: int = 365) -> list[str]:
        return [f"AIPET-{plan_code.upper()}-{secrets.token_hex(6).upper()}" for _ in range(count)]


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activation_code_id: Mapped[int] = mapped_column(ForeignKey("activation_codes.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    store_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="")
    machine_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    activation_code: Mapped[ActivationCode] = relationship(back_populates="licenses")


class ActivationRecord(Base):
    __tablename__ = "activation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activation_code_id: Mapped[int | None] = mapped_column(ForeignKey("activation_codes.id"))
    license_id: Mapped[int | None] = mapped_column(ForeignKey("licenses.id"))
    machine_id: Mapped[str] = mapped_column(String(120), default="")
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
