const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
let listener,position={x:50,y:850};
function node(id,kind='DIV',extra={}){return {id,tagName:kind,dataset:{},scrollTop:0,scrollLeft:0,selectionStart:null,selectionEnd:null,matches:()=>false,querySelector:()=>null,focus(){document.activeElement=this},setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b},...extra};}
const oldInput=node('draft','INPUT',{value:'작성 중인 이름',selectionStart:3,selectionEnd:7,type:'text',dataset:{userDirty:'1'},matches:q=>q==='input,textarea,select'});
const oldDetails=node('hint','DETAILS',{open:true});
const oldScroller=node('problem','DIV',{scrollTop:520,scrollLeft:30});
const document={activeElement:oldInput,addEventListener(type,f){listener=f}};
const window={scrollX:position.x,scrollY:position.y,scrollTo(x,y){position={x,y}}};
const context=vm.createContext({document,window,Map});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/ui_state.js'),'utf8'),context);
const root={querySelectorAll:()=>[oldInput,oldDetails,oldScroller],contains:()=>true};
const saved=window.RumbleUI.capture(root);
const newInput=node('draft','INPUT',{value:'서버의 오래된 값',matches:q=>q==='input,textarea,select'});
const newDetails=node('hint','DETAILS',{open:false}),newScroller=node('problem');
root.querySelectorAll=()=>[newInput,newDetails,newScroller];window.RumbleUI.restore(root,saved);
assert.equal(newInput.value,'작성 중인 이름');assert.equal(document.activeElement,newInput);assert.equal(newInput.selectionStart,3);assert.equal(newInput.selectionEnd,7);
assert.equal(newDetails.open,true);assert.equal(newScroller.scrollTop,520);assert.equal(newScroller.scrollLeft,30);assert.deepEqual(position,{x:50,y:850});
document.activeElement=node('level','SELECT');assert.equal(window.RumbleUI.selectIsActive(root),true);
console.log('UI state: open hints, dirty draft, focus, caret, page and inner scroll survive polling; active select pauses repaint: OK');
