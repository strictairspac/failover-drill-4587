"""两班核对的分批处理器（外部归并连接思路）。

约束与口径：
- 内存有限：每批最多读取 RECON_BATCH_LIMIT(=100) 条候选证据；
- 同名节点的场次即使在不同扫描批次落盘，合并阶段也按节点名配齐；
- 中断恢复：游标(Reconciliation.cursor)与批次台账(ReconciliationBatch)随事务持久化，
  重试从游标继续，已发布批次不重复发布，已查到的配对顺序(merge_seq)保持不变；
- 演练照常出结论：本处理器只读已完成演练的 result，不改变演练状态。
"""
import logging

from sqlalchemy import select

from src.constants.enums import RECON_BATCH_LIMIT
from src.models.entities import (
    Drill, Reconciliation, ReconciliationBatch,
    ReconciliationEvidence, ReconciliationPair,
)
from src.models.entities import now

logger = logging.getLogger(__name__)


def _extract_candidates(drill: Drill):
    """从一场已完成演练的冻结结果取候选证据（节点名、日志位置、当时落后条数）。"""
    result = drill.result or {}
    candidates = result.get('candidates')
    if not candidates:
        return []
    out = []
    for c in candidates:
        out.append({
            'node_name': c['name'],
            'log_position': c['log_position'],
            'lag': c['lag'],
        })
    return out


def _next_batch_no(db, recon_id, phase):
    used = db.scalars(
        select(ReconciliationBatch.batch_no).where(
            ReconciliationBatch.reconciliation_id == recon_id,
            ReconciliationBatch.phase == phase,
        ).execution_options(autoflush=False)
    ).all()
    return (max(used) + 1) if used else 1


def _load_drills(db, drill_ids):
    if not drill_ids:
        return []
    rows = db.scalars(select(Drill).where(Drill.id.in_(drill_ids))).all()
    by_id = {d.id: d for d in rows}
    return [by_id[i] for i in drill_ids if i in by_id]


def scan_step(db, recon: Reconciliation):
    """扫描阶段一步：至多读 100 条候选证据并落盘，推进游标。返回是否扫描完毕。"""
    if recon.status == 'queued':
        recon.status = 'scanning'
    cursor = dict(recon.cursor or {})
    frozen = recon.frozen_drill_ids or {}

    total_read = 0
    total_written = 0
    for shift in ('A', 'B'):
        key = f'scan_{shift}'
        pos = cursor.get(key, {'drill_index': 0, 'row_offset': 0})
        drill_ids = frozen.get(shift, [])
        drills = _load_drills(db, drill_ids[pos['drill_index']:])
        rows_this_batch = []
        di = pos['drill_index']
        offset = pos['row_offset']
        for drill in drills:
            candidates = _extract_candidates(drill)
            take = candidates[offset:]
            room = RECON_BATCH_LIMIT - total_read
            if room <= 0:
                break
            if len(take) > room:
                # 批次在读到该场中间时打满：di 不前进，row_offset 记录场内续读位置
                rows_this_batch.extend((c, drill) for c in take[:room])
                total_read += room
                offset += room
                break
            rows_this_batch.extend((c, drill) for c in take)
            total_read += len(take)
            offset = 0
            di += 1
        else:
            # 本 shift 全部场次自然消费完
            di = len(drill_ids)
            offset = 0

        if rows_this_batch:
            batch_no = _next_batch_no(db, recon.id, 'scan')
            written = 0
            for c, drill in rows_this_batch:
                exists = db.scalar(select(ReconciliationEvidence.id).where(
                    ReconciliationEvidence.reconciliation_id == recon.id,
                    ReconciliationEvidence.shift == shift,
                    ReconciliationEvidence.node_name == c['node_name'],
                    ReconciliationEvidence.drill_id == drill.id,
                ).execution_options(autoflush=False))
                if exists:
                    continue
                db.add(ReconciliationEvidence(
                    reconciliation_id=recon.id, shift=shift, drill_id=drill.id,
                    node_name=c['node_name'], log_position=c['log_position'], lag=c['lag'],
                ))
                written += 1
            db.add(ReconciliationBatch(
                reconciliation_id=recon.id, phase='scan', batch_no=batch_no,
                rows_read=len(rows_this_batch), rows_written=written,
                node_name=rows_this_batch[0][0]['node_name'],
            ))
            total_written += written
            recon.evidence_count = (recon.evidence_count or 0) + written

        cursor[key] = {'drill_index': di, 'row_offset': offset}
        if total_read >= RECON_BATCH_LIMIT:
            break

    done = all(
        cursor.get(f'scan_{s}', {'drill_index': 0})['drill_index'] >= len(frozen.get(s, []))
        and cursor.get(f'scan_{s}', {}).get('row_offset', 0) == 0
        for s in ('A', 'B')
    )
    recon.cursor = cursor
    if done:
        recon.status = 'merging'
        cursor.setdefault('merge', {'name_offset': 0})
        recon.cursor = cursor
    logger.info('recon %s scan step read=%s written=%s done=%s',
                recon.id, total_read, total_written, done)
    return done


