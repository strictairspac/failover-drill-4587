import {nodesAPI,scenariosAPI,drillsAPI,reconciliationsAPI} from '../api/entities.js';
export const store={nodes:[],scenarios:[],drills:[],reconciliations:[],async refresh(){[this.nodes,this.scenarios,this.drills,this.reconciliations]=await Promise.all([nodesAPI.list(),scenariosAPI.list(),drillsAPI.list(),reconciliationsAPI.list()]);}};
