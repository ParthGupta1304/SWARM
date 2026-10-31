// Offline browser-behavior check: no real reset or network requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
function element(tag='div') {
  return {tagName:tag,children:[],handlers:{},value:'',textContent:'',className:'',
    classList:{toggle(){}},addEventListener(name,handler){this.handlers[name]=handler;},
    append(...children){this.children.push(...children);},
    replaceChildren(...children){this.children=[...children];},
    reset(){this.resetCount=(this.resetCount||0)+1;},setAttribute(){},
    get lastChild(){return this.children.at(-1);}};
}
function storage(entries) {const data=new Map(entries);return {
  getItem:key=>data.get(key)||null,setItem:(key,value)=>data.set(key,String(value)),
  removeItem:key=>data.delete(key),data};}
const local=storage([['bazaar-user','9'],['other-app','preserve']]);
const session=storage([]);
const deleted=[];let reloads=0,confirmed=false,posts=0,polls=0;
let finishReview;
const oldReview=new Promise(resolve=>{finishReview=resolve;});
let state={generation:'initial',model:'scripted-fixture',token_budget:1000,max_rounds:6,
  busy:false,resetting:false,reset_failed:false,reset_allowed:true,error:null,
  actions:[],findings:[],events:[],runs:[],gate:null,
  benchmark:{runs:[{run_id:'old-run'}],conditions:{}}};
let source;
const scope={console,Promise,JSON,Number,Map,Set,Date,localStorage:local,sessionStorage:session,
  location:{reload(){reloads++;}},setTimeout:fn=>setImmediate(fn),
  document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},
    createElement:element,querySelectorAll(){return [];}},
  window:{confirm:()=>confirmed,caches:{}},
  caches:{keys:async()=>['swarm-history','bazaar-preview','other-cache'],
    delete:async key=>{deleted.push(key);return true;}},
  EventSource:class {constructor(){source=this;}addEventListener(){}},
  fetch:async (path, options={})=>{
    if(path==='/api/state')return {ok:true,json:async()=>state};
    if(path==='/api/review')return oldReview;
    if(path==='/api/reset'){
      posts++;assert.equal(JSON.parse(options.body).confirmed,true);
      return {ok:true,json:async()=>({status:'resetting'})};
    }
    if(path==='/api/workspace')return {ok:true,json:async()=>{
      polls++;return {resetting:polls===1,reset_failed:false,generation:'reset-2'};
    }};
    throw new Error('Unexpected request: '+path);
  }};
vm.createContext(scope);
vm.runInContext(fs.readFileSync('dashboard/app.js','utf8'),scope);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick();
  assert.equal(session.getItem('swarm-generation'),'initial');
  const next={...state,generation:'reset-1',benchmark:null};
  source.onmessage({data:JSON.stringify(next)});
  finishReview({ok:true,json:async()=>({findings:[{id:'stale',title:'Must not reappear'}]})});
  await tick();
  assert.equal(local.getItem('bazaar-user'),null);
  assert.equal(local.getItem('other-app'),'preserve');
  assert.equal(session.getItem('swarm-generation'),'reset-1');
  assert.equal(elements.get('review-finding').children.length,1);
  assert.equal(elements.get('review-finding').children[0].value,'');
  source.onmessage({data:JSON.stringify(state)}); // Delayed response from before reset.
  assert.equal(session.getItem('swarm-generation'),'reset-1');
  assert.equal(elements.get('review-finding').children.length,1);
  const handler=elements.get('reset').handlers.click;
  await handler();assert.equal(posts,0); // Cancel confirmation means no deletion.
  confirmed=true;state={...next,generation:'reset-2'};
  await handler();await tick();
  assert.equal(posts,1);assert.equal(polls,2);assert.equal(reloads,1);
  assert.equal(session.getItem('swarm-generation'),'reset-2');
  assert.equal(deleted.includes('other-cache'),false);
  assert.ok(deleted.includes('swarm-history')&&deleted.includes('bazaar-preview'));
  source.onmessage({data:JSON.stringify({...state,reset_allowed:false})});
  assert.equal(elements.get('reset').disabled,true);
  source.onmessage({data:JSON.stringify({...state,reset_failed:true,error:'Retry reset'})});
  assert.equal(elements.get('start').disabled,true);
  assert.equal(elements.get('reset').disabled,false);
  console.log('PASS reset UI: confirmation, cache/state clearing, stale review/response rejection, polling/reload, read-only and retry controls');
})().catch(error=>{console.error(error);process.exitCode=1;});
