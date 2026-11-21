# 数据结构
本小型项目首次启动使用 SQLAlchemy metadata 建立 users/nodes/scenarios/drills/audits 五表，以及两班核对的 reconciliations/reconciliation_batches/reconciliation_evidences/reconciliation_pairs 四表。自然键 users.email、nodes.name、scenarios.name 唯一。drills.scenario_id 为外键，快照在入队时固定。上线结构演进须补充版本化迁移，本项目不支持对既有不同结构数据库自动升级。

## 两班核对表
- `reconciliations`：核对申请。申请时把两个时段内已完成演练ID冻结在 `frozen_drill_ids`(JSON: {A:[],B:[]})，之后新完成的演练不进入本次核对。`status` 为 queued/scanning/merging/completed/failed；`cursor`(JSON) 持久化扫描与合并断点；`completed_at` 记录算齐时间。
- `reconciliation_batches`：批次台账，(reconciliation_id, phase, batch_no) 唯一。phase 为 scan/merge；重试时已发布批次不重复发布。
- `reconciliation_evidences`：候选证据，(reconciliation_id, shift, node_name, drill_id) 唯一。保留每场演练当时的节点日志位置与落后条数 lag。
- `reconciliation_pairs`：同名节点两班场次的两两配对，(reconciliation_id, evidence_a_id, evidence_b_id) 唯一；`merge_seq` 决定已查到配对的稳定顺序，带 (reconciliation_id, merge_seq) 索引供分页。
