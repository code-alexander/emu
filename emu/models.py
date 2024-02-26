from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class EmuState(BaseModel):
    block_height: int
    block_hash: bytes
    coinbase: bytes
    prev_retarget_time: datetime
    time: datetime
    target: bytes


class EmuTable(SQLModel, table=True):
    block_height: int = Field(primary_key=True)
    block_hash: str
    coinbase: str
    prev_retarget_time: datetime
    time: datetime
    target: str
