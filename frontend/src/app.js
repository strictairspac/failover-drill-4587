import {session} from './stores/session.js';
import {store} from './stores/entities.js';
import {drillsAPI,reconciliationsAPI} from './api/entities.js';
import {layout} from './components/common/layout.js';
import {loginPage,bindLogin} from './pages/login.js';
import {nodesPage,bindNodes} from './pages/nodes.js';
import {scenariosPage,bindScenarios} from './pages/scenarios.js';
import {drillsPage,bindDrills} from './pages/drills.js';
import {reconciliationsPage,bindReconciliations} from './pages/reconciliations.js';
import {reconDetailPage,bindReconDetail} from './pages/recon_detail.js';
import {detailPage,bindDetail} from './pages/detail.js';
import {routes} from './router/routes.js';
import {esc} from './utils/html.js';
const app=document.querySelector('#app');
function parseHash(){
 const raw=location.hash.slice(1);
 const [path,query='']=raw.split('?');
 const [key,id]=path.split('/');
 const params=new URLSearchParams(query);
 return {key,id,page:Number(params.get('page')||1),node:params.get('node')||''};
}
async function render(){
 const {key,id,page,node}=parseHash();
 if(!session.token||key==='login'){app.innerHTML=loginPage();bindLogin();return;}
 try{
  await store.refresh();
  let body,job;
  const route=routes[key]?key:'nodes';
  if(route==='nodes')body=nodesPage();
  if(route==='scenarios')body=scenariosPage();
  if(route==='drills')body=drillsPage();
  if(route==='reconciliations')body=reconciliationsPage(store.reconciliations);
  if(route==='recon'){body=await reconDetailPage(Number(id),page,node);}
  if(route==='detail'){job=id?await drillsAPI.get(Number(id)):store.drills[0];body=detailPage(job);}
  const [title,subtitle]=routes[route==='recon'?'reconciliations':route]||routes.nodes;
  app.innerHTML=layout(title,subtitle,body);
  document.querySelector('#logout').onclick=()=>{session.clear();location.hash='#login';};
  if(route==='nodes')bindNodes(render);
  if(route==='scenarios')bindScenarios(render);
  if(route==='drills')bindDrills(render);
  if(route==='reconciliations')bindReconciliations(render,store.reconciliations);
  if(route==='recon')bindReconDetail(Number(id),page,node,render);
  if(route==='detail')bindDetail(job,render);
 }catch(e){app.innerHTML=layout('暂时无法载入','请检查服务状态后重试。',`<p class="notice error">${esc(e.message)}</p><button id="retry">重新加载</button>`);document.querySelector('#retry').onclick=render;document.querySelector('#logout').onclick=()=>{session.clear();location.hash='#login';};}
}
window.addEventListener('hashchange',render);render();
