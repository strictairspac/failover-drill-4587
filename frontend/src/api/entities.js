import {api} from './client.js';
export const nodesAPI={list:()=>api('/nodes'),save:(data,id)=>api('/nodes'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(data)})};
export const scenariosAPI={list:()=>api('/scenarios'),create:data=>api('/scenarios',{method:'POST',body:JSON.stringify(data)})};
export const drillsAPI={list:()=>api('/drills'),get:id=>api('/drills/'+id),create:data=>api('/drills',{method:'POST',body:JSON.stringify(data)})};
export const reconciliationsAPI={
 list:()=>api('/reconciliations'),
 get:id=>api('/reconciliations/'+id),
 create:data=>api('/reconciliations',{method:'POST',body:JSON.stringify(data)}),
 pairs:(id,params)=>api('/reconciliations/'+id+'/pairs?'+new URLSearchParams(params)),
};
