from fastapi import APIRouter, Depends
from src.config.database import get_db
from src.middlewares.auth import current_user, writable
from src.schemas.reconciliation import ReconciliationInput
from src.services.reconciliation_service import (
    create_reconciliation, list_reconciliations, get_reconciliation, list_pairs,
)
from src.utils.serialize import record
from src.controllers.actions import audit

router = APIRouter()


@router.get('/reconciliations')
def listing(db=Depends(get_db), user=Depends(current_user)):
    return list_reconciliations(db)


@router.post('/reconciliations', status_code=202)
def create(data: ReconciliationInput, db=Depends(get_db), user=Depends(writable)):
    obj = create_reconciliation(db, data)
    audit(db, user, f'reconciliation:enqueue:{obj.id}')
    db.commit()
    # 申请只冻结当时已完成的场次；worker 分批扫描配对，演练队列照常运转。
    return record(obj)


@router.get('/reconciliations/{recon_id}')
def detail(recon_id: int, db=Depends(get_db), user=Depends(current_user)):
    return record(get_reconciliation(db, recon_id))


@router.get('/reconciliations/{recon_id}/pairs')
def pairs(recon_id: int, node_name: str | None = None, page: int = 1, page_size: int = 20,
          db=Depends(get_db), user=Depends(current_user)):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return list_pairs(db, recon_id, node_name=node_name, page=page, page_size=page_size)
