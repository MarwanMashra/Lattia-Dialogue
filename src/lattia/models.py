from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from .db import Base


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    # defaults are Python side, safer than server_default for JSONB
    health_data = Column(JSONB, nullable=False, default=dict)
    is_done = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages = relationship(
        "Message", back_populates="profile", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    profile_id = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile = relationship("Profile", back_populates="messages")
