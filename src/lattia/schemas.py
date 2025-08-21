from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Profile
class ProfileBase(BaseModel):
    name: str = Field(..., max_length=100)


class ProfileCreate(ProfileBase):
    pass


class ProfileOut(BaseModel):
    id: int
    name: str
    is_done: bool
    health_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Messages
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HistoryOut(BaseModel):
    profile: ProfileOut
    messages: list[MessageOut]


# Status and health
class StatusUpdate(BaseModel):
    is_done: bool


class HealthData(BaseModel):
    health_data: dict
