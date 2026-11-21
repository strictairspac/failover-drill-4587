import os
from datetime import datetime, timezone
from sqlalchemy import select
from src.config.database import Base, engine, Session
from src.models.entities import User, Node, Scenario, Drill, Reconciliation
from src.services.node_service import list_nodes
from src.services.election import elect
from src.utils.security import hash_password
from src.utils.serialize import record


def seed():
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO', 'true').lower() != 'true':
        return
    with Session() as db:
        for role in ('admin', 'operator', 'viewer'):
            email = role + '@hengshi.local'
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, role=role, password_hash=hash_password('Drill2026!')))
        for name, role, pos in [('hs-primary', 'leader', 8100), ('hs-east', 'follower', 8100), ('hs-west', 'follower', 8098)]:
            if not db.scalar(select(Node).where(Node.name == name)):
                db.add(Node(name=name, role=role, term=6, log_position=pos, available=True, fenced=False, vote_enabled=True))
        for name, fence in [('晚班隔离演练', True), ('缺少隔离证明', False)]:
            if not db.scalar(select(Scenario).where(Scenario.name == name)):
                db.add(Scenario(name=name, fail_primary=True, fence_primary=fence, max_data_loss=0, required_term=7))
        db.flush()

        scenario = db.scalar(select(Scenario).where(Scenario.name == '晚班隔离演练'))
        # 两班各三场已完成演练，候选节点带各自当时的落后条数
        plan = [
            ('A班-08点核验', datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc)),
            ('A班-10点核验', datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)),
            ('A班-12点核验', datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)),
            ('B班-16点核验', datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)),
            ('B班-18点核验', datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)),
            ('B班-20点核验', datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc)),
        ]
        created = []
        for label, ts in plan:
            if db.scalar(select(Drill).where(Drill.label == label)):
                continue
            snapshot = {'nodes': list_nodes(db), 'scenario': record(scenario)}
            drill = Drill(scenario_id=scenario.id, label=label, status='completed',
                          snapshot=snapshot, result=elect(snapshot['nodes'], snapshot['scenario']),
                          created_at=ts.replace(tzinfo=None))
            db.add(drill)
            created.append((label, ts))
        db.flush()

        if created and not db.scalar(select(Reconciliation).where(Reconciliation.label == '11月17日两班核对')):
            ids = lambda lo, hi: [d.id for d in db.scalars(select(Drill).where(
                Drill.created_at >= lo, Drill.created_at < hi).order_by(Drill.id)).all()]
            a_lo = datetime(2026, 11, 17, 6, 0)
            a_hi = datetime(2026, 11, 17, 14, 0)
            b_lo = datetime(2026, 11, 17, 14, 0)
            b_hi = datetime(2026, 11, 17, 22, 0)
            ids_a, ids_b = ids(a_lo, a_hi), ids(b_lo, b_hi)
            if ids_a and ids_b:
                db.add(Reconciliation(
                    label='11月17日两班核对', status='queued',
                    shift_a_start=a_lo, shift_a_end=a_hi, shift_b_start=b_lo, shift_b_end=b_hi,
                    frozen_drill_ids={'A': ids_a, 'B': ids_b}))
        db.commit()


if __name__ == '__main__':
    seed()
