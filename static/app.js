const app=document.querySelector('#app');
const identity=document.querySelector('#identity');
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const base=()=>String(window.RUMBLE_API_BASE_URL||'').replace(/\/$/,'');
const imageURL=url=>url?base()+url:'';
const fmt=n=>Number(n||0).toLocaleString('ko-KR');
const labels={type:'문제 유형',structure:'핵심 구조',assist:'AI 조언',freeze:'빙결',rename:'변수 교란',erase:'코드 절단'};
let auth=sessionStorage.getItem('rumble_token')||'',state=null,busy=false,view='',clockOffset=0;
let accountMode=Boolean(auth),accountData=null,activeLobby=null,authForm='login',recoveryKind='',pendingEmail='',privacyNotice=null,friendWindow=false;
let submitError='',pendingSubmission=null;
let noticeTimer,editState=null,saveTimer,inspectId=null,inspectMode='draft',compareLevel=1,compareMatch=null;
let seenEvent=0,seenEpoch='',lastTeamSetup='',lastLobby='',gaugeWidths=new Map();
let finalChoiceA=null,finalChoiceB=null;
const now=()=>Date.now()/1000+clockOffset;
const roundLabel=r=>r===6?'FINAL':`RUMBLE ${r}`;
const seconds=end=>Math.max(0,Math.ceil((end||0)-now()));
const timeLabel=end=>{const t=seconds(end);return `${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;};
function toast(text){const el=document.querySelector('#toast');el.textContent=text;el.style.display='block';clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>el.style.display='none',5500);}
async function api(path,body){
  let response;
  try{response=await fetch(base()+'/api/'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:`Bearer ${auth}`,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});}
  catch(error){throw new Error('서버에 연결하지 못했습니다. Render 주소와 FRONTEND_ORIGIN을 확인하세요. 잠든 무료 서버는 약 1분 후 다시 시도하세요.');}
  let data;try{data=await response.json();}catch(error){throw new Error('API 응답을 읽지 못했습니다. config.js의 Render 주소와 서버 실행 상태를 확인하세요.');}
  if(response.status===409&&data.draft)return data;
  if(!response.ok)throw new Error(data.error||'요청에 실패했습니다.');
  return data;
}
function body(extra={}){return {epoch:state.epoch,...extra};}
async function action(path,extra={}){if(busy)return;busy=true;try{ingest(await api(path,body(extra)),true);}catch(error){toast(error.message);}finally{busy=false;}}
function authCard(){
  identity.textContent='CODE RUMBLE';
  if(authForm==='register'){
    if(pendingEmail)return `<section class="auth-card panel"><div class="eyebrow">EMAIL VERIFICATION</div><h1>이메일 확인</h1><p>${esc(pendingEmail)}로 보낸 6자리 코드를 입력하세요.</p><form id="verify-register"><input name="code" required inputmode="numeric" maxlength="6" placeholder="인증 코드"><button class="primary">계정 만들기</button></form><button class="text-button" data-auth="login">로그인으로 돌아가기</button></section>`;
    return `<section class="auth-card panel"><div class="eyebrow">CREATE ACCOUNT</div><h1>계정 생성</h1><form id="register-form"><div class="auth-fields"><label>닉네임<input name="nickname" maxlength="20" required></label><label>이름<input name="full_name" maxlength="50" required></label><label>아이디<input name="username" maxlength="20" required autocomplete="username"></label><label>이메일<input name="email" type="email" maxlength="254" required></label><label>비밀번호<input name="password" type="password" minlength="8" maxlength="20" required autocomplete="new-password"></label></div><details class="privacy-details"><summary>개인정보 수집·이용 안내 보기</summary>${privacyNotice?privacyHTML(privacyNotice.notice):'<p>개인정보 안내를 불러오는 중입니다.</p>'}</details><label class="consent-check"><input name="consent" type="checkbox" required> 개인정보 수집·이용 및 계정 운영을 위한 처리에 동의합니다.</label><button class="primary" ${privacyNotice?'':'disabled'}>이메일 인증 후 가입</button></form><button class="text-button" data-auth="login">로그인으로 돌아가기</button></section>`;
  }
  if(authForm==='recovery'){
    const start=!pendingEmail;
    return `<section class="auth-card panel"><div class="eyebrow">ACCOUNT RECOVERY</div><h1>${recoveryKind==='username'?'아이디 찾기':'비밀번호 재설정'}</h1>${start?`<form id="recovery-start"><label>가입 시 등록한 이메일<input name="email" type="email" maxlength="254" autocomplete="email" required></label><p class="form-hint">계정 생성 때 등록하고 이메일 인증을 마친 주소로 인증 코드를 보냅니다.</p><button class="primary">인증 코드 받기</button></form>`:`<p>${esc(pendingEmail)}로 보낸 인증 코드를 입력하세요.</p><form id="recovery-finish"><input name="code" required inputmode="numeric" maxlength="6" placeholder="인증 코드">${recoveryKind==='password'?'<label>새 비밀번호<input name="new_password" type="password" minlength="8" maxlength="20" required></label>':''}<button class="primary">${recoveryKind==='username'?'아이디 확인':'비밀번호 변경'}</button></form>`}<button class="text-button" data-auth="login">로그인으로 돌아가기</button></section>`;
  }
  return `<section class="auth-card login panel"><div class="eyebrow">CODE RUMBLE · ALGORITHM ARENA</div><h1>로그인</h1><form id="login-form"><label>아이디<input name="username" autocomplete="username" maxlength="20" required></label><label>비밀번호<input name="password" type="password" autocomplete="current-password" maxlength="20" required></label><button class="primary">로그인</button></form><div class="auth-links"><button data-auth="register">계정 생성</button><button data-recover="username">아이디 찾기</button><button data-recover="password">비밀번호 찾기</button></div></section>`;
}
function privacyHTML(n){return `<h3>${esc(n.controller)} 개인정보 수집·이용 안내</h3><p><b>수집 항목</b><br>${esc(n.items)}</p><p><b>이용 목적</b><br>${esc(n.purposes)}</p><p><b>저장 위치와 방법</b><br>${esc(n.storage||'운영자가 관리하는 서비스 서버의 데이터베이스에 저장합니다.')}</p><p><b>보호 조치</b><br>${esc(n.protection||'접근 권한을 확인하고 계정 정보를 보호합니다.')}</p><p><b>보유 기간</b><br>${esc(n.retention)}</p><p><b>외부 서비스 처리</b><br>${esc(n.third_party)}</p><p><b>동의 거부권</b><br>${esc(n.refusal)}</p><p><b>문의</b>: ${esc(n.contact)}</p>`;}
function loginView(){view='login';app.innerHTML=authCard();wireAuth();}
function wireAuth(){
  app.querySelectorAll('[data-auth]').forEach(b=>b.onclick=()=>{authForm=b.dataset.auth;pendingEmail='';loginView();});
  app.querySelectorAll('[data-recover]').forEach(b=>b.onclick=()=>{authForm='recovery';recoveryKind=b.dataset.recover;pendingEmail='';loginView();});
  const form=app.querySelector('#login-form');if(form)form.onsubmit=async e=>{e.preventDefault();try{const data=await api('auth/login',Object.fromEntries(new FormData(form)));setAccountToken(data.token);}catch(err){toast(err.message);}};
  const reg=app.querySelector('#register-form');if(reg)reg.onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(reg));d.consent=d.consent==='on';d.consent_version=privacyNotice.version;try{await api('auth/register/start',d);pendingEmail=d.email;loginView();toast('인증 코드를 이메일로 보냈습니다.');}catch(err){toast(err.message);}};
  const verify=app.querySelector('#verify-register');if(verify)verify.onsubmit=async e=>{e.preventDefault();try{const data=await api('auth/register/verify',{email:pendingEmail,code:new FormData(verify).get('code')});pendingEmail='';setAccountToken(data.token);}catch(err){toast(err.message);}};
  const rstart=app.querySelector('#recovery-start');if(rstart)rstart.onsubmit=async e=>{e.preventDefault();const email=new FormData(rstart).get('email');try{await api('auth/recovery/start',{email,kind:recoveryKind});pendingEmail=email;loginView();toast('등록된 이메일이면 인증 코드를 보냈습니다.');}catch(err){toast(err.message);}};
  const rfinish=app.querySelector('#recovery-finish');if(rfinish)rfinish.onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(rfinish));d.email=pendingEmail;d.kind=recoveryKind;try{const res=await api('auth/recovery/finish',d);if(res.username)toast('가입한 아이디: '+res.username);else toast('비밀번호를 변경했습니다. 새 비밀번호로 로그인하세요.');pendingEmail='';authForm='login';loginView();}catch(err){toast(err.message);}};
}
async function setAccountToken(token){auth=token;accountMode=true;sessionStorage.setItem('rumble_token',auth);accountData=await api('home');await refreshAccount(true);}
function radarSVG(skills){const keys=['implementation','strings','simulation','data_structures','search','optimization'];const vals=keys.map(k=>Math.max(0,Math.min(100,Number(skills[k]||0))));const cx=120,cy=110,r=78;const pt=(v,i)=>{const a=-Math.PI/2+i*Math.PI/3,rr=r*v/100;return `${cx+Math.cos(a)*rr},${cy+Math.sin(a)*rr}`};const grid=[25,50,75,100].map(v=>`<polygon points="${keys.map((_,i)=>pt(v,i)).join(' ')}"/>`).join('');const labels=['구현','문자열','시뮬레이션','자료구조','탐색','최적화'];return `<svg class="radar" viewBox="0 0 240 220" role="img" aria-label="코딩 능력 6개 지표"><g class="radar-grid">${grid}</g><polygon class="radar-value" points="${vals.map(pt).join(' ')}"/>${labels.map((x,i)=>{const a=-Math.PI/2+i*Math.PI/3;return `<text x="${cx+Math.cos(a)*100}" y="${cy+Math.sin(a)*95}" text-anchor="middle">${x}</text>`}).join('')}</svg>`;}
function homeView(d){const m=d.me;identity.innerHTML=`<span>${esc(m.nickname)} · ${m.tier.icon} ${m.tier.name} · ${m.rating}</span><button class="secondary" id="friends-open">친구</button><button class="secondary" id="logout">로그아웃</button>`;
 const rows=d.lobbies.map(l=>`<article class="lobby-row"><div><strong>${esc(l.name)}</strong><p>${esc(l.owner)} · ${l.players}/${l.capacity}명 · ${l.mode==='challenge'?'챌린지':'일반'}</p></div><button class="primary" data-join="${l.id}" ${d.queue.joined||d.active_lobby||l.full?'disabled':''}>${l.full?'정원 마감':'참가'}</button></article>`).join('')||'<p class="empty">현재 공개된 게임 로비가 없습니다.</p>';
 app.innerHTML=`${d.queue.joined?`<div class="queue-banner"><span class="pulse-dot"></span> ${d.queue.batch_lobby_id?`매칭 완료 · ${timeLabel(d.queue.phase_ends_at)} 후 로비로 이동합니다.`:`매칭 중 · ${d.queue.waiting}/10명`} ${!d.queue.batch_lobby_id?'<button class="secondary" id="queue-cancel">매칭 취소</button>':''}</div>`:''}<section class="profile-hero panel"><button class="avatar-button" id="avatar-edit" aria-label="프로필 아이콘 편집">${m.avatar_id>=1&&m.avatar_id<=5?['⚡','🧠','🦊','🐙','🚀'][m.avatar_id-1]:'⭐'}</button><div class="profile-info"><div class="eyebrow">PLAYER PROFILE</div><h1>${esc(m.nickname)}</h1><p>${m.tier.icon} ${m.tier.name} · 레이트 ${m.rating} · ${m.wins}승 / ${m.games}경기</p></div>${radarSVG(m.skills)}</section><button class="primary matchmaking-button" id="matchmaking" ${d.queue.joined||d.active_lobby?'disabled':''}><span class="match-icon">⚔</span> 게임 매칭</button><section class="panel home-lobbies"><div class="section-heading"><h2>게임 로비</h2><button class="primary" id="create-lobby" ${d.queue.joined||d.active_lobby?'disabled':''}>게임 로비 생성</button></div>${rows}</section>${friendWindow?friendPanel(d):''}${document.querySelector('#avatar-modal')?.outerHTML||''}`;
 document.querySelector('#friends-open').onclick=()=>{friendWindow=!friendWindow;renderAccount();};document.querySelector('#logout').onclick=logoutAccount;
 app.querySelector('#create-lobby').onclick=()=>createLobbyDialog();app.querySelector('#matchmaking').onclick=()=>accountAction('matchmaking/join',{});app.querySelector('#queue-cancel')?.addEventListener('click',()=>accountAction('matchmaking/cancel',{}));
 app.querySelectorAll('[data-join]').forEach(b=>b.onclick=()=>accountAction('lobby/join',{lobby_id:Number(b.dataset.join)}));
 app.querySelector('#avatar-edit').onclick=()=>avatarDialog();
 app.querySelector('#friends-close')?.addEventListener('click',()=>{friendWindow=false;renderAccount();});
 app.querySelector('#friend-add')?.addEventListener('submit',async e=>{e.preventDefault();const nickname=new FormData(e.currentTarget).get('nickname');await accountAction('friends/request',{nickname});});
 app.querySelectorAll('[data-friend]').forEach(b=>b.onclick=()=>accountAction('friends/respond',{requester_id:Number(b.dataset.friend),accept:b.dataset.accept==='1'}));
}
function friendPanel(d){return `<aside class="friend-panel panel"><div class="section-heading"><h2>친구</h2><button class="secondary" id="friends-close">닫기</button></div><form id="friend-add"><input name="nickname" placeholder="닉네임으로 친구 찾기"><button class="secondary">요청</button></form>${d.friend_requests.map(x=>`<div class="friend-row">${esc(x.nickname)} 요청 <button data-friend="${x.requester_id}" data-accept="1">수락</button><button data-friend="${x.requester_id}" data-accept="0">거절</button></div>`).join('')}${d.friends.map(x=>`<div class="friend-row">${esc(x.nickname)} · ${x.rating}</div>`).join('')||'<p>등록된 친구가 없습니다.</p>'}</aside>`;}
function lobbyViewAccount(l){
 const cap=l.mode==='challenge'?5:2, me=l.members.find(x=>x.id===accountData.me.id), allFull=Array.from({length:cap},(_,i)=>l.members.filter(x=>x.team_no===i+1&&!x.operator).length===5).every(Boolean);
 const teams=Array.from({length:cap},(_,i)=>{const no=i+1,mem=l.members.filter(x=>x.team_no===no),ident=l.identities.find(x=>x.team_no===no);return `<section class="lobby-team"><h3>${ident?.selected_logo?`<img class="lobby-team-logo" src="${esc(ident.candidates[ident.selected_logo-1]||'')}" alt="">`:''}${ident?.name?esc(ident.name):(l.mode==='challenge'?'팀 '+no:'팀 '+(no===1?'A':'B'))} <span>${mem.length}/5</span></h3>${mem.map(x=>`<div class="lobby-player"><span>${['','⚡','🧠','🦊','🐙','🚀'][x.avatar_id]||'⭐'} ${esc(x.nickname)} · ${x.rating}${x.ready?' · 준비':''}</span>${!x.ready&&x.id===me?.id&&l.phase==='waiting'?`<button data-move="${no===1?2:1}">이 팀으로 이동</button>`:''}${allFull&&x.id!==me?.id&&!x.ready&&!me?.ready&&x.team_no!==me?.team_no&&l.phase==='waiting'?`<button data-swap="${x.id}">교체 요청</button>`:''}</div>`).join('')}${l.phase==='captain_vote'&&me?.team_no===no?`<div class="captain-vote"><strong>팀장 투표 · ${l.votes?.[no]||0}표</strong>${mem.map(x=>`<button class="${l.my_vote===x.id?'selected':''}" data-vote="${x.id}">${esc(x.nickname)} 선택</button>`).join('')}</div>`:''}${l.phase==='team_setup'&&ident?.captain_id===me?.id?`<form class="team-identity-form" data-team="${no}"><label>우리 팀 이름<input data-focus-key="team-name-${no}" name="name" maxlength="24" value="${esc(ident.name||'')}" required></label><button class="primary">이름 저장 및 로고 후보 만들기</button></form>${(ident.candidates||[]).length?`<div class="logo-options">${ident.candidates.map((src,j)=>`<button class="logo-option ${ident.selected_logo===j+1?'selected':''}" data-logo="${no}:${j+1}"><img src="${src}" alt="로고 후보 ${j+1}"><span>후보 ${j+1} 선택</span></button>`).join('')}</div>`:''}`:''}</section>`}).join('');
 const waiting=l.phase==='waiting', ownerReady=l.members.filter(x=>x.id!==l.owner_id&&!x.operator).every(x=>x.ready), identities=l.identities||[];
 const ownIdentity=identities.find(x=>x.captain_id===me?.id);identity.innerHTML=`${esc(accountData.me.nickname)} · ${accountData.me.tier.icon} ${accountData.me.tier.name} · ${accountData.me.rating}`;
 if(l.phase==='live'&&l.is_operator)return accountOperatorView(l);
 if(l.phase==='live'&&l.game?.player)return accountGameView(l);
 if(l.phase==='finalist_choice'&&l.finalist_choices){
   const choices=l.finalist_choices,candidates=choices.candidates;
   app.innerHTML=`<section class="panel finalist-choice"><div class="eyebrow">CHALLENGE · FINALISTS</div><h1>결승 진출팀 합의</h1><p>럼블 5라운드 종료 시 결승 진출 경계의 승점이 동점입니다. 게임 밖에서 합의한 두 팀을 정하세요.${choices.locked_first?` 팀 ${choices.locked_first}은 단독 1위로 반드시 포함합니다.`:''}</p><div class="finalist-selects"><label>결승 팀 A<select id="finalist-a">${candidates.map(x=>`<option value="${x.team_no}">팀 ${x.team_no} · ${fmt(x.win_points)}점</option>`).join('')}</select></label><label>결승 팀 B<select id="finalist-b">${candidates.map(x=>`<option value="${x.team_no}" ${x.team_no===candidates[1]?.team_no?'selected':''}>팀 ${x.team_no} · ${fmt(x.win_points)}점</option>`).join('')}</select></label></div>${l.is_owner||l.is_operator?'<button class="primary" id="finalist-confirm">합의한 팀으로 확정</button>':'<p class="meta">로비 생성자 또는 운영자가 팀을 확정하면 결승 준비가 시작됩니다.</p>'}</section>`;
   app.querySelector('#finalist-confirm')?.addEventListener('click',()=>accountAction('lobby/finalists',{lobby_id:l.id,team_a:Number(app.querySelector('#finalist-a').value),team_b:Number(app.querySelector('#finalist-b').value)}));return;
 }
 if(l.phase==='operator_results'&&l.is_operator){
   const g=l.game||{},matches=(g.pairs||[]).map(([a,b])=>{const winner=g.winners_by_team?.[String(a)];return `팀 ${a} vs 팀 ${b} · ${winner?`팀 ${winner} 승리`:'무승부'}`;});
   app.innerHTML=`<section class="panel account-result"><div class="eyebrow">OPERATOR · MATCH RESULT</div><div class="result-symbol">RESULT</div><h1>${l.stage_no===6?'결승 결과':'라운드 결과'}</h1><p>${matches.join('<br>')}</p><p>${(g.totals||[]).map(x=>`팀 ${x.team_no} · 승점 ${fmt(x.win_points)} · solve ${fmt(x.solve_points)}`).join(' / ')}</p><div class="phase-banner">다음 대진과 점수를 확인한 뒤 진행하세요.</div><button class="primary" id="operator-next">${l.stage_no>=6?'챌린지 종료':'다음 매치 확인 · 20초 휴식'}</button></section>`;
   app.querySelector('#operator-next').onclick=()=>accountAction('lobby/operator-next',{lobby_id:l.id});return;
 }
 if(l.phase==='results'&&l.game){
   const active=l.game.pairs.some(pair=>pair.includes(me?.team_no)),winner=l.game.winners_by_team?.[String(me?.team_no)]??l.game.winner_team,won=winner===me?.team_no,draw=winner==null&&active;
   const headline=!active?'이번 단계는 휴식':draw?'무승부':won?'승리':'패배';
   app.innerHTML=`<section class="panel account-result ${won?'won':draw?'draw':'lost'}"><div class="eyebrow">${l.mode==='challenge'?`챌린지 ${l.game.round_no}단계 결과`:'일반 매치 결과'}</div><div class="result-symbol">${!active?'REST':draw?'DRAW':won?'VICTORY':'DEFEAT'}</div><h1>${headline}</h1><p>${l.game.totals.map(x=>`팀 ${x.team_no} · 승점 ${fmt(x.win_points)} · solve ${fmt(x.solve_points)}`).join(' / ')}</p><p>레이트 ${accountData.me.rating} · ${accountData.me.tier.name}</p><div class="phase-banner">${phaseText(l)}</div><button class="secondary" id="leave-result">홈페이지로 돌아가기</button></section>`;app.querySelector('#leave-result').onclick=()=>accountAction('lobby/leave',{lobby_id:l.id});return;
 }
 app.innerHTML=`<section class="panel lobby-page"><div class="section-heading"><div><div class="eyebrow">${l.mode==='challenge'?'CHALLENGE MODE':'NORMAL MODE'}</div><h1>${esc(l.name)}</h1></div><button class="secondary" id="lobby-leave">로비 나가기</button></div><p>생성자 ${esc(l.members.find(x=>x.id===l.owner_id)?.nickname||'')} · ${l.members.filter(x=>!x.operator).length}/${l.capacity}명</p>${l.mode==='challenge'?`<div class="operator-slot">운영자 자리 ${l.operator_id?'참가 중':'비어 있음'} ${!l.operator_id&&accountData.me.is_operator&&waiting?'<button class="secondary" id="operator-join">운영자로 참가</button>':''}</div>`:''}<div class="lobby-teams">${teams}</div><div class="phase-banner">${phaseText(l)}</div>${waiting?`<div class="lobby-controls"><button class="primary" id="ready-toggle">${me?.ready?'준비 취소':'준비 완료'}</button>${l.is_owner?`<button class="primary start-game" id="start-game" ${ownerReady?'':'disabled'}>게임 시작</button>`:''}</div>`:''}${l.phase==='operator_start'&&l.is_operator?'<button class="primary operator-start" id="operator-start">챌린지 시작</button>':''}${l.phase==='live'&&l.mode==='challenge'&&l.is_operator?'<button class="secondary" id="operator-close">현재 매치 종료</button>':''}<div class="swap-inbox">${[...(l.swaps||[]),...(l.outgoing_swaps||[])].map(x=>`<div>팀 교체 요청 · <span data-end="${x.expires_at}">${timeLabel(x.expires_at)}</span> ${x.target_id===me?.id?`<button data-swap-answer="${x.id}" data-answer="1">수락</button><button data-swap-answer="${x.id}" data-answer="0">거절</button>`:''}</div>`).join('')}</div>${l.phase==='captain_vote'&&l.mode==='challenge'?'<div class="idle-animation"><span>🗳️</span><b>팀장 투표가 진행 중입니다</b><small>투표가 끝나면 팀장이 팀 이름과 로고를 정합니다.</small></div>':''}${l.phase==='team_setup'&&!ownIdentity?'<div class="idle-animation"><span>✨</span><b>팀을 대표할 이름과 로고를 준비하고 있습니다</b><small>잠시 응원 애니메이션을 보여드립니다.</small></div>':''}${l.phase==='level_select'&&me&&!me.operator?`<div class="level-pick"><label>풀 문제 레벨<select id="account-level"><option value="">레벨 선택</option>${[1,2,3,4,5].map(n=>`<option value="${n}" ${me.level===n?'selected':''}>레벨 ${n}</option>`).join('')}</select></label></div>`:''}</section>`;
 app.querySelector('#lobby-leave').onclick=()=>accountAction('lobby/leave',{lobby_id:l.id});app.querySelector('#ready-toggle')?.addEventListener('click',()=>accountAction('lobby/ready',{lobby_id:l.id,ready:!me.ready}));app.querySelector('#start-game')?.addEventListener('click',()=>accountAction('lobby/start',{lobby_id:l.id}));app.querySelector('#operator-join')?.addEventListener('click',()=>accountAction('lobby/operator-seat',{lobby_id:l.id}));app.querySelector('#operator-start')?.addEventListener('click',()=>accountAction('lobby/operator-start',{lobby_id:l.id}));app.querySelector('#operator-close')?.addEventListener('click',()=>accountAction('lobby/operator-close',{lobby_id:l.id}));
 app.querySelectorAll('[data-vote]').forEach(b=>b.onclick=()=>accountAction('lobby/captain-vote',{lobby_id:l.id,candidate_id:Number(b.dataset.vote)}));app.querySelectorAll('.team-identity-form').forEach(f=>f.onsubmit=async e=>{e.preventDefault();const name=new FormData(f).get('name');try{await api('lobby/team-name',{lobby_id:l.id,team_no:Number(f.dataset.team),name});toast('팀 이름을 저장했습니다. 로고 후보를 준비합니다.');await refreshAccount(true);}catch(err){toast(err.message);}});app.querySelectorAll('[data-logo]').forEach(b=>b.onclick=()=>{const [team,slot]=b.dataset.logo.split(':').map(Number);accountAction('lobby/choose-logo',{lobby_id:l.id,team_no:team,slot});});app.querySelector('#account-level')?.addEventListener('change',e=>{if(e.target.value)accountAction('lobby/level',{lobby_id:l.id,level:Number(e.target.value)});});
 app.querySelectorAll('[data-move]').forEach(b=>b.onclick=()=>accountAction('lobby/move',{lobby_id:l.id,team_no:Number(b.dataset.move)}));app.querySelectorAll('[data-swap]').forEach(b=>b.onclick=()=>accountAction('lobby/swap-request',{lobby_id:l.id,target_id:Number(b.dataset.swap)}));app.querySelectorAll('[data-swap-answer]').forEach(b=>b.onclick=()=>accountAction('lobby/swap-response',{lobby_id:l.id,request_id:Number(b.dataset.swapAnswer),accept:b.dataset.answer==='1'}));
}
function accountOperatorView(l){
 const game=l.game||{},players=game.players||[];
 app.innerHTML=`<section class="panel account-match-top"><div><div class="eyebrow">OPERATOR DESK · ${l.mode==='challenge'?`ROUND ${game.round_no||l.stage_no}`:'RANKED MATCH'}</div><h1>${esc(l.name)}</h1></div><strong class="clock" data-end="${game.ends_at||l.phase_ends_at}">${timeLabel(game.ends_at||l.phase_ends_at)}</strong></section><section class="panel account-scorebar">${(game.totals||[]).map(x=>`<div class="game-score"><strong>팀 ${x.team_no}</strong><span>승점 ${fmt(x.win_points)}</span><span>solve ${fmt(x.solve_points)}</span></div>`).join('')}</section><section class="panel operator-live-board"><div class="section-heading"><h2>실시간 코드 확인</h2><button class="secondary" id="operator-close">현재 매치 종료</button></div><div class="operator-code-grid">${players.map(x=>`<article class="operator-code-card"><div><strong>팀 ${x.team_no} · Lv${x.level} · ${esc(x.nickname)}</strong><small>${esc(x.problem_title)} ${x.solved?'· 정답':''}</small></div><pre>${esc(x.code||'# 아직 작성된 코드가 없습니다.')}</pre></article>`).join('')||'<p>현재 제출 가능한 플레이어가 없습니다.</p>'}</div></section>`;
 app.querySelector('#operator-close')?.addEventListener('click',()=>accountAction('lobby/operator-close',{lobby_id:l.id}));
}
let accountDraftTimer=null,accountSubmitLockedUntil=0,accountLastVerdict='',accountSubmitting=false;
function accountGameView(l){
 const game=l.game,p=game.problem,player=game.player,remaining=seconds(game.ends_at);
 if(player.cooldown_until>now())accountSubmitLockedUntil=Math.max(accountSubmitLockedUntil,player.cooldown_until);const locked=Math.max(0,Math.ceil(accountSubmitLockedUntil-now()));
 const problem={...p,title:`레벨 ${player.level} · ${p.title}`};
 const totals=(game.totals||[]).map(x=>`<div class="game-score"><strong>팀 ${x.team_no}</strong><span>승점 ${fmt(x.win_points)}</span><span>solve ${fmt(x.solve_points)}</span></div>`).join('');
 const hintCards=(game.hints||[]).map(x=>`<details class="account-hint"><summary>${labels[x.kind]} · −${x.cost} solve</summary><p>${esc(x.detail)}</p></details>`).join('');
 app.innerHTML=`<section class="account-match-top panel"><div><div class="eyebrow">${l.mode==='challenge'?`CHALLENGE · ROUND ${game.round_no}`:'RANKED MATCH'}</div><h1>${esc(accountData.me.nickname)} · 레벨 ${player.level}</h1></div><strong class="clock" data-end="${game.ends_at}">${timeLabel(game.ends_at)}</strong></section><section class="account-scorebar panel">${totals}</section>${player.solved?`<section class="panel account-solved"><div class="eyebrow">SUBMISSION ACCEPTED</div><h2>정답입니다</h2><p>solve 포인트 ${player.solve_earned}점이 팀에 즉시 추가되었습니다.</p><p>${phaseText(l)}</p></section>`:`<div class="account-player-grid"><section class="panel account-problem">${problemHTML(problem)}</section><section class="panel account-code"><div class="account-hint-bar"><strong>팀 solve ${fmt(game.solve_balance)}점</strong>${[['type','유형',50],['structure','핵심 구조',150],['assist','AI Code Assist',300]].map(([kind,label,cost])=>`<button class="secondary" data-account-hint="${kind}" ${game.solve_balance<cost?'disabled':''}>${label} · ${cost}</button>`).join('')}</div>${hintCards}<div class="code-label"><strong>Python 코드</strong><span>${locked?`${locked}초 후 제출 가능`:''}</span></div><textarea id="account-code" class="editor account-editor" data-focus-key="game-code" spellcheck="false" aria-label="Python 코드">${esc(player.code||'')}</textarea><div class="actionrow"><span class="meta" id="account-verdict">${esc(accountLastVerdict)}</span><button id="account-submit" class="primary" ${locked?'disabled':''}>${locked?`제출 대기 ${locked}초`:'코드 제출'}</button></div></section></div>`}`;
 const editor=app.querySelector('#account-code');if(editor){window.RumbleEditor?.attach(editor,value=>{clearTimeout(accountDraftTimer);accountDraftTimer=setTimeout(()=>api('lobby/draft',{lobby_id:l.id,code:value}).catch(e=>toast(e.message)),350);});app.querySelector('#account-submit').onclick=async()=>{const btn=app.querySelector('#account-submit'),status=app.querySelector('#account-verdict');accountSubmitting=true;btn.disabled=true;status.textContent='채점 중…';try{const result=await api('lobby/submit',{lobby_id:l.id,code:editor.value});accountLastVerdict=`${result.verdict} · ${result.passed}/${result.total}`;if(result.verdict!=='정답')accountSubmitLockedUntil=now()+10;await refreshAccount(true);}catch(e){accountLastVerdict=e.message;toast(e.message);renderAccount();}finally{accountSubmitting=false;const current=app.querySelector('#account-submit');if(current){current.disabled=accountSubmitLockedUntil>now();if(!current.disabled)current.textContent='코드 제출';}}};app.querySelectorAll('[data-account-hint]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{const result=await api('lobby/hint',{lobby_id:l.id,kind:button.dataset.accountHint,code:editor.value});accountLastVerdict=`${labels[result.kind]}를 사용했습니다. solve ${result.cost}점 차감`;await refreshAccount(true);}catch(e){toast(e.message);button.disabled=false;}});}
}
function phaseText(l){if(l.phase==='waiting')return '팀을 정하고 준비를 완료하세요.';if(l.phase==='captain_vote')return `팀장 투표 · ${timeLabel(l.phase_ends_at)}`;if(l.phase==='team_setup')return `팀 이름과 로고 설정 중 · ${timeLabel(l.phase_ends_at)}`;if(l.phase==='operator_start')return '모든 팀의 이름과 로고가 준비되었습니다. 운영자 시작을 기다립니다.';if(l.phase==='level_select')return `문제 난이도를 선택하세요 · ${timeLabel(l.phase_ends_at)}`;if(l.phase==='start_countdown'||l.phase==='countdown')return `경기 시작까지 ${timeLabel(l.phase_ends_at)}`;if(l.phase==='live')return `${l.mode==='challenge'?`챌린지 ${l.stage_no}단계`:'단판 매치'} 진행 중 · ${timeLabel(l.phase_ends_at)}`;if(l.phase==='results')return `매치 결과 · 다음 단계까지 ${timeLabel(l.phase_ends_at)}`;if(l.phase==='operator_results')return '운영자가 결과를 확인하고 다음 매치를 진행합니다.';if(l.phase==='break')return `다음 매치까지 쉬는 시간 · ${timeLabel(l.phase_ends_at)}`;return '경기 종료';}
async function refreshAccount(force=false){if(!auth)return;try{accountData=await api('home');if(accountData.queue.batch_lobby_id){const matched=await api('lobby/'+accountData.queue.batch_lobby_id);activeLobby=matched.phase==='countdown'&&matched.phase_ends_at>now()?null:matched;}else if(accountData.active_lobby)activeLobby=await api('lobby/'+accountData.active_lobby);else activeLobby=null;renderAccount();}catch(e){if(force||e.message.includes('로그인이 만료')){auth='';accountMode=false;sessionStorage.removeItem('rumble_token');loginView();}else toast(e.message);}}
function renderAccount(){if(!accountMode||!accountData)return loginView();const focused=document.activeElement?.dataset?.focusKey;const value=focused?document.activeElement.value:null;const start=focused?document.activeElement.selectionStart:null,end=focused?document.activeElement.selectionEnd:null;const hasLobby=Boolean(activeLobby);if(hasLobby)lobbyViewAccount(activeLobby);else homeView(accountData);if(focused){const next=app.querySelector(`[data-focus-key="${focused}"]`);if(next){next.focus({preventScroll:true});next.value=value;try{next.setSelectionRange(start,end);}catch(_){}}}}
async function accountAction(path,data){try{await api(path,data);await refreshAccount(true);}catch(e){toast(e.message);}}
function createLobbyDialog(){app.insertAdjacentHTML('beforeend',`<div class="modal-backdrop"><form class="modal-card" id="create-lobby-form"><h2>게임 로비 생성</h2><label>로비 이름<input name="name" maxlength="40" required></label><label>게임 모드<select name="mode"><option value="normal">일반 모드 · 2팀 단판</option><option value="challenge">챌린지 모드 · 5팀 대회</option></select></label><div class="section-heading"><button type="button" class="secondary" id="modal-cancel">취소</button><button class="primary">생성</button></div></form></div>`);app.querySelector('#modal-cancel').onclick=()=>app.querySelector('.modal-backdrop').remove();app.querySelector('#create-lobby-form').onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget));try{const l=await api('lobby/create',data);activeLobby=l;await refreshAccount(true);}catch(err){toast(err.message);}};}
function avatarDialog(){app.insertAdjacentHTML('beforeend',`<div class="modal-backdrop"><div class="modal-card"><h2>프로필 아이콘</h2><div class="avatar-choices">${['⚡','🧠','🦊','🐙','🚀'].map((x,i)=>`<button data-avatar="${i+1}">${x}</button>`).join('')}</div><button class="secondary" id="avatar-close">닫기</button></div></div>`);app.querySelector('#avatar-close').onclick=()=>app.querySelector('.modal-backdrop').remove();app.querySelectorAll('[data-avatar]').forEach(b=>b.onclick=()=>accountAction('account/avatar',{avatar_id:Number(b.dataset.avatar)}));}
function logoutAccount(){api('auth/logout',{}).catch(()=>{});auth='';accountMode=false;accountData=null;activeLobby=null;sessionStorage.removeItem('rumble_token');loginView();}

function profileView(s){
  app.innerHTML=`<section class="login panel"><div class="eyebrow">PLAYER PROFILE</div><h1>선수 이름</h1><form id="profile-form"><div class="login-row"><input id="player-name" minlength="2" maxlength="20" required placeholder="이름"><button class="primary">저장</button></div>${s.me.captain_available?`<label class="captain-check"><input id="captain-choice" type="checkbox" ${s.me.force_captain?'checked disabled':''}>팀장을 맡겠습니다${s.me.force_captain?' · 마지막 선수 자동 지정':''}</label>`:'<p>팀장이 이미 지정되었습니다.</p>'}</form></section>`;
  app.querySelector('form').onsubmit=e=>{e.preventDefault();action('profile',{name:app.querySelector('#player-name').value,captain:!!app.querySelector('#captain-choice')?.checked});};
}
function teamSetupView(s){
  const t=s.team_setup,j=t.job||{},running=j.status==='running',elapsed=running?Math.floor(now()-j.started):0;
  app.innerHTML=`<section class="panel team-setup"><div class="eyebrow">CAPTAIN · TEAM IDENTITY</div><h1>팀 이름과 로고</h1><form id="team-name-form"><div class="login-row"><input id="team-name" minlength="2" maxlength="24" required value="${t.named?esc(t.name):''}" placeholder="팀명"><button class="primary">팀명 저장</button></div></form>
  ${t.named?`<section class="logo-section"><h2>${esc(t.name)}</h2>${!t.candidates.length?'<button id="generate-logos" class="primary">로고 후보 3개 만들기</button>':''}
  <p class="meta" id="logo-status">${running?'AI 로고 생성 중… 저화질·JPEG로 빠르게 생성합니다. 약 30초를 넘으면 임시 후보를 먼저 선택할 수 있습니다.':j.status==='failed'?esc(j.error):j.status==='done'?'AI 후보 3개가 준비되었습니다.':'API 키가 없으면 임시 후보를 제공합니다.'}</p>
  <div class="logo-options">${t.candidates.map(x=>`<button class="logo-option" data-slot="${x.slot}" ${running&&elapsed<30?'disabled':''}><img src="${imageURL('/api/logo/'+s.me.team_id+'?slot='+x.slot+'&v='+(j.status||'local'))}" alt="후보 ${x.slot}"><span>${x.source} ${x.slot}</span></button>`).join('')}</div></section>`:''}</section>`;
  app.querySelector('form').onsubmit=e=>{e.preventDefault();action('team/name',{name:app.querySelector('#team-name').value});};
  const gen=app.querySelector('#generate-logos');if(gen)gen.onclick=()=>action('team/logos');
  app.querySelectorAll('[data-slot]').forEach(el=>el.onclick=()=>action('team/choose-logo',{slot:Number(el.dataset.slot)}));
}
function board(s){return `<section class="panel full-board"><h2>럼블 종합 순위</h2><div class="tablewrap"><table class="board"><thead><tr><th>순위</th><th>팀</th><th>승점</th><th>승리</th><th>정답</th><th>solve 잔액</th></tr></thead><tbody>${s.standings.map((t,i)=>`<tr class="${t.id===s.me.team_id?'mine':''}"><td>${i+1}</td><td>${esc(t.name)}</td><td>${fmt(t.points)}</td><td>${t.wins}</td><td>${t.solved}</td><td>${fmt(t.credit)}</td></tr>`).join('')}</tbody></table></div><p class="meta">승점 = 문제 승점 + 럼블 매치 승리 보너스 100점. 무승부 보너스 없음.</p></section>`;}
function outcome(m,tid){return !m.settled?'':m.winner===null?'DRAW':m.winner===tid?'VICTORY':'DEFEAT';}
function teamHead(t,m){const result=outcome(m,t.id);return `<div class="arena-team-head">${t.logo?`<img src="${imageURL(t.logo)}" alt="${esc(t.name)} 로고">`:'<div class="arena-no-logo">CR</div>'}<div><h2>${esc(t.name)}</h2>${result?`<span class="outcome ${result.toLowerCase()}">${result}</span>`:''}${m.settled&&m.round===6?`<p class="meta">${m.reason==='solve_tiebreak'?'승점 동점 · 남은 solve로 승패 결정':m.winner===null?'승점·solve 모두 동점':'결승 승점 합으로 승패 결정'}</p>`:''}<p class="meta">${fmt(t.points)} 승점 ${t.bonus?`+ 승리 보너스 ${t.bonus}`:''} · solve ${fmt(t.credit)}</p></div></div>`;}
function memberCard(x,m,admin){return `<div class="member-card" data-user="${x.id}"><div class="member-title"><span class="online-dot ${x.online?'online':''}"></span><strong>${esc(x.name)}</strong>${x.captain?'<small>팀장</small>':''}<span class="member-level">${x.level?'Lv'+x.level:'무작위'}</span></div><div class="member-data"><span class="${x.solved?'good':''}">${x.solved?'정답 · +'+x.win_points+' P':m.status==='pending'?(x.ready?'준비 완료':'준비 중'):x.verdict?esc(x.verdict.split('\n')[0]):'풀이 중'}</span>${admin&&m.status!=='pending'?`<button class="secondary mini" data-inspect="${x.id}">코드 확인</button>`:''}</div><div class="item-history">${x.purchases.map(h=>`<span>${labels[h.kind]} −${h.cost}</span>`).join('')}${x.item_used?'<span>결승 스킬 사용</span>':''}${x.freeze_until>now()?'<span class="frozen-label">빙결</span>':''}</div></div>`;}
function matchCard(m,admin=false){
  const a=m.teams[0],b=m.teams[1],ratio=100*(a.points+50)/(a.points+b.points+100);
  const prev=gaugeWidths.get(m.id)??50;gaugeWidths.set(m.id,ratio);
  return `<section class="panel arena match-arena" data-match="${m.id}"><div class="arena-top"><span class="eyebrow">${roundLabel(m.round)} · MATCH ${m.id}</span><strong class="clock" data-end="${m.end_at||0}">${m.status==='open'?timeLabel(m.end_at):m.status==='pending'?'시작 대기':'종료'}</strong></div>
  <div class="tug-label"><span>${esc(a.name)} ${a.points}</span><span>${b.points} ${esc(b.name)}</span></div><div class="tug"><div class="tug-blue" style="width:${prev}%" data-ratio="${ratio}"></div><span class="tug-center"></span></div>
  <div class="arena-grid"><section class="arena-team own ${m.settled&&m.winner===a.id?'match-winner':''}" data-team="${a.id}">${teamHead(a,m)}${a.members.map(x=>memberCard(x,m,admin)).join('')}</section><div class="arena-center"><div>VS</div><p>${m.round===6?'결승 10분 · 동일 승점 · 동점 시 solve 잔액':'승리 보너스 +100'}</p></div><section class="arena-team opponent ${m.settled&&m.winner===b.id?'match-winner':''}" data-team="${b.id}">${teamHead(b,m)}${b.members.map(x=>memberCard(x,m,admin)).join('')}</section></div></section>`;
}
function wireMatches(){app.querySelectorAll('[data-inspect]').forEach(b=>b.onclick=()=>{inspectId=Number(b.dataset.inspect);inspectMode='draft';showInspect();});requestAnimationFrame(()=>app.querySelectorAll('[data-ratio]').forEach(el=>el.style.width=el.dataset.ratio+'%'));}
function compare(s){
  const matches=s.matches.filter(m=>m.status!=='pending');if(!matches.length)return '';
  const m=matches.find(x=>x.id===compareMatch)||matches[0];compareMatch=m.id;
  const members=m.teams.map(t=>t.members.find(x=>x.level===compareLevel));const lines=members.map(x=>(x?.draft||'').split('\n'));
  return `<section class="panel full-board compare"><div class="compare-tools"><h2>실시간 코드 비교</h2><select id="compare-match">${matches.map(x=>`<option value="${x.id}" ${x.id===m.id?'selected':''}>${esc(x.teams[0].name)} vs ${esc(x.teams[1].name)}</option>`).join('')}</select><select id="compare-level">${[1,2,3,4,5].map(l=>`<option value="${l}" ${l===compareLevel?'selected':''}>레벨 ${l}</option>`).join('')}</select></div><div class="compare-grid">${members.map((x,i)=>`<div><h3>${esc(m.teams[i].name)} · ${esc(x?.name)} ${x?.solved?'✓':''}</h3><pre class="compare-code" data-scroll="compare-${i}">${lines[i].map((line,j)=>`<span class="code-line ${line!==lines[1-i][j]?'different':''}"><i>${j+1}</i>${esc(line)||' '}</span>`).join('')}</pre></div>`).join('')}</div><p class="meta">1~2초 간격으로 동기화된 코드를 표시합니다. 색이 있는 줄은 상대 코드와 다른 줄입니다.</p></section>`;
}
function previewCard(info){
  if(!info)return '';
  return `<section class="panel full-board"><h2>다음 ${roundLabel(info.round)} 대진 ${info.tentative?'· 현재 순위 기준 잠정':''}</h2>${info.pending_tie?'<p>진출권 동점입니다. 아래에서 결승 진출팀을 먼저 지정하세요.</p>':info.pairs.map(pair=>`<div class="preview-pair">${pair.map(t=>`<span>${t.logo?`<img src="${imageURL(t.logo)}" alt="">`:''}<strong>${esc(t.name)}</strong></span>`).join('<b>VS</b>')}</div>`).join('')}</section>`;
}
function historyCard(matches){
  return `<section class="panel full-board"><h2>지금까지의 경기 결과</h2>${matches.length?`<div class="history-grid">${matches.map(m=>`<div class="history-match"><span>${roundLabel(m.round)}</span><div>${m.teams.map(t=>`<span class="${m.winner===t.id?'history-winner':''}">${t.logo?`<img src="${imageURL(t.logo)}" alt="">`:''}${esc(t.name)} <strong>${fmt(t.points+(m.winner===t.id?m.bonus:0))}</strong> ${esc(outcome(m,t.id))}</span>`).join('<b>VS</b>')}</div></div>`).join('')}</div>`:'<p class="meta">종료된 경기가 없습니다.</p>'}</section>`;
}
function rehearsalControls(m){return `<div class="panel rehearsal-controls" data-rehearsal-match="${m.id}"><div><strong>리허설 판정 · ${esc(m.teams[0].name)} vs ${esc(m.teams[1].name)}</strong><p class="meta">실제 코드 제출과 OpenAI 호출 없이 점수·승패를 시험합니다. 실제 제출 코드는 생성하지 않습니다.</p></div><div class="rehearsal-tools"><select data-rehearsal-team aria-label="리허설 팀">${m.teams.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select><select data-rehearsal-level aria-label="리허설 레벨">${[1,2,3,4,5].map(l=>`<option value="${l}">Lv${l}</option>`).join('')}</select><button class="primary" data-simulate="correct">정답 처리</button><button class="secondary" data-simulate="wrong">오답 연출</button></div></div>`;}
function tieSelection(tie){
  if(!tie?.required)return '';
  const allowed=tie.candidates;
  if(finalChoiceA===null||!allowed.some(x=>x.id===finalChoiceA))finalChoiceA=tie.chosen?.[0]??allowed[0]?.id;
  if(finalChoiceB===null||!allowed.some(x=>x.id===finalChoiceB))finalChoiceB=tie.chosen?.[1]??allowed[1]?.id;
  return `<section class="panel full-board tie-choice"><h2>결승 진출 동점 결정</h2><p>결승 진출 경계에서 누적 승점이 같습니다. 대회 밖에서 합의한 두 팀을 선택하고 확정하세요.${tie.locked_first?` ${esc(allowed.find(x=>x.id===tie.locked_first)?.name)} 팀은 상위 확정 팀이므로 반드시 포함해야 합니다.`:''}</p><div class="tie-fields">${['A','B'].map(slot=>`<label>결승 ${slot}팀<select data-final-choice="${slot}">${allowed.map(t=>`<option value="${t.id}" ${(slot==='A'?finalChoiceA:finalChoiceB)===t.id?'selected':''}>${esc(t.name)} · ${t.points}점 · ${t.wins}승 · 정답 ${t.solved}</option>`).join('')}</select></label>`).join('')}<button class="primary" id="confirm-finalists">진출팀 확정</button></div>${tie.chosen?`<p class="meta">확정됨: ${esc(allowed.find(x=>x.id===tie.chosen[0])?.name)} vs ${esc(allowed.find(x=>x.id===tie.chosen[1])?.name)} · 변경하려면 다시 확정하세요.</p>`:'<p class="meta">확정 전에는 다음 대진을 열 수 없습니다.</p>'}</section>`;
}
function adminView(s){
  const phaseText={matching:'대진·준비 확인',live:'경기 진행 중',results:'결과 확인',finished:'대회 종료'}[s.phase];
  const actionHTML=s.phase==='matching'
    ?`<button class="primary" id="start-round">준비 확인 · 라운드 시작</button><span class="meta">${s.rehearsal?'리허설: 선수 접속 없이 시작합니다.':'경기에 참여하는 모든 팀원의 준비 완료가 필요합니다.'}</span>`
    :s.phase==='live'
      ?'<button class="secondary" id="close-round">현재 라운드 종료</button><span class="meta">시간 만료 시 자동 종료됩니다.</span>'
      :s.phase==='results'
        ?`<button class="primary" id="next-round" ${s.tie?.required&&!s.tie?.chosen?'disabled':''}>${s.tie?.required&&!s.tie?.chosen?'동점 결정 후 다음 대진 열기':'결과 확인 완료 · 다음 대진 열기'}</button>`
        :'<strong>결승이 종료되었습니다. 새 대회는 전체 초기화 후 시작하세요.</strong>';
  app.innerHTML=`<div class="topline"><div><div class="eyebrow">TOURNAMENT CONTROL ${s.rehearsal?'· REHEARSAL':''}</div><h1>${roundLabel(s.target_round)} · ${phaseText}</h1></div><button class="secondary danger" id="reset-all">전체 초기화</button></div>
  ${s.phase==='matching'&&s.round===0?`<section class="panel full-board rehearsal-switch"><div><h2>혼자 진행하는 리허설 ${s.rehearsal?'· 사용 중':''}</h2><p>선수 25명의 접속·준비 없이 라운드를 시작하고 운영자가 정답·오답을 시험합니다. 대회 기록을 초기화하지 않고 첫 라운드 전까지만 변경할 수 있습니다.</p></div><button class="secondary" id="toggle-rehearsal">${s.rehearsal?'리허설 끄기':'리허설 켜기'}</button></section>`:''}
  <div class="admin-action">${actionHTML}</div>
  ${!s.judge_enabled?'<p class="notice-box">OpenAI 채점이 설정되지 않았습니다. Render의 OPENAI_API_KEY와 JUDGE_PROVIDER를 확인하세요.</p>':''}
  <section class="panel full-board"><h2>OpenAI 연결 상태</h2><p>채점: ${esc(s.judge_provider)} · ${s.judge_enabled?'설정됨 (실제 연결 시험 필요)':'설정 필요'}</p><button class="secondary" id="api-check" ${s.phase==='live'||s.api_check?.status==='running'?'disabled':''}>채점·AI 조언 연결 시험 (유료 호출)</button><p>${s.api_check?.status==='running'?'연결 시험 중… 최대 수 분 걸릴 수 있습니다.':''}</p>${(s.api_check?.results||[]).map(x=>`<p>${x.ok?'✓':'✕'} ${esc(x.name)} · ${x.seconds}초 · ${esc(x.detail)}</p>`).join('')}<p class="meta">로고는 팀장 화면에서 후보 생성으로 확인하세요. 연결 시험은 대회 점수에 반영되지 않습니다.</p></section>
  ${s.matches.map(m=>matchCard(m,true)+(s.rehearsal&&s.phase==='live'?rehearsalControls(m):'')).join('')}
  ${tieSelection(s.tie)}${previewCard(s.upcoming)}${historyCard(s.completed_matches||[])}${compare(s)}${board(s)}<section class="panel full-board"><h2>최근 경기 이벤트</h2><div class="event-log">${s.events.slice(-15).reverse().map(e=>`<p>${new Date(e.at*1000).toLocaleTimeString()} · ${esc(e.detail)}</p>`).join('')}</div></section>`;
  const bind=(id,path,msg)=>{const b=app.querySelector(id);if(b)b.onclick=()=>{if(!msg||confirm(msg))action(path);};};
  const rehearsalButton=app.querySelector('#toggle-rehearsal');if(rehearsalButton)rehearsalButton.onclick=()=>action('admin/rehearsal',{enabled:!s.rehearsal});
  app.querySelectorAll('[data-rehearsal-match]').forEach(panel=>panel.querySelectorAll('[data-simulate]').forEach(button=>button.onclick=()=>action('admin/simulate',{match_id:Number(panel.dataset.rehearsalMatch),team_id:Number(panel.querySelector('[data-rehearsal-team]').value),level:Number(panel.querySelector('[data-rehearsal-level]').value),verdict:button.dataset.simulate})));
  app.querySelectorAll('[data-final-choice]').forEach(el=>el.onchange=()=>{if(el.dataset.finalChoice==='A')finalChoiceA=Number(el.value);else finalChoiceB=Number(el.value);});
  const finalists=app.querySelector('#confirm-finalists');if(finalists)finalists.onclick=()=>{if(finalChoiceA===finalChoiceB)return toast('서로 다른 두 팀을 선택하세요.');action('admin/finalists',{team_a:finalChoiceA,team_b:finalChoiceB});};
  bind('#api-check','admin/api-check','실제 OpenAI API 사용료가 발생합니다. 정답·오답·실행 오류 채점 3건과 AI 조언 1건을 시험할까요?');
  bind('#start-round','admin/start','준비된 팀들의 경기를 시작할까요?');bind('#close-round','admin/close','남은 시간과 관계없이 현재 라운드를 종료할까요?');bind('#next-round','admin/next');
  app.querySelector('#reset-all').onclick=()=>{const text=prompt('모든 경기 기록, 이름, 팀명, 로고, 포인트가 초기화됩니다. 접속 코드는 유지됩니다. 진행하려면 전체 초기화를 입력하세요.');if(text==='전체 초기화')action('admin/reset',{confirmation:text});};
  const cl=app.querySelector('#compare-level'),cm=app.querySelector('#compare-match');
  if(cl)cl.onchange=()=>{compareLevel=Number(cl.value);render();};if(cm)cm.onchange=()=>{compareMatch=Number(cm.value);render();};wireMatches();
}
function lobbyView(s){
  const m=s.matches.find(x=>x.teams.some(t=>t.id===s.me.team_id)),team=m?.teams.find(t=>t.id===s.me.team_id),mine=team?.members.find(x=>x.id===s.me.id);
  app.innerHTML=`<div class="topline"><div><div class="eyebrow">${roundLabel(s.target_round)}</div><h1>${s.phase==='matching'?'다음 대진 · 준비':'대기실'}</h1></div></div>${m?matchCard(m):'<section class="panel empty"><h2>이번 라운드는 휴식입니다.</h2></section>'}
  ${s.phase==='matching'&&mine?`<section class="panel selection-card"><div><h2>내 담당 레벨</h2><p>선택하지 않으면 시작할 때 무작위로 배정됩니다. 선택을 변경하면 준비 상태가 해제됩니다.</p><p>현재 코드는 운영자가 관전 화면에서 확인할 수 있습니다.</p></div><div><select id="level-choice"><option value="">미선택 · 무작위 배정</option>${[1,2,3,4,5].map(l=>`<option value="${l}" ${mine.level===l?'selected':''} ${team.members.some(x=>x.id!==mine.id&&x.level===l)?'disabled':''}>Lv${l} · ${s.rewards[l]}점</option>`).join('')}</select><button id="ready" class="primary">${mine.ready?'준비 취소':'준비 완료'}</button></div></section>`:'<p class="meta">운영자가 결과를 확인하고 다음 대진을 열면 준비할 수 있습니다.</p>'}${board(s)}`;
  if(mine&&s.phase==='matching'){
    app.querySelector('#level-choice').onchange=e=>action('selection',{level:e.target.value?Number(e.target.value):null});
    app.querySelector('#ready').onclick=()=>action('ready',{ready:!mine.ready});
  }wireMatches();
}
function resultView(s){
  const m=s.match,my=m?.teams.find(t=>t.id===s.me.team_id),result=m?outcome(m,s.me.team_id):'';
  app.innerHTML=`<section class="panel result-screen ${result==='DEFEAT'?'failed':''}"><div class="result-symbol">${result==='VICTORY'?'★':result==='DEFEAT'?'×':'='}</div><h1 class="outcome ${result.toLowerCase()}">${result}</h1><h2>${esc(my?.name)}</h2><p>${s.phase==='finished'?'결승 종료 · 대회가 끝났습니다.':'라운드가 종료되었습니다.'}</p><div class="result-points">${my?.points||0} 승점 ${my?.bonus?`+ 승리 보너스 ${my.bonus}`:''}</div><p>${s.solved?'정답 제출 완료':'이번 문제 정답 제출에 실패했습니다.'}</p>${s.phase!=='finished'?'<p>결과 안내 후 대기실에서 다음 대진을 기다립니다.</p>':''}</section>${m?matchCard(m):''}${board(s)}`;wireMatches();
}
function solvedView(s){
  const l=s.me.level,final=s.match.round===6;
  app.innerHTML=`<section class="panel result-screen"><div class="result-symbol">✓</div><h1>정답 제출 완료</h1><p>승점 +${s.solved.win_points} · solve +${s.solved.solve_points}</p><strong class="clock" data-end="${s.match.end_at}">${timeLabel(s.match.end_at)}</strong>
  ${final&&l<=3?`<div class="final-skill"><h2>${['','빙결','변수 교란','코드 절단'][l]}</h2><p>${['','상대 팀 전체의 문제와 코드 작성을 20초 동안 막습니다.','상대 Lv4·5의 가장 자주 쓰인 변수 이름을 바꿉니다.','상대 Lv4·5의 마지막 내용 있는 두 줄을 지웁니다. 빈 줄은 건너뜁니다.'][l]}</p><button class="primary" id="use-item" ${s.item_available?'':'disabled'}>${s.item_available?'아이템 사용 · 1회':'아이템 사용 완료'}</button></div>`:'<p>매치 종료까지 기다려 주세요.</p>'}
  </section>${board(s)}`;
  const b=app.querySelector('#use-item');if(b)b.onclick=()=>action('item');
}
function sampleHTML(title,text){
  const raw=String(text||'').trimEnd();
  const lines=raw.split('\n');
  const preview=(lines.length>10 ? lines.slice(0,9).concat('… (생략) …') : lines).join('\n');
  return `<h3>${esc(title)}</h3><pre class="sample sample-raw">${esc(preview)}</pre>${preview.includes('…')?'<p class="meta">두 테스트케이스의 일부만 표시합니다. … 부분은 생략되어 있으므로 그대로 실행 입력에 사용하지 마세요.</p>':''}`;
}
function problemHTML(p){
  const figures=(p.figures||[]).filter(f=>/^\/problem-images\/[A-Z0-9-]+\.(png|svg)$/.test(f.src));
  const drawings=figures.map(f=>`<figure class="problem-figure"><img src="${esc(f.src)}" alt="${esc(f.alt)}" loading="lazy" decoding="async"><figcaption>${esc(f.caption)}</figcaption></figure>`).join('');
  return `<article class="problem-document"><span class="kicker">${esc(p.id)} · LEVEL ${p.level}</span><h2>${esc(p.title)}</h2><section class="problem-section"><h3>문제 설명</h3><p class="problem-statement">${esc(p.statement)}</p>${drawings}</section><section class="problem-section"><h3>입력</h3><p class="problem-statement">${esc(p.input)}</p></section><section class="problem-section"><h3>제약조건</h3><p class="problem-statement">${esc(p.constraints)}</p></section><section class="problem-section"><h3>출력</h3><p class="problem-statement">${esc(p.output)}</p><pre class="sample sample-raw">${esc(p.output_format)}</pre></section><section class="problem-section">${sampleHTML('예제 입력',p.sample_input)}${sampleHTML('예제 출력',p.sample_output)}</section></article>`;
}

function playView(s){
  const p=s.problem;submitError='';pendingSubmission=null;
  app.innerHTML=`<div class="topline"><div><div class="eyebrow">${roundLabel(s.round)} · ${esc(s.me.name)} · LV ${s.me.level}</div><h1>${esc(p.title)}</h1></div><div><span class="meta">남은 시간 </span><strong class="clock" data-end="${s.match.end_at}">${timeLabel(s.match.end_at)}</strong></div></div><div id="freeze-banner" class="freeze-banner" hidden></div>
  <div class="player-grid"><section class="panel column problem-wrap"><div id="problem-content">${problemHTML(p)}</div><div id="problem-mask" class="problem-mask" hidden>빙결 중 · 문제를 볼 수 없습니다.</div></section>
  <div class="play-workspace"><section class="panel column hint-panel"><h2>팀 solve <span id="balance"></span></h2><div class="hint-list">${Object.keys(s.costs).map(kind=>`<button class="secondary hint-btn" data-kind="${kind}" ${kind==='assist'&&!s.assist_enabled?'disabled':''}>${labels[kind]} <strong>${s.costs[kind]} P</strong></button>`).join('')}</div><p class="meta">팀원이 정답을 내면 즉시 공동 잔액에 적립됩니다.</p><div id="hint-details" class="hint-details"></div></section>
  <section class="panel column"><div class="code-label"><h2>Python 풀이</h2><span id="sync-status">운영자와 코드 공유 중</span></div><p class="editor-help">Tab 자동완성 · Enter 들여쓰기 · 괄호 자동 완성</p><div class="editor-surface"><div class="editor-gutter" aria-hidden="true"></div><div class="editor-pane"><pre class="editor-highlight" aria-hidden="true"></pre><textarea class="editor" id="editor" spellcheck="false" autocomplete="off" aria-label="Python 코드"></textarea><div class="completion-menu" role="listbox" hidden></div></div></div><div class="actionrow"><span id="submit-timer" class="meta"></span><button class="primary" id="submit">코드 제출</button></div><div class="verdict" id="verdict"></div></section>
  </div></div>`;
  const editor=app.querySelector('#editor'),key=`draft:${s.epoch}:${s.match.id}:${s.me.id}`;
  const initial=s.draft.code||sessionStorage.getItem(key)||`# ${p.title}\nT = int(input())\nfor tc in range(1, T + 1):\n    # 입력을 읽고 answer를 계산하세요.\n    print(f"#{tc} {answer}")\n`;
  editState={key,match:s.match.id,rev:s.draft.rev,code:initial,dirty:initial!==s.draft.code,saving:false,version:0};editor.value=initial;
  window.RumbleEditor.attach(editor,value=>{if(editor.readOnly)return;editState.code=value;editState.dirty=true;editState.version++;sessionStorage.setItem(key,value);clearTimeout(saveTimer);saveTimer=setTimeout(syncDraft,400);});
  app.querySelector('#submit').onclick=submitCode;
  app.querySelectorAll('[data-kind]').forEach(b=>b.onclick=()=>{const kind=b.dataset.kind;if(confirm(`팀 solve ${state.costs[kind]}점을 사용해 ${labels[kind]}를 열까요?`))action('hint',{kind,code:editor.value});});
  updatePlay();if(editState.dirty)syncDraft();
}
function acceptDraft(d){
  if(!editState||!d||d.match_id!==editState.match||d.rev<=editState.rev)return;
  if(pendingSubmission&&d.match_id===pendingSubmission.match&&d.rev===pendingSubmission.rev+1&&d.code===pendingSubmission.code){editState.rev=d.rev;pendingSubmission=null;return;}
  const editor=app.querySelector('#editor');
  if(editState.dirty)sessionStorage.setItem(editState.key+':before-effect',editState.code);
  editState.rev=d.rev;editState.code=d.code;editState.dirty=false;
  sessionStorage.setItem(editState.key,d.code);
  if(editor&&editor.value!==d.code){editor.value=d.code;editor.dispatchEvent(new Event('input'));editState.dirty=false;}
}
async function syncDraft(){
  const local=editState;if(!local||local.saving||!local.dirty||view!=='play'||state.draft.freeze_until>now())return;
  local.saving=true;const version=local.version,code=local.code,rev=local.rev;
  try{const res=await api('draft',body({match_id:local.match,code,rev}));if(editState!==local)return;
    if(res.conflict){acceptDraft(res.draft);toast('서버 코드에 아이템 효과가 적용되어 최신 코드로 동기화했습니다.');}
    else{local.rev=Math.max(local.rev,res.draft.rev);if(version===local.version)local.dirty=false;}
  }catch(error){if(editState===local)toast(error.message);}finally{local.saving=false;}
  if(editState===local&&local.dirty)saveTimer=setTimeout(syncDraft,500);
}
async function submitCode(){
  if(busy||!editState||editState.saving)return;
  await syncDraft();if(editState?.dirty||editState?.saving)return;
  busy=true;submitError='';pendingSubmission={match:editState.match,rev:editState.rev,code:editState.code};updatePlay();app.querySelector('#verdict').textContent=(state.judge_provider==='openai'?'OpenAI 채점 중…':'채점 중…')+' 코드를 계속 수정할 수 있습니다.';
  try{const sentRev=editState.rev;const result=await api('submit',body({match_id:editState.match,code:editState.code,rev:sentRev}));if(editState&&result.draft?.rev===sentRev+1)editState.rev=result.draft.rev;ingest(result,true);}
  catch(error){submitError=error.message;const el=app.querySelector('#verdict');if(el)el.textContent=error.message;toast(error.message);}finally{busy=false;updatePlay();}
}
function updatePlay(){
  if(view!=='play'||!state?.draft)return;
  const s=state,d=s.draft,freeze=seconds(d.freeze_until),cool=seconds(d.cooldown_until);
  const editor=app.querySelector('#editor');if(!editor)return;editor.readOnly=freeze>0;
  app.querySelector('#problem-mask').hidden=!freeze;app.querySelector('#problem-content').style.visibility=freeze?'hidden':'visible';
  const banner=app.querySelector('#freeze-banner');banner.hidden=!freeze;banner.textContent=`빙결 · ${freeze}초 동안 문제와 코드 작성이 잠깁니다`;
  const button=app.querySelector('#submit');button.disabled=busy||freeze>0||cool>0||!s.judge_enabled;
  app.querySelector('#submit-timer').textContent=freeze?`빙결 ${freeze}초`:cool?`재제출까지 ${cool}초`:!s.judge_enabled?'OpenAI 채점 설정 필요':'';
  app.querySelector('#sync-status').textContent=editState?.dirty?'코드 저장 중…':'운영자와 코드 공유 중';
  const team=s.standings.find(t=>t.id===s.me.team_id);app.querySelector('#balance').textContent=fmt(team?.credit);
  app.querySelector('#hint-details').innerHTML=s.hints.map(h=>`<h3>${labels[h.kind]}</h3><p>${esc(h.detail)}</p>`).join('');
  const verdict=app.querySelector('#verdict');if(submitError)verdict.textContent=submitError;else if(!busy&&s.last_submission)verdict.textContent=`${s.last_submission.verdict}\n${s.last_submission.passed}/${s.last_submission.total}개 채점 파일 통과`;

}
function phase(s){
  if(s.me.role==='admin')return 'admin';if(!s.me.profile_complete)return 'profile';if(s.me.is_captain&&!s.team_setup.complete)return 'team-setup';
  if(s.phase==='matching')return 'lobby';if(!s.match)return 'lobby';
  if(s.match.settled)return s.phase==='finished'||now()<s.match.end_at+10?'result':'lobby';
  if(s.solved)return 'solved';return s.problem?'play':'lobby';
}
function render(){
  if(accountMode)return renderAccount();
  if(!state)return loginView();
  const input=app.querySelector('#team-name')||app.querySelector('#player-name');
  const draft=input?{id:input.id,value:input.value,start:input.selectionStart,end:input.selectionEnd,focused:document.activeElement===input}:null;
  const scrolls=[...app.querySelectorAll('[data-scroll]')].map(el=>[el.dataset.scroll,el.scrollTop]);
  view=phase(state);identity.innerHTML=`${esc(state.me.name)} <button id="logout" class="secondary">나가기</button>`;
  ({admin:adminView,profile:profileView,'team-setup':teamSetupView,lobby:lobbyView,result:resultView,solved:solvedView,play:playView})[view](state);
  if(view!=='play')editState=null;
  document.querySelector('#logout').onclick=()=>{auth='';state=null;editState=null;inspectId=null;document.querySelector('#inspector')?.remove();sessionStorage.removeItem('rumble_token');loginView();};
  if(draft){const next=app.querySelector('#'+draft.id);if(next){next.value=draft.value;if(draft.focused){next.focus();next.setSelectionRange(draft.start,draft.end);}}}
  for(const [key,pos] of scrolls){const el=app.querySelector(`[data-scroll="${key}"]`);if(el)el.scrollTop=pos;}
}
function effects(s){
  if(seenEpoch!==s.epoch){seenEpoch=s.epoch;seenEvent=s.events.at(-1)?.id||0;return;}
  const fresh=s.events.filter(e=>e.id>seenEvent);seenEvent=s.events.at(-1)?.id||seenEvent;
  for(const e of fresh){
    const targets=['wrong','hint'].includes(e.kind)?document.querySelectorAll(`[data-user="${e.user_id}"]`):document.querySelectorAll(`[data-team="${e.team_id}"]`);
    targets.forEach(el=>{el.classList.add('effect-'+e.kind);setTimeout(()=>el.classList.remove('effect-'+e.kind),900);});
    if(['freeze','rename','erase','result','hint'].includes(e.kind)||e.kind==='wrong'&&s.me.id===e.user_id){
      const el=document.createElement('div');el.className='battle-effect effect-'+e.kind;el.textContent=e.kind==='result'?'경기 결과 확정':e.detail;el.setAttribute('role','status');document.body.appendChild(el);setTimeout(()=>el.remove(),2200);
    }
  }
}
function ingest(s,force=false){
  const old=state,oldView=view;state=s;clockOffset=s.server_time-Date.now()/1000;
  if(old&&old.epoch!==s.epoch){editState=null;inspectId=null;document.querySelector('#inspector')?.remove();toast('대회가 초기화되었습니다.');}
  const next=phase(s),setupSignature=JSON.stringify({me:s.me,setup:s.team_setup});
  if(next==='play'&&oldView==='play'&&old?.match?.id===s.match.id){if(!editState?.saving)acceptDraft(s.draft);updatePlay();}
  else if((next==='team-setup'||next==='profile')&&next===oldView&&setupSignature===lastTeamSetup&&!force){}
  else if(next==='lobby'&&oldView==='lobby'&&JSON.stringify({me:s.me,matches:s.matches,standings:s.standings,selection:s.selection,phase:s.phase,target:s.target_round})===lastLobby&&!force){}
  else if(next===oldView&&['admin','lobby'].includes(next)&&document.activeElement?.tagName==='SELECT'&&!force){}
  else render();
  lastTeamSetup=setupSignature;if(document.activeElement?.tagName!=='SELECT'||force)lastLobby=JSON.stringify({me:s.me,matches:s.matches,standings:s.standings,selection:s.selection,phase:s.phase,target:s.target_round});effects(s);
}
async function refresh(){if(accountMode)return refreshAccount();if(!auth||(busy&&view!=='play'))return;try{ingest(await api('state'));if(inspectId)await showInspect();}catch(error){toast(error.message);}}
let inspectRequest=0;
async function showInspect(){
  const uid=inspectId,request=++inspectRequest;if(!uid)return;
  try{const data=await api('inspect?user_id='+uid);if(inspectId!==uid||request!==inspectRequest)return;
    let pane=document.querySelector('#inspector');if(!pane){pane=document.createElement('div');pane.id='inspector';pane.className='inspector';document.body.appendChild(pane);}
    const key=String(uid)+':'+data.problem.id;
    if(pane.dataset.subject!==key){
      pane.innerHTML=`<div class="inspect-shell panel"><div class="topline"><h2>${esc(data.name)} · 코드 확인</h2><button id="close-inspect" class="secondary">닫기</button></div><div class="inspect-grid"><section class="inspect-problem">${problemHTML(data.problem)}</section><section class="inspect-editor"><select id="inspect-mode"><option value="draft">작성 중인 코드</option><option value="last">마지막 제출 코드</option><option value="accepted">정답 제출 코드</option></select><pre class="inspect-code sample"></pre><p class="meta">실시간 갱신 · 문제와 코드의 스크롤 위치를 유지합니다.</p></section></div></div>`;
      pane.dataset.subject=key;
      pane.querySelector('#close-inspect').onclick=()=>{inspectId=null;inspectRequest++;pane.remove();};
      pane.querySelector('#inspect-mode').onchange=e=>{inspectMode=e.target.value;showInspect();};
    }
    const code=inspectMode==='accepted'?(data.accepted_code??'정답 제출 기록 없음'):inspectMode==='last'?(data.last?.code??'제출 기록 없음'):data.draft.code;
    const el=pane.querySelector('.inspect-code');
    if(el.textContent!==code){const top=el.scrollTop,left=el.scrollLeft;el.textContent=code;el.scrollTop=top;el.scrollLeft=left;}
    pane.querySelector('#inspect-mode').value=inspectMode;
  }catch(error){if(request!==inspectRequest||inspectId!==uid)return;toast(error.message);}
}

setInterval(()=>{
  if(accountMode){document.querySelectorAll('[data-end]').forEach(el=>{if(Number(el.dataset.end)>0)el.textContent=timeLabel(Number(el.dataset.end));});const submit=document.querySelector('#account-submit');if(submit&&!accountSubmitting){const wait=Math.max(0,Math.ceil(accountSubmitLockedUntil-now()));submit.disabled=wait>0;submit.textContent=wait?`제출 대기 ${wait}초`:'코드 제출';}return;}
  if(!state)return;
  document.querySelectorAll('[data-end]').forEach(el=>{if(Number(el.dataset.end)>0)el.textContent=timeLabel(Number(el.dataset.end));});
  if(phase(state)!==view)render();
  updatePlay();
  if(view==='team-setup'&&state.team_setup.job?.status==='running'&&now()-state.team_setup.job.started>=30){
    app.querySelectorAll('[data-slot]').forEach(b=>b.disabled=false);
    app.querySelector('#logo-status').textContent='생성이 30초를 넘었습니다. 임시 로고를 선택해 입장하거나 AI 결과를 기다릴 수 있습니다.';
  }
},250);
setInterval(refresh,1500);
if(auth){accountMode=true;refreshAccount(true);}else{fetch(base()+'/api/privacy').then(r=>r.json()).then(x=>{privacyNotice=x;if(authForm==='register'&&!pendingEmail)loginView();}).catch(()=>{});loginView();}
