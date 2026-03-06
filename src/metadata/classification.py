from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DatabaseType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    PARK_TEMPLATE = "park_template"
    PARK_INSTANCE = "park_instance"
    EXCLUDED = "excluded"


class DatabaseClassification(BaseModel):
    """Classification metadata for a database."""

    database_name: str
    database_type: DatabaseType
    namespace: str = ""
    template_source: Optional[str] = None
    template_instances: List[str] = Field(default_factory=list)
