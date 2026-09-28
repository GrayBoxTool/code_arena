const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const stored = new Map();
const sessionStorage = {
  getItem: key => stored.get(key) || null,
  setItem: (key, value) => stored.set(key, value),
  removeItem: key => stored.delete(key),
};
const element = {querySelector: () => ({}),querySelectorAll: () => []};
const intervals = [];
const context = vm.createContext({
  window: {}, sessionStorage, setInterval: (callback, delay) => intervals.push({callback, delay}), clearTimeout: () => {},
  document: {querySelector: () => element},
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/editor.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8'), context);

const editor = context.window.RumbleEditor;
assert.ok(editor.highlightLine('for x in range(3): # loop').includes('tok-keyword'));
assert.ok(editor.highlightLine('print("<tag>")').includes('&lt;tag&gt;'));
assert.equal(editor.indentation('if ready:', 9), '\n    ');
assert.equal(editor.indentation('    for i in items:', 19), '\n        ');
assert.ok(editor.completeCandidates('count, result = 0, 0\nres', 26).includes('result'));
assert.ok(editor.completeCandidates('values.ap', 9).includes('append'));
const bracket = editor.pairEdit('print', 5, 5, '(');
assert.equal(bracket.value, '()');
assert.equal(bracket.start, 6);
const wrapped = editor.pairEdit('foo', 0, 3, '[');
assert.equal(wrapped.value, '[foo]');
assert.equal(wrapped.end, 4);

const phase = vm.runInContext('phase', context);
const timestamp = Date.now()/1000;
const state = {me:{role:'player',profile_complete:true,is_captain:false},phase:'live',
  match:{id:3,settled:false,end_at:timestamp+100},problem:{id:'R1-L1'},solved:false};
assert.equal(phase(state),'play');
state.solved=true;assert.equal(phase(state),'solved');
state.match.settled=true;state.match.end_at=timestamp-1;assert.equal(phase(state),'result');
state.match.end_at=timestamp-11;assert.equal(phase(state),'lobby');
state.phase='finished';assert.equal(phase(state),'result');
state.phase='matching';assert.equal(phase(state),'lobby');
state.me.is_captain=true;state.team_setup={complete:false};assert.equal(phase(state),'team-setup');
state.me.profile_complete=false;assert.equal(phase(state),'profile');
state.me.role='admin';assert.equal(phase(state),'admin');

// Polling must not remount an unchanged captain form; the clock must not render it.
context.document.querySelectorAll=()=>[];
context.Date=Date;
vm.runInContext(`state={epoch:'e',server_time:Date.now()/1000,me:{role:'player',profile_complete:true,is_captain:true},team_setup:{complete:false},events:[]};
view='team-setup';lastTeamSetup=JSON.stringify({me:state.me,setup:state.team_setup});
render=()=>{window.renderCount=(window.renderCount||0)+1;};
ingest({...state,server_time:state.server_time+1});`,context);
intervals.find(x=>x.delay===250).callback();
assert.equal(context.window.renderCount,undefined);

// An unchanged lobby and a focused dropdown survive polling.
vm.runInContext(`state={epoch:'e',server_time:Date.now()/1000,me:{role:'player',profile_complete:true,is_captain:false},phase:'matching',matches:[],standings:[],target_round:1,events:[]};
view='lobby';lastLobby=JSON.stringify({me:state.me,matches:state.matches,standings:state.standings,selection:state.selection,phase:state.phase,target:state.target_round});
ingest({...state,server_time:state.server_time+1});`,context);
assert.equal(context.window.renderCount,undefined);
context.document.activeElement={tagName:'SELECT'};
vm.runInContext(`ingest({...state,standings:[{points:100}]});`,context);
assert.equal(context.window.renderCount,undefined);
console.log('Frontend editor, lifecycle and polling preservation: OK');

// Operator controls show the rehearsal switch and require a tie decision before advancing.
context.requestAnimationFrame=()=>{};
const rehearsalHtml=vm.runInContext(`(function(){adminView({phase:'matching',round:0,target_round:1,rehearsal:true,matches:[],standings:[],events:[],me:{team_id:null},judge_provider:'local',judge_enabled:false,completed_matches:[]});return app.innerHTML})()`,context);
assert.ok(rehearsalHtml.includes('리허설 끄기'));
assert.ok(rehearsalHtml.includes('선수 접속 없이 시작'));
const tieHtml=vm.runInContext(`(function(){adminView({phase:'results',round:5,target_round:5,rehearsal:true,matches:[],standings:[],events:[],me:{team_id:null},judge_provider:'local',judge_enabled:false,completed_matches:[],tie:{required:true,chosen:null,locked_first:1,candidates:[{id:1,name:'첫 팀',points:400,wins:2,solved:3},{id:2,name:'둘째 팀',points:300,wins:1,solved:2},{id:3,name:'셋째 팀',points:300,wins:0,solved:1}]},upcoming:{round:6,pending_tie:true,pairs:[]}});return app.innerHTML})()`,context);
assert.match(tieHtml,/id="next-round" disabled/);
assert.ok(tieHtml.includes('결승 진출 동점 결정'));
assert.ok(tieHtml.includes('첫 팀'));

// Polling a submission acknowledgement must preserve edits made during remote judging.
vm.runInContext(`editState={match:3,rev:2,code:'new edits',dirty:true};pendingSubmission={match:3,rev:2,code:'submitted code'};
acceptDraft({match_id:3,rev:3,code:'submitted code'});`,context);
assert.equal(vm.runInContext('editState.code',context),'new edits');
assert.equal(vm.runInContext('editState.rev',context),3);
assert.equal(vm.runInContext('editState.dirty',context),true);

// Literal input remains copyable; whitespace symbols are a separate view.
const sampleHtml=vm.runInContext(`sampleHTML('예제', '2 3\\n<tag>\\n')`,context);
assert.ok(sampleHtml.includes('2 3\n&lt;tag&gt;'));
assert.ok(!sampleHtml.includes('전체 예제 보기')); 
assert.ok(!sampleHtml.includes('<details')); 
// A final Lv5 player can submit before the Lv4 relay has been revealed.
const nodes=new Map();
element.querySelector=selector=>{
  if(!nodes.has(selector))nodes.set(selector,{style:{}});
  return nodes.get(selector);
};
vm.runInContext(`view='play';busy=false;submitError='';state={draft:{freeze_until:0,cooldown_until:0},match:{round:6},me:{level:5,team_id:1},relay:null,judge_enabled:true,standings:[],hints:[]};updatePlay();`,context);
assert.equal(nodes.get('#submit').disabled,false);
assert.ok(!sampleHtml.includes('표시 생략'));
const longHtml=vm.runInContext(`sampleHTML('긴 예제', Array.from({length:30},(_,i)=>String(i)).join('\\n'))`,context);
assert.ok(!longHtml.includes('전체 예제 보기')); 
assert.ok(longHtml.includes('… (생략) …')); 
console.log('Problem whitespace and early final submission controls: OK');

// Polling inspector updates only code, leaving the problem DOM and both scroll axes intact.
(async()=>{
  const codeNode={textContent:'old',scrollTop:150,scrollLeft:35};
  const selector={value:'draft'};
  const pane={dataset:{subject:'7:FA-L4'},scrollTop:250,
    querySelector:sel=>sel==='.inspect-code'?codeNode:selector};
  Object.defineProperty(pane,'innerHTML',{set(){throw new Error('Inspector remounted during live refresh');}});
  const originalQuery=context.document.querySelector;
  context.document.querySelector=sel=>sel==='#inspector'?pane:originalQuery(sel);
  vm.runInContext(`inspectId=7;inspectMode='draft';api=async()=>({problem:{id:'FA-L4'},draft:{code:'latest code'}});`,context);
  await vm.runInContext('showInspect()',context);
  assert.equal(codeNode.textContent,'latest code');
  assert.equal(codeNode.scrollTop,150);assert.equal(codeNode.scrollLeft,35);assert.equal(pane.scrollTop,250);
  console.log('Inspector live refresh preserves mounted problem and scroll: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
