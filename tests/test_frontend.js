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
const element = {querySelector: () => ({})};
const context = vm.createContext({
  window: {}, sessionStorage, setInterval: () => {}, clearTimeout: () => {},
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

const phase = (state, now) => vm.runInContext('playerPhase', context)(state, now);
const state = {me:{team_id:1},match:{id:3,status:'open',end_at:1000},
  problems:[{id:'S1-L1'}],solves:[]};
assert.equal(phase(state, 800), 'play');
state.solves = [{team_id:1,problem_id:'S1-L1'}];
assert.equal(phase(state, 800), 'solved-wait');
assert.equal(phase(state, 1000), 'solved-ready');
state.solves = [];
assert.equal(phase(state, 1000), 'failed');
assert.equal(phase(state, 1009), 'failed');
assert.equal(phase(state, 1010), 'lobby');
assert.equal(phase(state, 800), 'lobby');

stored.clear();
context.RumbleEditor = editor;
const now = Date.now()/1000;
const screen = {
  me:{team_id:1,name:'블루 1번',level:1}, round:1,
  match:{id:4,team_a:1,team_b:2,team_a_name:'블루',team_b_name:'레드',
    status:'open',end_at:now+60, scores:{1:100,2:0}},
  matches:[], problems:[{id:'S1-L1',title:'충전 기록',reward:100}],
  solves:[{team_id:1,problem_id:'S1-L1',win_points:100}],
  standings:[{id:1,name:'블루',points:100,credit:0,wins:0,solved:1}],
  lobby_teams:[{id:1,name:'블루',logo:null,roster:[{id:1,name:'민수',captain:true,selected_level:1}]}],
  rewards:{1:100,2:150,3:200,4:250,5:300},
};
vm.runInContext('playerView', context)(screen);
assert.match(element.innerHTML,/정답 제출 완료/);
assert.doesNotMatch(element.innerHTML,/return-lobby/);
screen.match.end_at=now-1;
vm.runInContext('playerView', context)(screen);
assert.match(element.innerHTML,/대기실로 돌아가기/);
screen.solves=[];
screen.match.end_at=Date.now()/1000-1;
vm.runInContext('playerView', context)(screen);
assert.match(element.innerHTML,/\d+<\/strong>초 후 대기실로 자동 이동/);
const choices={...screen, next_selection:{round:2,members:[
  {id:1,name:'민수',level:2},{id:2,name:'지우',level:null},
  {id:3,name:'A',level:5},{id:4,name:'B',level:null},{id:5,name:'C',level:null}]}};
choices.me.id=2;
const selection=vm.runInContext('selectionCard',context)(choices);
assert.match(selection,/Lv2/);
assert.match(selection,/민수 선택/);
assert.match(selection,/disabled/);
console.log('Frontend editor and match phases: OK');
