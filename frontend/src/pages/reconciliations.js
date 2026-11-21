import {session} from '../stores/session.js';
import {reconciliationsAPI} from '../api/entities.js';
import {table} from '../components/common/table.js';
import {reconBadge} from '../components/common/status.js';
import {esc,formObject} from '../utils/html.js';
import {action,message} from '../hooks/action.js';

const fmt=t=>t?new Date(t).toLocaleString('zh-CN',{hour12:false}):'—';
const today=()=>new Date().toISOString().slice(0,11);

export function reconciliationsPage(recons){
 const rows=recons.map(r=>[
  r.id,esc(r.label),reconBadge(r.status),
  `${(r.frozen_drill_ids?.A||[]).length} / ${(r.frozen_drill_ids?.B||[]).length}`,
  r.evidence_count,r.pair_count,fmt(r.completed_at),
  `<a href="#recon/${r.id}">核对配对 →</a>`,
 ]);
 return `<section class="split compact"><div><h2>申请两班核对</h2><p>选择两个不重叠的班次时段。申请瞬间只冻结当时已完成的场次，之后出结论的演练照常运转，不影响本次核对。</p></div>
 ${session.role!=='viewer'?`<form id="recon-form">
  <label>核对标签<input name="label" value="两班演练核对" required maxlength="120"></label>
  <div class="fields">
   <label>A班开始<input type="datetime-local" name="shift_a_start" value="${today()}06:00" required></label>
   <label>A班结束<input type="datetime-local" name="shift_a_end" value="${today()}14:00" required></label>
   <label>B班开始<input type="datetime-local" name="shift_b_start" value="${today()}14:00" required></label>
   <label>B班结束<input type="datetime-local" name="shift_b_end" value="${today()}22:00" required></label>
  </div>
  <button type="submit">冻结场次并申请核对 →</button>
 </form>`:'<p class="readonly">观察员可复核下方核对记录与配对明细。</p>'}</section>
 <div class="section-title"><h2>核对申请</h2><button class="secondary" id="refresh">刷新进度</button></div>
 ${table(['编号','核对标签','状态','冻结场次 A/B','候选证据','已配对','算齐时间','操作'],rows)}`;
}

export function bindReconciliations(render,recons){
 document.querySelector('#refresh').onclick=render;
 const form=document.querySelector('#recon-form');
 action(form,async f=>{
  const d=formObject(f);
  const obj=await reconciliationsAPI.create(d);
  message('核对已申请，后台分批处理中');
  location.hash='#recon/'+obj.id;
 });
}
