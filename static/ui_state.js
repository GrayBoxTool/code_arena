/* Preserve interaction state while polling replaces a page's content. */
(() => {
  function key(el,root){
    if(el.id)return '#'+el.id;
    if(el.dataset.focusKey)return 'focus:'+el.dataset.focusKey;
    if(el.dataset.scroll)return 'scroll:'+el.dataset.scroll;
    if(el.dataset.key)return 'key:'+el.dataset.key;
    if(el.tagName==='DETAILS')return 'details:'+el.querySelector('summary')?.textContent;
    if(el.name)return 'field:'+(el.closest('form')?.id||el.closest('form')?.dataset.team||'')+':'+el.name;
    let path=[];
    for(let n=el;n&&n!==root;n=n.parentElement){
      path.unshift(n.tagName+':'+Array.from(n.parentElement?.children||[]).indexOf(n));
    }
    return path.join('/');
  }
  document.addEventListener('input',event=>{if(event.target.matches?.('input,textarea'))event.target.dataset.userDirty='1';});
  function capture(root){
    const active=document.activeElement;
    const entries=[...root.querySelectorAll('*')].map(el=>({key:key(el,root),scrollTop:el.scrollTop,scrollLeft:el.scrollLeft,
      open:el.tagName==='DETAILS'?el.open:undefined,focused:active===el,
      value:el.matches('input,textarea,select')&&(active===el||el.dataset.userDirty==='1')?el.value:undefined,
      checked:el.matches('input[type=checkbox]')&&(active===el||el.dataset.userDirty==='1')?el.checked:undefined,
      dirty:el.dataset.userDirty,type:el.type,start:el.selectionStart,end:el.selectionEnd}));
    return {x:window.scrollX,y:window.scrollY,entries};
  }
  function restore(root,saved){
    if(!saved)return;
    const map=new Map();for(const el of root.querySelectorAll('*'))map.set(key(el,root),el);
    for(const old of saved.entries){
      const el=map.get(old.key);if(!el)continue;
      if(old.open!==undefined)el.open=old.open;
      if(old.value!==undefined){el.value=old.value;if(old.dirty)el.dataset.userDirty=old.dirty;}
      if(old.checked!==undefined)el.checked=old.checked;
      if(old.type==='text'&&el.matches('input[data-password]'))el.type='text';
      if(old.focused){el.focus({preventScroll:true});try{el.setSelectionRange(old.start,old.end);}catch(_){}}
      el.scrollTop=old.scrollTop;el.scrollLeft=old.scrollLeft;
    }
    window.scrollTo(saved.x,saved.y);
  }
  window.RumbleUI={capture,restore,selectIsActive:root=>root.contains(document.activeElement)&&document.activeElement?.tagName==='SELECT'};
})();
