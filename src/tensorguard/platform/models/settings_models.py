"""
System Settings Model for TensorGuard Platform.
Provides persistent storage for global platform configuration.
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class SystemSettingBase(SQLModel):
    key: str = Field(index=True, unique=True)
    value: str
    description: Optional[str] = None


class SystemSetting(SystemSettingBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None
