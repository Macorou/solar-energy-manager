from typing import Literal
from pydantic import BaseModel

LogLevel = Literal['FATAL', 'ERROR', 'WARN', 'INFO', 'DEBUG', 'TRACE']


class LogEntry(BaseModel):
    id: int
    at: str
    level: LogLevel
    area: str
    message: str


class LogPage(BaseModel):
    entries: list[LogEntry]
    cursor: int
    has_more: bool
    has_older: bool
    areas: list[str]
    gap: bool
    retention_days: int
    max_entries: int
    max_verbose_entries: int
    dropped: int
