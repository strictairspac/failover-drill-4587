import {reconciliationsAPI} from '../api/entities.js';
import {table} from '../components/common/table.js';
import {reconBadge} from '../components/common/status.js';
import {esc} from '../utils/html.js';

const fmt=t=>t?new Date(t).toLocaleString('zh-CN',{hour12:false}):'—';
const PAGE_SIZE=20;

export async function reconDetailPage(id,page=1,nodeName=''){
 const recon=await reconciliationsAPI.get(id);
 const data=await reconciliationsAPI.pairs(id,{page,page_size:PAGE_SIZE,...(nodeName?{node_name:nodeName}:{})});
 const done=recon.status==='completed';
 const progress=done?'全部算齐':recon.status==='failed'?('失败：'+(recon.error||'未知原因')):'后台分批处理中，已完成的配对可先翻查';
 const rows=data.items.map(p=>[
  esc(p.node_name),
  `#${p.drill_a_id}（落后 ${p.lag_a} 条）`,
  `#${p.drill_b_id}（落后 ${p.lag_b} 条）`,
  p.lag_diff,
 ]);
 const totalPages=Math.max(1,Math.ceil(data.total/PAGE_SIZE));
 const pager=`<div class="pager">
  <button class="secondary" id="prev" ${page<=1?'disabled':''}>← 上一页</button>
  <span>第 ${page} / ${totalPages} 页 · 共 ${data.total} 对</span>
  <button class="secondary" id="next" ${page>=totalPages?'disabled':''}>下一页 →</button>
 </div>`;
 return `<div class="section-title"><h2>${esc(recon.label)} <small>#${recon.id}</small></h2>${reconBadge(recon.status)}</div>
 <section class="verdict"><div><p>核对进度</p><h2>${done?'已算齐':'计算中'}</h2></div>
  <p>${esc(progress)}<br>
  冻结场次 A班 ${(recon.frozen_drill_ids?.A||[]).length} 场 / B班 ${(recon.frozen_drill_ids?.B||[]).length} 场
  · 候选证据 ${recon.evidence_count} 条 · 已配对 ${recon.pair_count} 对<br>
  申请于 ${fmt(recon.created_at)} · 算齐于 ${fmt(recon.completed_at)}</p></section>
 <form id="node-filter" class="filter-bar"><label>按节点名筛选<input name="node_name" value="${esc(nodeName)}" placeholder="如 hs-east"></label>
  <button type="submit">筛选</button>
  ${nodeName?'<button type="button" class="secondary" id="clear-filter">清除</button>':''}</form>
 ${table(['同名节点','A班场次（落后条数）','B班场次（落后条数）','落后差 A−B'],rows)}
 ${pager}
 <div class="toolbar"><button class="secondary" id="refresh">刷新状态</button><a class="back-link" href="#reconciliations">← 返回核对列表</a></div>`;
}

export function bindReconDetail(id,page,nodeName,render){
 const go=(p,n)=>{location.hash=`#recon/${id}?page=${p}${n?`&node=${encodeURIComponent(n)}`:''}`;};
 document.querySelector('#refresh').onclick=()=>render();
 document.querySelector('#prev')?.addEventListener('click',()=>{if(page>1)go(page-1,nodeName);});
 document.querySelector('#next')?.addEventListener('click',()=>go(page+1,nodeName));
 document.querySelector('#clear-filter')?.addEventListener('click',()=>go(1,''));
 document.querySelector('#node-filter')?.addEventListener('submit',e=>{
  e.preventDefault();
  const v=new FormData(e.target).get('node_name').trim();
  go(1,v);
 });
}
