from datetime import datetime, timezone
from sqlalchemy import String, Integer, BigInteger, Boolean, JSON, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(250))
class Node(Base):
    __tablename__ = 'nodes'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    term: Mapped[int] = mapped_column(Integer)
    log_position: Mapped[int] = mapped_column(Integer)
    available: Mapped[bool] = mapped_column(Boolean)
    fenced: Mapped[bool] = mapped_column(Boolean)
    vote_enabled: Mapped[bool] = mapped_column(Boolean)
class Scenario(Base):
    __tablename__ = 'scenarios'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    fail_primary: Mapped[bool] = mapped_column(Boolean)
    fence_primary: Mapped[bool] = mapped_column(Boolean)
    max_data_loss: Mapped[int] = mapped_column(Integer)
    required_term: Mapped[int] = mapped_column(Integer)
class Drill(Base):
    __tablename__ = 'drills'
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey('scenarios.id'))
    label: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class Audit(Base):
    __tablename__ = 'audits'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Reconciliation(Base):
    """两班核对申请。申请时冻结两个时段内已完成的演练ID，之后新完成的演练不影响本次核对。"""
    __tablename__ = 'reconciliations'
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    shift_a_start: Mapped[datetime] = mapped_column(DateTime)
    shift_a_end: Mapped[datetime] = mapped_column(DateTime)
    shift_b_start: Mapped[datetime] = mapped_column(DateTime)
    shift_b_end: Mapped[datetime] = mapped_column(DateTime)
    # queued/scanning/merging/completed/failed
    status: Mapped[str] = mapped_column(String(20), default='queued')
    frozen_drill_ids: Mapped[dict] = mapped_column(JSON)
    cursor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    pair_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class ReconciliationBatch(Base):
    """已处理批次台账。扫描批次和合并批次分别编号；重试时据此跳过已发布内容。"""
    __tablename__ = 'reconciliation_batches'
    __table_args__ = (UniqueConstraint('reconciliation_id', 'phase', 'batch_no', name='uq_recon_batch'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey('reconciliations.id'))
    phase: Mapped[str] = mapped_column(String(10))  # scan / merge
    batch_no: Mapped[int] = mapped_column(Integer)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    node_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class ReconciliationEvidence(Base):
    """分批复核的候选证据（每条来自一场已完成演练的一个节点），按 (recon, shift, node, drill) 去重。"""
    __tablename__ = 'reconciliation_evidences'
    __table_args__ = (
        UniqueConstraint('reconciliation_id', 'shift', 'node_name', 'drill_id', name='uq_recon_evidence'),
        Index('ix_recon_evidence_lookup', 'reconciliation_id', 'shift', 'node_name', 'id'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey('reconciliations.id'))
    shift: Mapped[str] = mapped_column(String(1))  # A / B
    drill_id: Mapped[int] = mapped_column(ForeignKey('drills.id'))
    node_name: Mapped[str] = mapped_column(String(80))
    log_position: Mapped[int] = mapped_column(Integer)
    lag: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class ReconciliationPair(Base):
    """同名节点在两班场次的两两配对结果。"""
    __tablename__ = 'reconciliation_pairs'
    __table_args__ = (
        UniqueConstraint('reconciliation_id', 'evidence_a_id', 'evidence_b_id', name='uq_recon_pair'),
        Index('ix_recon_pair_order', 'reconciliation_id', 'merge_seq'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey('reconciliations.id'))
    merge_seq: Mapped[int] = mapped_column(BigInteger)
    node_name: Mapped[str] = mapped_column(String(80))
    evidence_a_id: Mapped[int] = mapped_column(ForeignKey('reconciliation_evidences.id'))
    evidence_b_id: Mapped[int] = mapped_column(ForeignKey('reconciliation_evidences.id'))
    drill_a_id: Mapped[int] = mapped_column(ForeignKey('drills.id'))
    drill_b_id: Mapped[int] = mapped_column(ForeignKey('drills.id'))
    lag_a: Mapped[int] = mapped_column(Integer)
    lag_b: Mapped[int] = mapped_column(Integer)
    lag_diff: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
