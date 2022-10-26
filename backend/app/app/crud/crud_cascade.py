from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.cascade import Cascade
from app.schemas.cascade import CascadeCreate, CascadeUpdate


class CRUDCascade(CRUDBase[Cascade, CascadeCreate, CascadeUpdate]):
    def create_with_owner(
            self, db: Session, *, obj_in: CascadeCreate, owner_id: int
    ) -> Cascade:
        db_obj = Cascade(
            original_file_name=obj_in.original_file_name,
            original_file_content_type=obj_in.original_file_content_type,
            original_file_local_path=obj_in.original_file_local_path,
            work_id=obj_in.work_id,
            task_id=obj_in.task_id,
            wn_file_id=obj_in.wn_file_id,
            wn_fee=obj_in.wn_fee,
            height=obj_in.height,
            owner_id=owner_id
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_task_id(self, db: Session, *, task_id: str) -> Optional[Cascade]:
        return db.query(Cascade).filter(Cascade.task_id == task_id).first()

    def get_multi_by_owner(
            self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )


cascade = CRUDCascade(Cascade)
