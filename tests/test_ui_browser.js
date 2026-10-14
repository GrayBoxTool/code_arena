/* Browser-level regression tests for polling, modals, scroll, editor and social UI.
   Run: node tests/test_ui_browser.js (requires Playwright + Chromium). */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let playwright;try{playwright=require('playwright');}catch(_){playwright=require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'playwright'));}
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await playwright.chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const me={id:1,nickname:'선수1',rating:1200,tier:{name:'골드',key:'gold',index:2,color:'#f6c955'},avatar_id:1,games:0,wins:0,skill_max:60,skill_total_max:360,skills:{completion:30,speed:25,accuracy:30,independence:20,contribution:30,challenge:25},skill_labels:{completion:'문제 완수'}};
 const home={me,lobbies:Array.from({length:24},(_,i)=>({id:i+1,name:'테스트 로비 '+i,owner:'테스트',players:1,capacity:10,mode:'normal',full:false})),friends:[{id:2,nickname:'친구',rating:1200,tier:me.tier,online:true}],friend_requests:[],queue:{joined:false},active_lobby:null,notifications:[],invites:[],unread_chat:0,chat_blocked:false};
 let lobby=null;
 const problem={id:'EA-L1',level:1,title:'브라우저 테스트 문제',statement:'충분히 긴 문제 설명입니다.\n\n'.repeat(80),input:'입력 설명',constraints:'제약조건',output:'출력 설명',output_format:'#tc answer',sample_input:'2\n1\n2',sample_output:'#1 1\n#2 2',figures:[]};
 const members=Array.from({length:15},(_,i)=>({id:i+1,nickname:'선수'+(i+1),rating:1200,avatar_id:1,team_no:Math.floor(i/5)+1,ready:i!==0,level:i%5+1,operator:false}));
 await page.route('http://rumble.test/**',async route=>{
  const url=new URL(route.request().url()),p=url.pathname;
  if(p.startsWith('/api/')){
   let data={};if(p==='/api/home')data=home;else if(p==='/api/privacy')data={version:'test',notice:{controller:'테스트',contact:'test@example.com'}};else if(p==='/api/lobby/12')data=lobby;else if(p==='/api/friends/chat')data={messages:[{id:1,sender_id:2,text:'안녕하세요 <script>bad()</script>',created_at:Date.now()/1000}],has_older:false};
   else if(p==='/api/lobby/draft'){const payload=route.request().postDataJSON();lobby.game.player.code=payload.code;data={saved:true};}
   else if(p==='/api/lobby/move'){lobby.members[0].team_no=route.request().postDataJSON().team_no;data={ok:true};}
   return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  }
  const file=path.join(root,'static',p==='/'?'index.html':p.slice(1));return route.fulfill({contentType:p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(file)});
 });
 await page.goto('http://rumble.test/');
 await page.click('[data-auth="register"]');await page.fill('[name=password]','secret123');await page.fill('[name=password_confirm]','secret123');await page.click('[data-password-toggle="password"]');
 assert.equal(await page.locator('[name=password]').getAttribute('type'),'text');assert.equal(await page.locator('[name=password_confirm]').getAttribute('type'),'password');
 await page.click('[data-password-toggle="password_confirm"]');assert.equal(await page.locator('[name=password_confirm]').getAttribute('type'),'text');
 await page.click('[data-auth="login"]');await page.click('[data-recover="password"]');assert.equal(await page.locator('#recovery-start [name=username]').count(),1);
 await page.evaluate(()=>sessionStorage.setItem('rumble_token','test-token'));await page.reload();await page.waitForSelector('#create-lobby');
 await page.click('#create-lobby');await page.fill('#create-lobby-form [name=name]','유지되는 로비 이름');await page.waitForTimeout(3300);
 assert.equal(await page.locator('#create-lobby-form [name=name]').inputValue(),'유지되는 로비 이름');await page.click('#modal-cancel');
 await page.locator('.skill-description').evaluate(el=>el.open=true);await page.evaluate(()=>window.scrollTo(0,1000));await page.waitForTimeout(3300);
 assert.equal(await page.locator('.skill-description').evaluate(el=>el.open),true);assert.ok(Math.abs(await page.evaluate(()=>window.scrollY)-1000)<5);
 await page.evaluate(()=>window.scrollTo(0,0));await page.click('#friends-open');await page.fill('#friend-add [name=nickname]','유지되는 친구 입력');await page.waitForTimeout(1700);assert.equal(await page.locator('#friend-add [name=nickname]').inputValue(),'유지되는 친구 입력');
 await page.click('[data-chat-friend="2"]');await page.waitForSelector('.chat-bubble');await page.fill('#chat-form input','전송 전 초안');await page.waitForTimeout(1700);assert.equal(await page.locator('#chat-form input').inputValue(),'전송 전 초안');assert.equal(await page.locator('.chat-bubble script').count(),0);
 lobby={id:12,name:'3팀 챌린지',mode:'challenge',owner_id:1,visibility:'public',phase:'waiting',status:'waiting',stage_no:0,team_slots:3,final_stage:4,rumble_rounds:3,capacity:40,estimated_seconds:1760,members,identities:[],swaps:[],outgoing_swaps:[],is_owner:true,is_operator:false};home.active_lobby=12;await page.waitForSelector('.lobby-page');
 assert.equal(await page.locator('.lobby-team').count(),3);assert.ok((await page.locator('.duration-estimate').textContent()).includes('30분'));assert.equal(await page.locator('#chat-form input').inputValue(),'전송 전 초안');
 await page.click('#friends-close');lobby.phase='live';lobby.stage_no=1;lobby.phase_ends_at=Date.now()/1000+300;home.chat_blocked=true;lobby.game={round_no:1,started_at:Date.now()/1000,ends_at:lobby.phase_ends_at,player:{level:1,solved:false,code:'',cooldown_until:0},problem,pairs:[[1,2]],totals:[{team_no:1,win_points:0,solve_points:300},{team_no:2,win_points:0,solve_points:300}],solve_balance:300,hints:[{kind:'type',detail:'힌트 내용',cost:50,at:1}]};
 await page.waitForSelector('#account-code');await page.waitForTimeout(500);assert.equal(await page.locator('#chat-form input').isDisabled(),true);
 await page.locator('.account-hint').evaluate(el=>el.open=true);await page.locator('.account-problem').evaluate(el=>el.scrollTop=400);await page.fill('#account-code','T=int(input())\npri');await page.locator('#account-code').press('n');await page.waitForTimeout(3300);
 assert.equal(await page.locator('#account-code').inputValue(),'T=int(input())\nprin');assert.equal(await page.locator('.completion-menu').isVisible(),true);assert.equal(await page.locator('.account-hint').evaluate(el=>el.open),true);assert.equal(await page.locator('.account-problem').evaluate(el=>el.scrollTop),400);
 await page.locator('#account-code').blur();lobby.spectator=true;delete lobby.game.player;lobby.game.players=[{account_id:2,team_no:2,level:1,nickname:'결승선수',problem_title:problem.title,problem,code:'print(1)',solved:false}];
 await page.waitForSelector('.spectator-label');assert.equal(await page.locator('#operator-close').count(),0);await page.locator('.operator-code-card details').evaluate(el=>el.open=true);await page.waitForTimeout(1700);assert.equal(await page.locator('.operator-code-card details').evaluate(el=>el.open),true);
 assert.deepEqual(errors,[]);await browser.close();console.log('Browser: password reveal, recovery fields, persistent modal/details/scroll/chat/editor, and read-only spectator: OK');
})().catch(e=>{console.error(e);process.exit(1)});
