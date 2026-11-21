"""两班核对申请与查询。

申请核对时演练照常出结论（不触碰演练队列），只把申请瞬间两个时段内
状态已为 completed 的演练ID冻结下来；之后新完成的场次不进入本次核对。
"""
from sqlalchemy import select, func
from fastapi import HTTPException
from src.models.entities import (
    Drill, Reconciliation, ReconciliationPair,
)
from src.schemas.reconciliation import ReconciliationInput
from src.utils.serialize import record


def _freeze_drill_ids(db, start, end):
    rows = db.scalars(
        select(Drill.id).where(
            Drill.status == 'completed',
            Drill.created_at >= start.replace(tzinfo=None),
            Drill.created_at < end.replace(tzinfo=None),
        ).order_by(Drill.id)
    ).all()
    return list(rows)


def create_reconciliation(db, payload: ReconciliationInput):
    ids_a = _freeze_drill_ids(db, payload.shift_a_start, payload.shift_a_end)
    ids_b = _freeze_drill_ids(db, payload.shift_b_start, payload.shift_b_end)
    if not ids_a or not ids_b:
        raise HTTPException(422, '两个时段都至少需要一场已完成演练，否则无法配对')
    obj = Reconciliation(
        label=payload.label,
        shift_a_start=payload.shift_a_start.replace(tzinfo=None),
        shift_a_end=payload.shift_a_end.replace(tzinfo=None),
        shift_b_start=payload.shift_b_start.replace(tzinfo=None),
        shift_b_end=payload.shift_b_end.replace(tzinfo=None),
        status='queued',
        frozen_drill_ids={'A': ids_a, 'B': ids_b},
        cursor=None,
        evidence_count=0,
        pair_count=0,
    )
    db.add(obj)
    db.flush()
    return obj


def list_reconciliations(db):
    rows = db.scalars(select(Reconciliation).order_by(Reconciliation.id.desc()).limit(100)).all()
    return [record(r) for r in rows]


def get_reconciliation(db, recon_id):
    obj = db.get(Reconciliation, recon_id)
    if obj is None:
        raise HTTPException(404, '核对申请不存在')
    return obj


def list_pairs(db, recon_id, node_name=None, page=1, page_size=20):
    get_reconciliation(db, recon_id)
    stmt = select(ReconciliationPair).where(ReconciliationPair.reconciliation_id == recon_id)
    count_stmt = select(func.count()).select_from(ReconciliationPair).where(
        ReconciliationPair.reconciliation_id == recon_id)
    if node_name:
        like = f'%{node_name}%'
        stmt = stmt.where(ReconciliationPair.node_name.like(like))
        count_stmt = count_stmt.where(ReconciliationPair.node_name.like(like))
    total = db.scalar(count_stmt)
    rows = db.scalars(
        stmt.order_by(ReconciliationPair.merge_seq)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        'items': [record(p) for p in rows],
        'page': page,
        'page_size': page_size,
        'total': total,
    }
