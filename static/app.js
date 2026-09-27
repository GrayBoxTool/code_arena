const app = document.querySelector('#app');
const identity = document.querySelector('#identity');
let auth = sessionStorage.getItem('rumble_token') || '';
let state = null;
let busy = false;
let noticeTimer;
let shownPhase = null;

const esc = (x) => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labelRound = r => r === 6 ? '결승' : r ? `럼블 ${r} / 5 라운드` : '시작 전';
const fmt = n => Number(n || 0).toLocaleString('ko-KR');
const codeKey = s => `draft:${s.me.team_id}:${s.match?.id}:${s.me.level}`;
const lobbyKey = s => `lobby:${s.me.id}:${s.match?.id}`;

function playerPhase(s, now = Date.now()/1000) {
  const m = s.match, p = s.problems[0];
  if (!m || !p || sessionStorage.getItem(lobbyKey(s))) return 'lobby';
  const solved = s.solves.some(x => x.problem_id===p.id && x.team_id===s.me.team_id);
  if (m.status==='pending') return 'lobby';
  if (solved) return now < m.end_at && m.status==='open' ? 'solved-wait' : 'solved-ready';
  if (now >= m.end_at || m.status==='closed') {
    if (now < m.end_at + 10) return 'failed';
    sessionStorage.setItem(lobbyKey(s), '1');
    return 'lobby';
  }
  return 'play';
}

