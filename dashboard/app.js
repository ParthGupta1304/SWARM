const $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const money=value=>'$'+Number(value||0).toFixed(4);
let fetching=false;
let lastTimeline='',lastFindings='';
for(const tab of document.querySelectorAll('.tab'))tab.addEventListener('click',()=>{for(const other of document.querySelectorAll('.tab'))other.classList.toggle('active',other===tab);for(const view of document.querySelectorAll('.view'))view.hidden=view.id!==tab.dataset.tab;});
async function command(path,payload){try{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})});if(!response.ok)throw new Error((await response.json()).detail||'Request failed');await refresh();}catch(error){$('error').hidden=false;$('error').textContent=error.message;}}
$('start').addEventListener('click',()=>command('/api/start',{condition:$('condition').value}));
$('stop').addEventListener('click',()=>command('/api/stop'));
function render(data){
 $('connection').textContent='Connected · updates every second';
 $('start').disabled=data.busy;$('stop').disabled=!data.busy;
 $('error').hidden=!data.error;if(data.error)$('error').textContent=data.error;
 const runs=data.runs||[];const run=runs.find(r=>r.status==='running')||runs.at(-1);
 $('model').textContent=data.model;$('tokens').textContent=Number(run?.tokens_used||0).toLocaleString();
 $('budget').max=run?.token_budget||data.token_budget||1;$('budget').value=run?.tokens_used||0;
 $('cap').textContent='of '+Number(run?.token_budget||data.token_budget).toLocaleString()+' tokens';
 $('cost').textContent=money(run?.cost_usd);$('status').textContent=data.busy?'Running':(run?.status||'Ready');
 const findings=data.findings||[];$('verified').textContent=findings.filter(f=>f.verified).length;
 $('unverified').textContent=findings.filter(f=>!f.verified).length+' unverified';
 const agents=$('agents');agents.replaceChildren();agents.className='';
 for(const actor of run?.agents||[]){const item=node('div',undefined,'agent');item.append(node('b',actor.agent_id),node('span',actor.role+' · '+actor.steps+' actions · '+actor.tokens_used+' tokens'));agents.append(item);}
 if(!agents.children.length){agents.className='empty';agents.textContent='Your configured personas will appear here.';}
 const key=JSON.stringify(data.actions||[]);
 if(key!==lastTimeline){lastTimeline=key;const timeline=$('timeline');timeline.replaceChildren();timeline.className='';const grouped=new Map();for(const action of data.actions||[]){const round=action.round; if(!grouped.has(round))grouped.set(round,[]);grouped.get(round).push(action);}
 for(const [round,actions] of [...grouped].reverse().slice(0,12)){const row=node('div',undefined,'round');row.append(node('span','ROUND '+round,'round-label'));const cells=node('div',undefined,'actions');for(const action of actions){const cell=node('div',undefined,'action'+(action.response_status>=500||!action.response_status?' bad':''));cell.append(node('b',action.agent_id),node('code',action.request.method+' '+action.request.path),node('small',' · '+(action.response_status||'transport error')));cells.append(cell);}row.append(cells);timeline.append(row);}
 if(!grouped.size){timeline.className='empty';timeline.textContent='Start a run to see each actor’s actions, grouped by round.';}}
 const fk=JSON.stringify(findings);if(fk!==lastFindings){lastFindings=fk;const list=$('findings');list.replaceChildren();list.className='';for(const finding of findings){const detail=node('details');const summary=node('summary');summary.append(node('span',finding.verified?'VERIFIED':'UNVERIFIED','badge '+(finding.verified?'confirmed':'pending')),node('span',finding.severity.toUpperCase(),'badge'),node('span',finding.title));detail.append(summary,node('p',(finding.type||'')+' · '+(finding.involved_agents||[]).join(', ')),node('pre',JSON.stringify(finding.minimal_repro_sequence||finding.evidence,null,2)));list.append(detail);}if(!findings.length){list.className='empty';list.textContent='No findings yet. A completed run does not prove the application is bug-free.';}}
 if(data.benchmark){const target=$('benchmark');target.className='';target.replaceChildren();const table=node('table');const head=node('tr');for(const h of ['Condition','Verified recall (mean / range)','Tokens (mean)','Cost (mean)','Measured seeds'])head.append(node('th',h));table.append(head);for(const [condition,values] of Object.entries(data.benchmark.conditions)){const m=values.metrics;const row=node('tr');const pct=x=>x===null?'—':(x*100).toFixed(1)+'%';for(const text of [condition,pct(m.recall.mean)+' / '+pct(m.recall.min)+'–'+pct(m.recall.max),Number(m.tokens_used.mean).toLocaleString(),money(m.cost_usd.mean),m.recall.measured_runs])row.append(node('td',text));table.append(row);}target.append(table);if(data.gate){const message=node('p',data.gate.complete?'Phase 1 gate passed':data.gate.pending.join('. '));message.setAttribute('role','status');target.append(message);}}
}
async function refresh(){if(fetching)return;fetching=true;try{const response=await fetch('/api/state');if(!response.ok)throw new Error('State unavailable');render(await response.json());}catch(error){$('connection').textContent='Disconnected · retrying';$('error').hidden=false;$('error').textContent='Cannot reach the local run console. Check that it is running.';}finally{fetching=false;}}
refresh();setInterval(refresh,1000);
