'use strict';
const sameKey = (source, tradeId) => JSON.stringify([source,tradeId]);
function reconstruct(events){
  const groups=new Map();
  for(const e of events){
    if(!e.source?.trim()||!e.trade_id?.trim()||!Number.isInteger(e.version)||e.version<1||!Number.isInteger(e.arrival_seq)||e.arrival_seq<1||!Number.isInteger(e.notional_minor)||e.notional_minor<0||!['USD','EUR'].includes(e.currency)||!['ACTIVE','CANCELLED'].includes(e.status)) throw new Error('Invalid synthetic event');
    const key=JSON.stringify([e.source,e.trade_id,e.version]);
    if(!groups.has(key))groups.set(key,new Map());
    groups.get(key).set(JSON.stringify([e.status,e.notional_minor,e.currency]),e);
  }
  const quarantined=new Map(),conflictingKeys=[],canonical=[];
  for(const [key,values] of groups){
    const [source,trade_id,version]=JSON.parse(key);
    if(values.size>1){quarantined.set(sameKey(source,trade_id),{source,trade_id});conflictingKeys.push({source,trade_id,version});}
    else{const e=values.values().next().value;canonical.push({source,trade_id,version,status:e.status,notional_minor:e.notional_minor,currency:e.currency});}
  }
  const latestByTrade=new Map();
  for(const e of canonical){const key=sameKey(e.source,e.trade_id);if(quarantined.has(key))continue;if(!latestByTrade.has(key)||latestByTrade.get(key).version<e.version)latestByTrade.set(key,e);}
  const compare=(a,b)=>a.source.localeCompare(b.source)||a.trade_id.localeCompare(b.trade_id)||(a.version||0)-(b.version||0);
  const latest=[...latestByTrade.values()].sort(compare);
  return {latest,active:latest.filter(e=>e.status==='ACTIVE'),quarantined:[...quarantined.values()].sort(compare),conflicting_keys:conflictingKeys.sort(compare),input_records:events.length,distinct_event_keys:groups.size,replay_records:events.length-[...groups.values()].reduce((n,m)=>n+m.size,0)};
}
function contextPacket(state,source,trade_id){
  if(state.quarantined.some(e=>e.source===source&&e.trade_id===trade_id))return {source,trade_id,serving_eligible:false,reason:'Conflicting business-version payloads require review.',evidence:null};
  const evidence=state.latest.find(e=>e.source===source&&e.trade_id===trade_id);
  if(!evidence)return {source,trade_id,serving_eligible:false,reason:'No validated event exists in this snapshot.',evidence:null};
  return {source,trade_id,serving_eligible:true,reason:'Validated latest state; a cancellation must not be described as active.',evidence:{...evidence}};
}
function naiveActive(events){const rows=new Map();for(const e of [...events].sort((a,b)=>a.arrival_seq-b.arrival_seq)){if(e.status==='ACTIVE')rows.set(sameKey(e.source,e.trade_id),e);}return [...rows.values()];}
window.TradeStateLab={reconstruct,contextPacket,naiveActive};
const $=id=>document.getElementById(id);
const formatMoney=e=>new Intl.NumberFormat('en-US',{style:'currency',currency:e.currency}).format(e.notional_minor/100)+' '+e.currency;
let fixtures=[],current,workingEvents=[],replayRuns=0;
function textCell(row,text,className){const cell=document.createElement('td');cell.textContent=text;if(className)cell.className=className;row.append(cell);return cell;}
function showResult(id,rows,empty){const target=$(id);target.replaceChildren();if(!rows.length){const p=document.createElement('div');p.className='result-values';p.textContent=empty;target.append(p);return;}for(const row of rows){const p=document.createElement('div');p.className='result-values';p.textContent=row.trade_id+' · '+formatMoney(row);const detail=document.createElement('small');detail.textContent='Source '+row.source+' · version '+row.version;p.append(detail);target.append(p);}}
function render(){
  const state=reconstruct(workingEvents),naive=naiveActive(workingEvents);
  $('scenario-title').textContent=current.title;$('scenario-description').textContent=current.description;
  $('input-count').textContent=state.input_records;$('key-count').textContent=state.distinct_event_keys;$('replay-count').textContent=state.replay_records;
  $('event-rows').replaceChildren();
  for(const e of workingEvents){const row=document.createElement('tr');textCell(row,e.source+' / '+e.trade_id);textCell(row,e.version);textCell(row,e.arrival_seq);const cell=textCell(row,'');const badge=document.createElement('span');badge.className='badge'+(e.status==='CANCELLED'?' cancelled':'');badge.textContent=e.status;cell.append(badge);textCell(row,formatMoney(e),'money');$('event-rows').append(row);}
  showResult('naive-result',naive,'No active rows');
  showResult('correct-result',state.active,state.quarantined.length?'Review required · no served state':'No active trade');
  const notes={
    'late-arrival':['Version 1 arrived last and incorrectly replaced version 2.','Business version 2 remains current, regardless of arrival order.'],
    'cancellation':['Removing the cancellation first resurrected version 1.','Latest version 2 is CANCELLED; the active result is empty.'],
    'replay':['The active view can look fine while a blind raw append still duplicates events.','Exact business-event replays do not add another canonical fact.'],
    'conflict':['The last arrival hides a disagreement about the same event identity.','The conflicting trade is quarantined; the evidence packet is ineligible.']
  };
  $('naive-note').textContent=notes[current.id][0];$('correct-note').textContent=notes[current.id][1];
  $('context-packet').textContent=JSON.stringify(contextPacket(state,'SIM','T1'),null,2);
  $('lab-message').textContent=replayRuns?'Input replayed '+replayRuns+' time'+(replayRuns===1?'':'s')+'. Compare the raw count with the unchanged business state.':'Choose a scenario or replay this input to inspect the policy.';
  document.querySelectorAll('[data-case]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.case===current.id)));
}
function selectCase(id){current=fixtures.find(c=>c.id===id);workingEvents=current.events.map(e=>({...e}));replayRuns=0;render();}
document.querySelectorAll('[data-case]').forEach(button=>button.addEventListener('click',()=>selectCase(button.dataset.case)));
$('replay-button').addEventListener('click',()=>{if(!current)return;const max=Math.max(...workingEvents.map(e=>e.arrival_seq));workingEvents.push(...current.events.map((e,i)=>({...e,arrival_seq:max+i+1})));replayRuns++;render();});
$('copy-sql').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('sql-code').textContent);$('copy-sql').textContent='Copied';setTimeout(()=>{$('copy-sql').textContent='Copy SQL';},1800);}catch{$('copy-sql').textContent='Select code below';$('sql-code').focus();}});
fetch('fixtures.json').then(response=>{if(!response.ok)throw new Error('Fixture unavailable');return response.json();}).then(data=>{fixtures=data;window.TradeStateLab.fixtures=fixtures;selectCase('late-arrival');}).catch(()=>{$('scenario-title').textContent='Interactive fixture could not load';$('scenario-description').textContent='The note, downloadable SQL and source package remain available.';});