function toast(message) {
  const el = document.querySelector('#toast'); el.textContent = message; el.style.display = 'block';
  clearTimeout(noticeTimer); noticeTimer = setTimeout(() => el.style.display = 'none', 4500);
}
async function api(path, body) {
  const base = (window.RUMBLE_API_BASE_URL || '').replace(/\/$/, '');
  const response = await fetch(base + '/api/' + path, {method: body === undefined ? 'GET' : 'POST',
    headers: {'Authorization': `Bearer ${auth}`, ...(body === undefined ? {} : {'Content-Type':'application/json'})},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '요청에 실패했습니다.');
  return data;
}
function loginView() {
  identity.textContent = '프로토타입';
  app.innerHTML = `<section class="login panel"><div class="eyebrow">5 TEAMS · 25 PLAYERS · 15 PROBLEMS</div>
    <h1>경기에 입장하세요.</h1><p>운영자 또는 선수 참가 코드를 입력하면 해당 화면이 열립니다.</p>
    <form id="login-form"><label for="token">참가 코드</label><div class="login-row"><input id="token" type="password" required autocomplete="off" placeholder="운영자에게 받은 참가 코드"><button class="primary">입장</button></div></form>
    <p class="login-note">참가 코드는 운영자에게 개인별로 받으세요.</p></section>`;
  app.querySelector('form').onsubmit = async e => {
    e.preventDefault(); auth = app.querySelector('#token').value.trim();
    try {state = await api('state'); sessionStorage.setItem('rumble_token', auth); render();}
    catch (error) {auth = ''; toast(error.message);}
  };
}
function profileView(s) {
  shownPhase='profile';
  app.innerHTML=`<section class="login panel"><div class="eyebrow">${esc(s.standings.find(t=>t.id===s.me.team_id)?.name || 'TEAM')}</div>
    <h1>선수 이름 설정</h1><p>이 참가 코드에서 사용할 이름을 입력하세요. 팀원에게도 이 이름으로 표시됩니다.</p>
    <form id="profile-form"><label for="player-name">이름</label><div class="login-row">
      <input id="player-name" maxlength="20" minlength="2" autocomplete="nickname" required placeholder="2~20자">
      <button class="primary" type="submit">이름 저장</button></div>
      ${s.me.captain_available ? `<label class="captain-check"><input id="captain-choice" type="checkbox" ${s.me.force_captain?'checked disabled':''}> 제가 팀장을 맡겠습니다${s.me.force_captain?' · 마지막 입장 선수로 자동 지정':''}</label>` : '<p class="meta">이 팀의 팀장은 이미 지정되었습니다.</p>'}</form></section>`;
  app.querySelector('#profile-form').onsubmit=async event=>{
    event.preventDefault();
    if(busy)return;busy=true;
    try{state=await api('profile',{name:app.querySelector('#player-name').value,
      captain: Boolean(app.querySelector('#captain-choice')?.checked)});render();toast('이름이 설정되었습니다.');}
    catch(error){toast(error.message);}finally{busy=false;}
  };
}

function teamSetupView(s) {
  shownPhase='team-setup';
  const setup=s.team_setup;
  app.innerHTML=`<section class="panel team-setup"><div class="eyebrow">CAPTAIN · TEAM IDENTITY</div>
    <h1>팀 이름과 로고를 정하세요</h1><p>팀장은 대기실에 들어가기 전에 팀 이름과 로고 하나를 확정합니다.</p>
    <form id="team-name-form"><label for="team-name">팀명</label><div class="login-row">
      <input id="team-name" minlength="2" maxlength="24" required value="${setup.named?esc(setup.name):''}" placeholder="우리 팀 이름">
      <button class="primary">팀명 저장</button></div></form>
    ${setup.named?`<div class="logo-section"><h2>${esc(setup.name)}의 로고 후보</h2>
      ${setup.candidates.length?`<p class="meta">${setup.candidates[0].source==='임시 로고'?'API 키가 없어 임시 로고가 표시됩니다.':'AI 생성 로고입니다.'} 후보 하나를 선택하면 팀 설정이 완료됩니다.</p>
        <div class="logo-options">${setup.candidates.map(x=>`<button type="button" class="logo-option" data-slot="${x.slot}">
          <img src="${x.data_uri}" alt="로고 후보 ${x.slot}"><span>후보 ${x.slot} · ${esc(x.source)}</span></button>`).join('')}</div>`
        : `<button class="primary" id="generate-logos" type="button">로고 후보 3개 만들기</button>`}</div>`:''}
    </section>`;
  app.querySelector('#team-name-form').onsubmit=async e=>{
    e.preventDefault();if(busy)return;busy=true;
    try{state=await api('team/name',{name:app.querySelector('#team-name').value});render();}
    catch(error){toast(error.message);}finally{busy=false;}
  };
  const generate=app.querySelector('#generate-logos');
  if(generate)generate.onclick=async()=>{
    if(busy)return;busy=true;generate.disabled=true;generate.textContent='후보 생성 중…';
    try{state=await api('team/logos',{});render();}
    catch(error){toast(error.message);generate.disabled=false;generate.textContent='다시 시도';}finally{busy=false;}
  };
  app.querySelectorAll('[data-slot]').forEach(button=>button.onclick=async()=>{
    if(busy)return;busy=true;
    try{state=await api('team/choose-logo',{slot:Number(button.dataset.slot)});render();toast('팀 이름과 로고가 확정되었습니다.');}
    catch(error){toast(error.message);}finally{busy=false;}
  });
}

function selectionCard(s) {
  const choice=s.next_selection;
  if(!choice)return '';
  const mine=choice.members.find(x=>x.id===s.me.id);
  const occupied=new Map(choice.members.filter(x=>x.level!==null).map(x=>[x.level,x.name]));
  return `<section class="panel selection-card"><div><div class="eyebrow">NEXT ROUND · ${choice.round===6?'FINAL':choice.round}</div>
    <h2>다음 경기 레벨 선택</h2><p>팀원마다 한 레벨씩 선택합니다. 선택하지 않은 레벨은 경기 시작 때 남은 팀원에게 무작위로 배정됩니다.</p></div>
    <div><label for="level-choice">내 레벨</label><select id="level-choice">
      <option value="" ${mine?.level===null?'selected':''}>선택하지 않음 · 무작위 배정</option>
      ${[1,2,3,4,5].map(level=>`<option value="${level}" ${mine?.level===level?'selected':''}
         ${occupied.has(level)&&mine?.level!==level?'disabled':''}>Lv${level} · ${fmt(s.rewards[level])}점${occupied.has(level)&&mine?.level!==level?' · '+esc(occupied.get(level))+' 선택':''}</option>`).join('')}
    </select><div class="selection-roster">${choice.members.map(x=>`<span>${esc(x.name)} <strong>${x.level?'Lv'+x.level:'미선택'}</strong></span>`).join('')}</div></div></section>`;
}
function lobbyArena(s) {
  const own=s.lobby_teams.find(t=>t.id===s.me.team_id);
  const opponent=s.lobby_teams.find(t=>t.id!==s.me.team_id);
  const teamCard=(team,side)=>`<section class="arena-team ${side}">
    <div class="arena-team-head">${team.logo?`<img src="${team.logo}" alt="${esc(team.name)} 로고">`:'<div class="arena-no-logo">?</div>'}
      <div><span class="kicker">${side==='own'?'MY TEAM':'OPPONENT'}</span><h2>${esc(team.name)}</h2></div></div>
    <div class="arena-roster">${team.roster.map((member,index)=>`<div class="arena-member ${member.id===s.me.id?'self':''}">
      <span class="arena-index">${String(index+1).padStart(2,'0')}</span><span>${esc(member.name)}${member.captain?' <small>팀장</small>':''}</span>
      <strong>${member.selected_level?'LV '+member.selected_level:'선택 전'}</strong></div>`).join('')}</div></section>`;
  return `<section class="panel arena"><div class="eyebrow">NEXT MATCH · ${s.next_match?labelRound(s.next_match.round):'대진 대기'}</div>
    <div class="arena-grid">${teamCard(own,'own')}<div class="arena-center"><div>VS</div>
      <p>${opponent?'다음 상대와 같은 레벨의 문제를 풉니다.':s.round===5?'결승 진출팀 확정 대기':'이번 라운드는 휴식 또는 대진 대기'}</p>
      <span>5분 제한 · 선착 100% / 후착 50%</span></div>
      ${opponent?teamCard(opponent,'opponent'):'<section class="arena-bye">상대 팀 대기 중</section>'}</div></section>`;
}
function board(s) {
  return `<section class="panel full-board"><h2 class="section-title">럼블 순위 · 승점 포인트</h2><div class="tablewrap"><table class="board">
  <thead><tr><th>순위</th><th>팀</th><th>승점</th><th>승리</th><th>해결</th><th>사용 가능 solve</th></tr></thead><tbody>
  ${s.standings.map((t, i) => `<tr class="${s.me.team_id===t.id?'mine':''}"><td>${i+1}</td><td>${esc(t.name)}</td><td>${fmt(t.points)}</td><td>${t.wins}</td><td>${t.solved}</td><td>${fmt(t.credit)}</td></tr>`).join('')}
  </tbody></table></div></section>`;
}
function matchCards(s) {
  return `<div class="match-list">${s.matches.map(m => `<section class="panel match-card"><span class="kicker">MATCH ${m.id} · SET ${m.problem_set}</span>
  <p><strong>${esc(m.team_a_name)} <span class="meta">VS</span> ${esc(m.team_b_name)}</strong></p>
  <div class="scores">${fmt(m.scores[m.team_a])} : ${fmt(m.scores[m.team_b])}</div>
  <span class="meta">${m.status==='open'?'진행 중':'종료'} · ${m.status==='open'?'정답 시각에 따라 100% / 50%':'승점 확정'}</span></section>`).join('')}</div>`;
}
function countdown(m) {
  if (!m || !m.end_at || m.status === 'pending') return '대기';
  let sec = Math.max(0, Math.ceil(m.end_at - Date.now()/1000));
  return `${String(Math.floor(sec/60)).padStart(2,'0')}:${String(sec%60).padStart(2,'0')}`;
}
function adminView(s) {
  const final = s.round === 6 && s.matches.length && s.matches[0].status === 'closed';
  const m = s.matches[0];
  const winner = final && m.scores[m.team_a] !== m.scores[m.team_b]
    ? (m.scores[m.team_a] > m.scores[m.team_b] ? m.team_a_name : m.team_b_name) : null;
  app.innerHTML = `<div class="topline"><div><div class="eyebrow">TOURNAMENT CONTROL</div><h1>${labelRound(s.round)}</h1></div>
   <div><div class="meta">남은 시간</div><div class="clock" id="clock">${countdown(m)}</div></div></div>
   ${winner ? `<section class="panel metric"><label>결승 우승팀</label><strong>${esc(winner)}</strong></section>` : final ? `<p>결승 동점입니다. 재경기나 동점 처리 규칙을 운영자가 결정하세요.</p>` : ''}
   <div class="admin-action"><button class="primary" id="advance" ${s.round>=6?'disabled':''}>${s.round===0?'럼블 1라운드 시작':s.round===5?'결승 진출팀 확정 · 결승 시작':'현재 라운드 종료 · 다음 라운드 시작'}</button>
   <button class="secondary" id="close" ${s.round===0 || s.matches.every(m=>m.status==='closed')?'disabled':''}>현재 라운드 종료</button></div>
   ${s.round===0?`<section class="panel empty"><h2>5팀 단일 리그를 시작할 준비가 되었습니다.</h2><p>각 라운드에 두 경기가 동시에 열리고 한 팀은 쉽니다.</p></section>`:matchCards(s)}
   ${board(s)}<p class="meta">매 경기의 두 팀은 같은 문제 세트를 받습니다. 세트는 1 → 2 → 3 → 1 → 2 → 결승 3 순서입니다.</p>`;
  app.querySelector('#advance').onclick = () => adminAction('advance');
  app.querySelector('#close').onclick = () => adminAction('close');
}
function playerView(s) {
  const my = s.standings.find(t => t.id === s.me.team_id);
  const m = s.match;
  const p = s.problems[0];
  const solved = p && s.solves.find(x => x.problem_id===p.id && x.team_id===s.me.team_id);
  const enemySolved = p && s.solves.find(x => x.problem_id===p.id && x.team_id!==s.me.team_id);
  const opp = m ? (m.team_a===s.me.team_id ? m.team_b_name : m.team_a_name) : '대기';
  const phase = playerPhase(s);
  shownPhase = phase;
  const top = `<div class="topline"><div><div class="eyebrow">${labelRound(s.round)} · ${esc(s.me.name)}</div><h1>${esc(my.name)} ${m?'vs '+esc(opp):''}</h1></div>
   <div><div class="meta">남은 시간</div><div class="clock" id="clock">${countdown(m)}</div></div></div>
   <div class="scorestrip"><section class="panel metric"><label>팀 승점</label><strong>${fmt(my.points)}</strong></section>
    <section class="panel metric"><label>사용 가능 solve</label><strong>${fmt(my.credit)}</strong></section>
    <section class="panel metric"><label>담당 레벨</label><strong>${s.me.level?'LV '+s.me.level:'배정 전'}</strong></section>
    <section class="panel metric"><label>현재 상태</label><strong>${solved?'해결':phase==='play'?'도전 중':'대기'}</strong></section></div>`;
  if (phase !== 'play') {
    let content;
    if (phase==='solved-wait' || phase==='solved-ready') {
      content = `<section class="panel result-screen" role="status"><div class="result-symbol">✓</div>
        <h2>정답 제출 완료</h2><p>${esc(p.title)} · 승점 ${fmt(solved.win_points)}점 획득</p>
        <div class="result-points">SOLVE +${fmt(p.reward)} P</div>
        ${phase==='solved-wait' ? `<p>제한시간이 끝날 때까지 이 화면에서 기다립니다.<br>남은 시간 <strong class="clock" id="result-clock">${countdown(m)}</strong></p>`
        : `<p>경기가 종료되었습니다. 대기실에서 다음 경기를 기다리세요.</p><button class="primary" id="return-lobby">대기실로 돌아가기</button>`}</section>`;
    } else if (phase==='failed') {
      content = `<section class="panel result-screen failed" role="alert"><div class="result-symbol">!</div>
        <h2>제한시간이 끝났습니다</h2><p>이번 문제의 정답 코드를 제출하지 못했습니다.</p>
        <p>${s.last_submission?`마지막 결과: ${esc(s.last_submission.verdict.split('\n')[0])}`:'제출 기록이 없습니다.'}</p>
        <div class="result-points">획득 승점 0 P</div>
        <p><strong class="failure-count" id="failure-count">${Math.max(0, Math.ceil(m.end_at+10-Date.now()/1000))}</strong>초 후 대기실로 자동 이동합니다.</p></section>`;
    } else {
      content = `<section class="panel result-screen" role="status"><div class="result-symbol">CR</div>
        <h2>대기실</h2><p>${m?'이번 경기가 끝났습니다. 운영자가 다음 라운드를 열면 새 문제가 표시됩니다.':'다음 경기 배정을 기다리고 있습니다.'}</p></section>`;
    }
    app.innerHTML = top + content + (phase==='lobby'?lobbyArena(s)+selectionCard(s):'') + board(s) + (m?`<section class="panel full-board"><h2 class="section-title">매치 진행</h2>${matchCards(s)}</section>`:'');
    const button = app.querySelector('#return-lobby');
    if (button) button.onclick = () => {sessionStorage.setItem(lobbyKey(s),'1');render();};
    const selector=app.querySelector('#level-choice');
    if(selector)selector.onchange=async()=>{
      if(busy)return;busy=true;
      try{const updated=await api('selection',{level:selector.value?Number(selector.value):null});state=updated;render();toast('다음 경기 선택을 저장했습니다.');}
      catch(error){toast(error.message);render();}finally{busy=false;}
    };
    return;
  }
  app.innerHTML = top + `${p ? `<div class="player-grid">
    <section class="panel column"><span class="kicker">${esc(p.id)} · LEVEL ${p.level} · ${fmt(p.reward)} P</span><h2 class="problem-title">${esc(p.title)}</h2>
      <p class="problem-statement">${esc(p.statement)}</p><div class="problem-section"><h3>입력</h3><p>${esc(p.input)}</p></div>
      <div class="problem-section"><h3>출력</h3><p>${esc(p.output)}</p></div>
      <div class="problem-section"><h3>예제 입력</h3><pre class="sample">${esc(p.sample_input)}</pre><h3>예제 출력</h3><pre class="sample">${esc(p.sample_output)}</pre></div></section>
    <section class="panel column"><div class="code-label"><h2>Python 풀이</h2><span>stdin → stdout</span></div>
      <p class="editor-help">Tab: 자동완성 또는 들여쓰기 · Enter: 자동 들여쓰기 · Esc: 제안 닫기</p>
      <div class="editor-surface"><div class="editor-gutter" aria-hidden="true"></div><div class="editor-pane">
        <pre class="editor-highlight" aria-hidden="true"></pre>
        <textarea class="editor" id="editor" spellcheck="false" autocomplete="off" autocapitalize="off" aria-label="Python 코드 편집기"></textarea>
        <div class="completion-menu" role="listbox" aria-label="코드 자동완성 제안" hidden></div>
      </div></div>
      <div class="actionrow"><span class="meta">${solved?'내 팀 정답 · +'+solved.win_points+' 승점':enemySolved?'상대 선착 · 지금 해결하면 50% 승점':'먼저 풀면 승점 100%'}</span>
      <button class="primary" id="submit" ${solved||m.status!=='open'||Date.now()/1000>=m.end_at?'disabled':''}>코드 제출</button></div>
      <div class="verdict ${s.last_submission?.verdict==='정답'?'ok':''}" id="verdict">${s.last_submission
        ? esc(`${s.last_submission.verdict}\n${s.last_submission.passed}/${s.last_submission.total}개 채점 파일 통과`)
        : `제출하면 ${p.id}의 예제 및 추가 케이스로 채점합니다.`}</div></section>
    <section class="panel column hint-panel"><h2>힌트 구매</h2><p class="meta">solve포인트는 팀 공동 자산입니다. 팀원이 정답을 제출하면 즉시 적립되어 같은 경기에서 사용할 수 있습니다.</p>
      <div class="hint-list"><button class="secondary hint-btn" data-kind="type"><span>문제 유형</span><strong>${fmt(s.costs.type)} P</strong></button>
      <button class="secondary hint-btn" data-kind="structure"><span>핵심 구조</span><strong>${fmt(s.costs.structure)} P</strong></button>
      <button class="secondary hint-btn" data-kind="assist" ${s.assist_enabled?'':'disabled title="API 키를 설정한 뒤 사용 가능"'}><span>내 코드 AI 조언</span><strong>${fmt(s.costs.assist)} P</strong></button></div>
      ${s.assist_enabled?'':'<p class="meta">AI 기능은 운영자가 API 키를 설정하면 활성화됩니다.</p>'}
      <div class="hint-details" id="hint-details">${s.hints.filter(h=>h.problem_id===p.id).map(h=>`<h3>${esc(({type:'문제 유형',structure:'핵심 구조',assist:'AI 코드 조언'})[h.kind])}</h3>${esc(h.detail)}<br><br>`).join('')}</div></section></div>`
    : `<section class="panel empty"><h2>${m?'이번 라운드는 종료되었거나 준비 중입니다.':'지금은 대기 라운드입니다.'}</h2><p>다음 경기에서 내 레벨의 새 문제가 열립니다. 순위와 팀 포인트를 확인하세요.</p></section>`}
    ${board(s)}${m?`<section class="panel full-board"><h2 class="section-title">매치 진행</h2>${matchCards(s)}</section>`:''}`;
  if (p) {
    const editor = app.querySelector('#editor');
    editor.value = sessionStorage.getItem(codeKey(s)) || `# ${p.title}\n# sys.stdin = open(...)은 필요하지 않습니다.\nT = int(input())\nfor tc in range(1, T + 1):\n    # 이곳에서 한 테스트케이스의 입력을 읽으세요.\n    # answer = ...\n    print(f"#{tc} {answer}")\n`;
    RumbleEditor.attach(editor, value => sessionStorage.setItem(codeKey(s), value));
    app.querySelector('#submit').onclick = submit;
    app.querySelectorAll('[data-kind]').forEach(b => b.onclick = () => buyHint(b.dataset.kind));
  }
}
function render() {
  if (!state) return loginView();
  const oldEditor = app.querySelector('#editor');
  const active = document.activeElement === oldEditor;
  const cursor = active ? [oldEditor.selectionStart, oldEditor.selectionEnd] : null;
  const scroll = oldEditor ? [oldEditor.scrollTop, oldEditor.scrollLeft] : null;
  identity.innerHTML = `${esc(state.me.name)} <button class="secondary" id="logout">나가기</button>`;
  state.me.role === 'admin' ? adminView(state) : !state.me.profile_complete ? profileView(state)
    : state.me.is_captain && !state.team_setup.complete ? teamSetupView(state) : playerView(state);
  document.querySelector('#logout').onclick = () => {auth='';state=null;sessionStorage.removeItem('rumble_token');loginView();};
  const editor = app.querySelector('#editor');
  if (editor && scroll) {editor.scrollTop=scroll[0];editor.scrollLeft=scroll[1];editor.dispatchEvent(new Event('scroll'));}
  if (active && editor) {editor.focus(); editor.setSelectionRange(...cursor);}
}
async function refresh() {
  if (!auth || busy) return;
  try {const updated = await api('state'); if(JSON.stringify(updated)!==JSON.stringify(state)){state=updated;render();}}
  catch (error) {if (error.message.includes('참가 코드')) {auth='';state=null;sessionStorage.removeItem('rumble_token');loginView();} else toast(error.message);}
}
async function submit() {
  if (busy) return; busy=true;
  const code = app.querySelector('#editor').value; const verdict = app.querySelector('#verdict');
  verdict.textContent='채점 중…'; app.querySelector('#submit').disabled=true;
  try {const result = await api('submit', {code}); state=result.state; render(); const box=app.querySelector('#verdict');
    if (box) {box.textContent = `${result.verdict} · ${result.passed}/${result.total} 케이스 통과${result.win_points?' · 승점 +'+result.win_points:''}`; box.classList.toggle('ok',result.verdict==='정답');}
    toast(result.verdict==='정답'?`정답! 승점 +${result.win_points}`:
      result.verdict.startsWith('실행 오류')?'실행 오류가 발생했습니다. 제출 결과에서 확인하세요.':result.verdict);}
  catch(error){
    if (app.contains(verdict)) verdict.textContent=error.message;
    toast(error.message);
    const button=app.querySelector('#submit');
    if (button) button.disabled=false;
  }
  finally{busy=false;}
}
async function buyHint(kind) {
  if (busy) return;
  const found=state.hints.find(h=>h.problem_id===state.problems[0].id && h.kind===kind);
  if (!found && !confirm(`${({type:'문제 유형',structure:'핵심 구조',assist:'AI 코드 조언'})[kind]} 힌트에 팀 solve포인트 ${state.costs[kind]}점을 사용하시겠습니까?`)) return;
  busy=true;
  try {const result=await api('hint',{kind,code:app.querySelector('#editor').value});state=result.state;render();toast(found?'구매한 힌트를 다시 표시했습니다.':'힌트를 열었습니다.');}
  catch(error){toast(error.message);}
  finally{busy=false;}
}
async function adminAction(action) {
  if (busy || !confirm(action==='advance'?'현재 경기를 종료하고 다음 경기를 시작하시겠습니까?':'현재 라운드의 경기를 종료하시겠습니까?')) return;
  busy=true;
  try{state=await api('admin/'+action,{});render();toast('경기 상태가 변경되었습니다.');}
  catch(error){toast(error.message);}
  finally{busy=false;}
}
setInterval(() => {
  if (!state) return;
  const clock=document.querySelector('#clock');
  if(clock) clock.textContent=countdown(state.match || state.matches[0]);
  if (state.me.role==='player' && state.me.profile_complete) {
    const phase=playerPhase(state);
    if (phase!==shownPhase) {render();return;}
    const resultClock=document.querySelector('#result-clock');
    if(resultClock) resultClock.textContent=countdown(state.match);
    const failure=document.querySelector('#failure-count');
    if(failure) failure.textContent=Math.max(0,Math.ceil(state.match.end_at+10-Date.now()/1000));
  }
},1000);
setInterval(refresh,2000);
if (auth) refresh(); else loginView();
