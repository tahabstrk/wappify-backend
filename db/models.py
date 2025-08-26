from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, func, ForeignKey, Index, UniqueConstraint

Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(120))

class WaCredential(Base):
    __tablename__ = "wa_credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, unique=True)
    phone_number_id: Mapped[str] = mapped_column(String(40), nullable=False)
    waba_id: Mapped[str | None] = mapped_column(String(40))
    access_token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship("Account")

class Message(Base):
    __tablename__ = "messages"
    id = mapped_column(Integer, primary_key=True)
    account_id = mapped_column(ForeignKey("accounts.id"), nullable=False)
    to = mapped_column(String(30), nullable=False)   # E.164
    body = mapped_column(String(4000), nullable=True)
    template_name = mapped_column(String(120), nullable=True)
    status = mapped_column(String(30), default="queued")  # queued/sent/delivered/read/failed
    provider_id = mapped_column(String(80), nullable=True)  # WhatsApp message id
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


Index("ix_wa_credentials_acc", WaCredential.account_id)