/* Dependency-free Python editor helpers for this local prototype. */
(function () {
  const escape = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const keywords = new Set('and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield match case'.split(' '));
  const builtins = new Set('abs all any bool dict enumerate float input int len list map max min open print range reversed round set sorted str sum tuple type zip'.split(' '));
  const methods = 'append clear copy count extend get index insert items join keys lower pop remove replace reverse sort split startswith strip upper values'.split(' ');
  const pairs = {'(':')','[':']','{':'}'};
  const token = /#.*|"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b/g;

  function highlightLine(line) {
    let out = '', last = 0;
    token.lastIndex = 0;
    for (const match of line.matchAll(token)) {
      const word = match[0];
      out += escape(line.slice(last, match.index));
      let kind = word.startsWith('#') ? 'comment'
        : word.startsWith('"') || word.startsWith("'") ? 'string'
        : /^\d/.test(word) ? 'number'
        : keywords.has(word) ? 'keyword'
        : builtins.has(word) ? 'builtin' : '';
      out += kind ? `<span class="tok-${kind}">${escape(word)}</span>` : escape(word);
      last = match.index + word.length;
    }
    return out + escape(line.slice(last));
  }

  function completeCandidates(source, caret) {
    const before = source.slice(0, caret);
    const match = /([A-Za-z_]\w*)$/.exec(before);
    if (!match || match[1].length < 2) return [];
    const prefix = match[1];
    const dotted = before.slice(0, -prefix.length).endsWith('.');
    const local = new Set();
    const captureNames = text => {
      for (const name of text.split(',')) {
        const clean = name.trim();
        if (/^[A-Za-z_]\w*$/.test(clean)) local.add(clean);
      }
    };
    for (const line of source.split('\n')) {
      const assignment = /^\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*=(?!=)/.exec(line);
      const loop = /^\s*(?:async\s+)?for\s+([\w,\s]+?)\s+in\b/.exec(line);
      const definition = /^\s*def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)/.exec(line);
      if (assignment) captureNames(assignment[1]);
      if (loop) captureNames(loop[1]);
      if (definition) {local.add(definition[1]);captureNames(definition[2]);}
    }
    const options = dotted ? methods : [...local, ...keywords, ...builtins];
    return [...new Set(options)].filter(x => x !== prefix && x.startsWith(prefix)).slice(0, 7);
  }

  function indentation(source, caret) {
    const line = source.slice(0, caret).split('\n').at(-1);
    const current = /^\s*/.exec(line)[0];
    return '\n' + current + (line.trimEnd().endsWith(':') ? '    ' : '');
  }

  function pairEdit(source, start, end, opener) {
    const inner=source.slice(start,end);
    return {value: opener+inner+pairs[opener], start:start+1, end:start+1+inner.length};
  }

  function attach(textarea, save) {
    const pane = textarea.closest('.editor-pane');
    const mirror = pane.querySelector('.editor-highlight');
    const gutter = pane.parentElement.querySelector('.editor-gutter');
    const menu = pane.querySelector('.completion-menu');
    let suggestions = [], selected = 0;

    function paint() {
      const lines = textarea.value.split('\n');
      mirror.innerHTML = lines.map(highlightLine).join('\n') + (textarea.value.endsWith('\n') ? ' ' : '');
      gutter.textContent = lines.map((_, i) => i + 1).join('\n');
      mirror.scrollTop = textarea.scrollTop;
      mirror.scrollLeft = textarea.scrollLeft;
      gutter.scrollTop = textarea.scrollTop;
    }
    function hide() { suggestions = []; menu.hidden = true; menu.innerHTML = ''; }
    function show() {
      suggestions = completeCandidates(textarea.value, textarea.selectionStart);
      selected = 0;
      if (!suggestions.length || textarea.selectionStart !== textarea.selectionEnd) return hide();
      menu.innerHTML = suggestions.map((word, i) => `<button type="button" role="option" aria-selected="${i===selected}" data-index="${i}">${escape(word)}</button>`).join('');
      menu.hidden = false;
      const before = textarea.value.slice(0, textarea.selectionStart);
      const line = before.split('\n').at(-1);
      const row = before.split('\n').length - 1;
      const style = getComputedStyle(textarea);
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      ctx.font = style.font;
      const x = parseFloat(style.paddingLeft) + ctx.measureText(line).width - textarea.scrollLeft;
      const y = parseFloat(style.paddingTop) + row * parseFloat(style.lineHeight) - textarea.scrollTop + parseFloat(style.lineHeight);
      menu.style.left = `${Math.max(8, Math.min(x, pane.clientWidth - 210))}px`;
      menu.style.top = `${Math.max(8, Math.min(y, pane.clientHeight - 42))}px`;
    }
    function insert(text) {
      if (textarea.readOnly) return;
      textarea.setRangeText(text, textarea.selectionStart, textarea.selectionEnd, 'end');
      textarea.dispatchEvent(new Event('input', {bubbles: true}));
    }
    function accept(index) {
      if (textarea.readOnly) return;
      const word = suggestions[index];
      if (!word) return;
      const start = textarea.selectionStart - /([A-Za-z_]\w*)$/.exec(textarea.value.slice(0, textarea.selectionStart))[0].length;
      textarea.setRangeText(word, start, textarea.selectionStart, 'end');
      textarea.dispatchEvent(new Event('input', {bubbles: true}));
      hide(); textarea.focus();
    }
    textarea.addEventListener('input', () => {save(textarea.value); paint(); show();});
    textarea.addEventListener('scroll', () => {mirror.scrollTop=textarea.scrollTop;mirror.scrollLeft=textarea.scrollLeft;gutter.scrollTop=textarea.scrollTop; if (!menu.hidden) show();});
    textarea.addEventListener('click', show);
    textarea.addEventListener('keydown', event => {
      if (textarea.readOnly) { hide(); return; }
      if(!event.ctrlKey && !event.metaKey && !event.altKey && pairs[event.key]){
        event.preventDefault();
        const start=textarea.selectionStart,end=textarea.selectionEnd;
        const edit=pairEdit(textarea.value,start,end,event.key);
        textarea.setRangeText(edit.value,start,end,'end');
        textarea.setSelectionRange(edit.start,edit.end);
        textarea.dispatchEvent(new Event('input',{bubbles:true}));hide();return;
      }
      if(!event.ctrlKey && !event.metaKey && !event.altKey && Object.values(pairs).includes(event.key)
         && textarea.selectionStart===textarea.selectionEnd && textarea.value[textarea.selectionStart]===event.key){
        event.preventDefault();textarea.setSelectionRange(textarea.selectionStart+1,textarea.selectionStart+1);hide();return;
      }
      if(event.key==='Backspace' && textarea.selectionStart===textarea.selectionEnd){
        const pos=textarea.selectionStart;
        if(pos>0 && pairs[textarea.value[pos-1]]===textarea.value[pos]){
          event.preventDefault();textarea.setRangeText('',pos-1,pos+1,'start');
          textarea.dispatchEvent(new Event('input',{bubbles:true}));hide();return;
        }
      }
      if (event.key === 'Escape' && !menu.hidden) {event.preventDefault(); hide(); return;}
      if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && !menu.hidden) {
        event.preventDefault(); selected = (selected + (event.key === 'ArrowDown' ? 1 : -1) + suggestions.length) % suggestions.length;
        menu.querySelectorAll('[role="option"]').forEach((item, i) => item.setAttribute('aria-selected', i===selected)); return;
      }
      if ((event.key === 'Tab' || event.key === 'Enter') && !menu.hidden) {event.preventDefault(); accept(selected); return;}
      if (event.key === 'Tab') {event.preventDefault();insert('    ');hide();return;}
      if (event.key === 'Enter') {event.preventDefault();insert(indentation(textarea.value,textarea.selectionStart));hide();return;}
    });
    menu.addEventListener('mousedown', event => event.preventDefault());
    menu.addEventListener('click', event => {
      const item=event.target.closest('[data-index]');
      if (item) accept(Number(item.dataset.index));
    });
    paint();
  }

  window.RumbleEditor = {attach, highlightLine, completeCandidates, indentation, pairEdit};
})();