def _existing_pair(db, recon_id, ev_a_id, ev_b_id):
    return db.scalar(select(ReconciliationPair.id).where(
        ReconciliationPair.reconciliation_id == recon_id,
        ReconciliationPair.evidence_a_id == ev_a_id,
        ReconciliationPair.evidence_b_id == ev_b_id,
    ).execution_options(autoflush=False))


def merge_step(db, recon: Reconciliation):
    """合并阶段一步：取下一个同名节点，把两班证据做笛卡尔配对，分批发布。"""
    recon.status = 'merging'
    cursor = dict(recon.cursor or {})
    mcursor = dict(cursor.get('merge', {'name_offset': 0}))
    name_offset = mcursor.get('name_offset', 0)

    names = db.scalars(
        select(ReconciliationEvidence.node_name).where(
            ReconciliationEvidence.reconciliation_id == recon.id,
        ).distinct().order_by(ReconciliationEvidence.node_name)
        .offset(name_offset).limit(1)
    ).all()
    if not names:
        recon.status = 'completed'
        recon.completed_at = now()
        recon.cursor = cursor
        return True

    node_name = names[0]
    ev_a = db.scalars(select(ReconciliationEvidence).where(
        ReconciliationEvidence.reconciliation_id == recon.id,
        ReconciliationEvidence.shift == 'A',
        ReconciliationEvidence.node_name == node_name,
    ).order_by(ReconciliationEvidence.drill_id, ReconciliationEvidence.id)).all()
    ev_b = db.scalars(select(ReconciliationEvidence).where(
        ReconciliationEvidence.reconciliation_id == recon.id,
        ReconciliationEvidence.shift == 'B',
        ReconciliationEvidence.node_name == node_name,
    ).order_by(ReconciliationEvidence.drill_id, ReconciliationEvidence.id)).all()

    # 每批读取上限同样约束合并发布：候选对超过100时拆成多个merge批次
    combos = [(a, b) for a in ev_a for b in ev_b]
    written_total = 0
    read_total = len(combos)
    # 批次编号在循环外一次性取定：同一事务内多个chunk都可见该起点，避免重号
    next_batch_no = _next_batch_no(db, recon.id, 'merge')
    # merge_seq 高水位记在游标里：同一事务内未 flush 的配对也连续取号，
    # 崩溃回滚后高水位随游标一起回退，已发布配对的相对顺序永远不变且无空洞。
    next_seq = mcursor.get('next_seq', 1)
    for start in range(0, max(len(combos), 1), RECON_BATCH_LIMIT) or [0]:
        chunk = combos[start:start + RECON_BATCH_LIMIT]
        if not chunk:
            continue
        batch_no = next_batch_no
        next_batch_no += 1
        written = 0
        for a, b in chunk:
            if _existing_pair(db, recon.id, a.id, b.id):
                continue
            db.add(ReconciliationPair(
                reconciliation_id=recon.id, merge_seq=next_seq, node_name=node_name,
                evidence_a_id=a.id, evidence_b_id=b.id,
                drill_a_id=a.drill_id, drill_b_id=b.drill_id,
                lag_a=a.lag, lag_b=b.lag, lag_diff=a.lag - b.lag,
            ))
            next_seq += 1
            written += 1
        db.add(ReconciliationBatch(
            reconciliation_id=recon.id, phase='merge', batch_no=batch_no,
            rows_read=len(chunk), rows_written=written, node_name=node_name,
        ))
        written_total += written
        recon.pair_count = (recon.pair_count or 0) + written

    mcursor['name_offset'] = name_offset + 1
    mcursor['next_seq'] = next_seq
    cursor['merge'] = mcursor
    recon.cursor = cursor
    logger.info('recon %s merge node=%s combos=%s written=%s',
                recon.id, node_name, read_total, written_total)
    return False


def process_reconciliation(db, recon_id):
    """供 worker 调用：推进一个核对申请一步。

    任何异常都把状态落为 failed（含原因）并正常返回，由调用方 commit；
    这样 worker 的回滚不会清掉 failed 标记而造成无限重试。
    """
    recon = db.get(Reconciliation, recon_id)
    if recon is None:
        return
    if recon.status in ('completed', 'failed'):
        return
    try:
        if recon.status in ('queued', 'scanning'):
            done = scan_step(db, recon)
            if not done:
                return
        merge_step(db, recon)
    except Exception as exc:  # noqa: BLE001 - 失败原因需落库供页面展示
        logger.exception('reconciliation %s failed', recon_id)
        recon.status = 'failed'
        recon.error = str(exc)[:300]
