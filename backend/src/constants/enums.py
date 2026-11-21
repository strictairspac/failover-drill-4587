ROLES = ('admin', 'operator', 'viewer')
DRILL_STATUSES = ('queued', 'running', 'completed', 'failed')
RECON_STATUSES = ('queued', 'scanning', 'merging', 'completed', 'failed')
# 每批最多读取的候选证据条数；同名节点跨批也能在合并阶段配齐
RECON_BATCH_LIMIT = 100
