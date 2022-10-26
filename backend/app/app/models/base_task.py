from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from app.db.base_class import Base, gen_rand_id

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class BaseTask(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)

    original_file_name = Column(String)
    original_file_content_type = Column(String)
    original_file_local_path = Column(String)

    work_id = Column(String, index=True)
    task_id = Column(String, index=True)
    wn_file_id = Column(String, index=True)
    wn_task_id = Column(String, index=True)
    wn_fee = Column(Integer)
    height = Column(Integer, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
