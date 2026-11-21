import logging, time
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models.entities import Drill, Reconciliation
from src.services.election import elect
from src.services.reconciliation_processor import process_reconciliation
redis = Redis.from_url(REDIS_URL)
logging.basicConfig(level=logging.INFO)
# Redis leadership lock ensures only one worker processes the durable DB queue.
while True:
    Path('/tmp/heartbeat').touch()
    lock = redis.lock('drill-worker', timeout=15, blocking_timeout=1)
    try:
        with lock:
            with Session() as db:
                job = db.scalar(select(Drill).where(Drill.status == 'queued').order_by(Drill.id).with_for_update(skip_locked=True))
                if job:
                    job.status = 'running'
                    try:
                        job.result = elect(job.snapshot['nodes'], job.snapshot['scenario'])
                        job.status = 'completed'
                    except ValueError as exc:
                        job.result = {'error': str(exc), 'simulation': True}
                        job.status = 'failed'
                    db.commit()
                    logging.info('drill %s %s', job.id, job.status)
                else:
                    # 演练照常优先出结论；队列空闲时推进一个核对申请的一批。
                    recon = db.scalar(select(Reconciliation).where(
                        Reconciliation.status.in_(['queued', 'scanning', 'merging'])
                    ).order_by(Reconciliation.id))
                    if recon:
                        try:
                            process_reconciliation(db, recon.id)
                            db.commit()
                            logging.info('reconciliation %s advanced', recon.id)
                        except Exception:
                            db.rollback()
    except Exception:
        logging.exception('worker retry')
    time.sleep(1)
