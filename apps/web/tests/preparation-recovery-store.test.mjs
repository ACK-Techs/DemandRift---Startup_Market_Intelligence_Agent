import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createPreparationRecovery, decodePreparationLocators, preparationLocatorStorageKey as storageKey, preparationLocatorTtlMs as ttl, preparationLocatorLimit as limit } from '../lib/preparation/preparation-recovery-store.ts';
import { createSessionStore } from '../lib/auth/session-store.ts';
import { createApiClient } from '../lib/api/client.ts';
import { brief as content, versions } from '../../../packages/contracts/tests/producer-consumer.ts';

const owner='00000000-0000-4000-8000-000000000001',other='00000000-0000-4000-8000-000000000002',project='00000000-0000-4000-8000-000000000010',research='00000000-0000-4000-8000-000000000011',briefId='00000000-0000-4000-8000-000000000012',key='00000000-0000-4000-8000-000000000013';
const date='2026-10-02T00:00:00Z',csrf='a'.repeat(64),idea='  Private synthetic idea 😀\uFEFF ',patch={expected_brief_version:1,target_user:'  Private synthetic patch 😀\uFEFF ',business_model:null,constraints:{budget:null}};
const session=(user=owner,token=csrf,expires=Date.now()+3600000)=>({schema_version:'1.0.0',user:{schema_version:'1.0.0',user_id:user,email:'synthetic@example.test',created_at:date},csrf_token:token,expires_at:new Date(expires).toISOString()});
const base=()=>({schema_version:'1.0.0',user_id:owner,project_id:project,research_id:research,brief_id:briefId,brief_version:1,created_at:date,versions:{...versions,brief:1,plan:null},status:'awaiting_user',content:{...structuredClone(content),original_idea:idea,clarity_status:'needs_clarification',constraints:{},language_scope:['tr'],skipped_clarification:false,continue_with_unknowns:false}});
const field=value=>({value,state:value===null?'missing':'known',origin:value===null?null:'user_stated',confirmed:false,assumption_id:null,prior_origins:[],conflicting_values:[]});
const revised=()=>{const result=base();result.brief_version=2;result.versions.brief=2;result.content.target_user=field(patch.target_user);result.content.business_model=field(null);result.content.constraints.budget=field(null);return result;};
const receipt=(operation='create_research',extra={})=>({schema_version:'1.0.0',operation,request_key:key,input_fingerprint:'b'.repeat(64),user_id:owner,project_id:project,research_id:research,brief_id:briefId,brief_version:operation==='create_research'?1:2,created_at:date,brief:operation==='create_research'?base():revised(),...extra});
const error=(wait=null)=>({schema_version:'1.0.0',code:'request_failed',message:'Private server text',request_id:owner,operation:null,stage:null,query_id:null,details_ref:null,source_id:null,retryable:true,retry_after_seconds:wait,usage:null,remaining_work:[],next_step:null});
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const locator=(operation='create_research',extra={})=>({v:1,owner_id:owner,project_id:project,request_key:key,expires_at_ms:Date.now()+ttl,operation,research_id:operation==='create_research'?null:research,...extra});
const path=operation=>`/projects/${project}/research${operation==='revise_brief'?`/${research}`:''}`;
function memoryStorage(initial=null){const map=new Map(initial===null?[]:[[storageKey,initial]]);return{map,getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};}
async function harness(t,{storage=memoryStorage(),fetcher=async()=>json(error(),503),auth=()=>json(session()),now=Date.now,operation='create_research',keys=()=>key,refresh=true}={}){
 const calls=[],client=createApiClient(async(url,init)=>{if(url.includes('/auth/'))return auth(url,init);calls.push([url,init]);return fetcher(url,init);});
 const recovery=createPreparationRecovery(()=>storage,client,now,keys),account=createSessionStore(recovery.sessionClient,now);
 const creations=recovery.creationResources(account),revisions=recovery.revisionResources(account);recovery.selectRoute(path(operation));recovery.attach(account);
 t.after(()=>{recovery.detachPreservingLocators();creations.clear();revisions.clear();account.dispose();});if(refresh)await account.refresh();
 const source=operation==='create_research'?creations.acquire(path(operation),project):revisions.acquire(path(operation),project,research);
 if(operation==='create_research')source.setInput({original_idea:idea});else{source.observeLatest(base());source.setInput(patch);}
 return{storage,calls,client,recovery,account,creations,revisions,source,send:()=>operation==='create_research'?source.createResearch():source.reviseBrief()};
}

test('opaque codec accepts only bounded UUID scope/operation/deadline primitives and no private fields',()=>{
 const now=Date.now(),valid=locator('create_research',{expires_at_ms:now+ttl});assert.deepEqual(decodePreparationLocators(JSON.stringify([valid]),now),[valid]);
 assert.equal(decodePreparationLocators(JSON.stringify([locator('revise_brief',{expires_at_ms:now+ttl})]),now).length,1);
 for(const value of [{...valid,body:idea},{...valid,csrf_token:csrf},{...valid,input_fingerprint:'b'.repeat(64)},{...valid,owner_id:[owner]},{...valid,v:'1'},{...valid,request_key:'../key'},{...valid,operation:'unknown'},{...valid,research_id:research},{...valid,expires_at_ms:now+ttl+1},{...valid,expires_at_ms:1.5},{...valid,expires_at_ms:0},{...valid,operation:'revise_brief',research_id:null}])assert.equal(decodePreparationLocators(JSON.stringify([value]),now),null);
 assert.equal(decodePreparationLocators(JSON.stringify([valid,valid]),now),null);assert.equal(decodePreparationLocators(JSON.stringify([valid,{...valid,request_key:other}]),now),null);
 assert.equal(decodePreparationLocators('x'.repeat(16385),now),null);assert.equal(decodePreparationLocators('[null]',now),null);assert.equal(decodePreparationLocators('{}',now),null);assert.equal(decodePreparationLocators('private malformed JSON',now),null);
});

for(const operation of ['create_research','revise_brief'])test(`${operation} writes only the same UUID locator before captured pending and suppresses duplicate POST`,async t=>{
 let release;const h=await harness(t,{operation,fetcher:async()=>new Promise(resolve=>release=()=>resolve(json(error(),503)))});
 let pendingSeen=false;const off=h.source.subscribe(()=>{if(h.source.getSnapshot().status==='pending'){
  pendingSeen=true;const saved=JSON.parse(h.storage.getItem(storageKey));assert.equal(saved.length,1);assert.deepEqual(Object.keys(saved[0]).sort(),['v','owner_id','project_id','request_key','expires_at_ms','operation','research_id'].sort());
  assert.equal(saved[0].operation,operation);assert.equal(saved[0].request_key,key);assert.equal(saved[0].research_id,operation==='create_research'?null:research);
 }});t.after(off);
 const pending=h.send();assert.equal(await h.send(),false);assert.equal(h.calls.length,1);assert.equal(h.calls[0][1].headers['Idempotency-Key'],key);assert.equal(pendingSeen,true);
 const text=h.storage.getItem(storageKey);for(const privateValue of [idea,patch.target_user,csrf,'expected_brief_version','input_fingerprint','business_model','content','email'])assert.equal(text.includes(privateValue),false);
 release();assert.equal(await pending,false);assert.equal(h.source.getSnapshot().status,'unknown');assert.equal(h.recovery.getSnapshot().items.length,0,'RAM source owns recovery until lost');
});

test('blocked/quota storage refuses new POST and leaves no false durable success',async t=>{
 for(const storage of [{getItem:()=>null,setItem:()=>{throw Error('private quota details');},removeItem:()=>{}},{getItem:()=>{throw Error('private denied');},setItem:()=>{},removeItem:()=>{}}]){
  const h=await harness(t,{storage});assert.equal(await h.send(),false);assert.equal(h.calls.length,0);assert.equal(h.source.getSnapshot().status,'contract');assert.equal(h.source.getSnapshot().message.includes('private'),false);
 }
});

for(const operation of ['create_research','revise_brief'])test(`${operation} intact RAM replay still uses its exact sparse body/UUID; definitive rejection/success removes only its locator`,async t=>{
 let posts=0;const h=await harness(t,{operation,fetcher:async()=>++posts===1?json(error(),503):json(operation==='create_research'?base():revised(),200)});
 await h.send();assert.ok(h.storage.getItem(storageKey));assert.equal(h.recovery.getSnapshot().items.length,0);
 assert.equal(await(operation==='create_research'?h.source.replayCreate({original_idea:idea}):h.source.replayRevision(patch)),true);
 assert.equal(h.calls[0][1].body,h.calls[1][1].body);assert.equal(h.calls[0][1].headers['Idempotency-Key'],h.calls[1][1].headers['Idempotency-Key']);assert.equal(h.storage.getItem(storageKey),null);
 const rejected=await harness(t,{operation,fetcher:async()=>json(error(),422)});assert.equal(await rejected.send(),false);assert.equal(rejected.storage.getItem(storageKey),null);
});

for(const operation of ['create_research','revise_brief'])test(`${operation} reload with RAM loss offers only explicit receipt GET,404 stays unknown, historical receipt does not redraft`,async t=>{
 const old=await harness(t,{operation});await old.send();const stored=old.storage.getItem(storageKey);old.recovery.detachPreservingLocators();old.creations.clear();old.revisions.clear();old.account.invalidate();assert.equal(old.storage.getItem(storageKey),stored);
 let checks=0;const h=await harness(t,{operation,storage:old.storage,fetcher:async()=>++checks===1?json(error(),404):json(receipt(operation))});
 assert.equal(h.calls.length,0);assert.equal(h.source.matchesSession(h.account.getSnapshot().session),false);assert.equal(await h.send(),false);
 assert.equal(operation==='create_research'?h.source.setInput({original_idea:'replacement'}):h.source.setInput({...patch,target_user:'replacement'}),false);
 const item=h.recovery.getSnapshot().items[0];assert.equal(item.status,'unknown');assert.equal(Object.hasOwn(item,'request_key'),false);assert.equal(Object.hasOwn(item,'csrf'),false);
 const input=h.source.getSnapshot().input;assert.equal(await h.recovery.checkReceipt(item.handle),false);assert.equal(h.recovery.getSnapshot().items[0].status,'unknown');assert.equal(h.storage.getItem(storageKey),stored);assert.equal(await h.send(),false);
 assert.equal(h.calls[0][1].method,'GET');assert.equal(h.calls[0][1].body,undefined);assert.equal(h.calls[0][1].headers['X-CSRF-Token'],undefined);assert.ok(h.calls[0][0].endsWith(`/preparation-mutations/${operation}/${key}`));
 assert.equal(await h.recovery.checkReceipt(item.handle),true);assert.equal(h.recovery.getSnapshot().items[0].saved.briefVersion,operation==='create_research'?1:2);assert.deepEqual(h.source.getSnapshot().input,input);assert.equal(h.storage.getItem(storageKey),null);assert.equal(await h.send(),false,'confirmed view still does not manufacture a replay or new draft');
});

test('unverified bootstrap unavailable/malformed/network reads keep locators quarantined until canonical session verifies',async t=>{
 for(const failure of [()=>json(error(),503),()=>json({},200),()=>json({},401),()=>{throw Error('private');}]){
  const storage=memoryStorage(JSON.stringify([locator()]));let reads=0;const h=await harness(t,{storage,auth:()=>++reads===1?failure():json(session()),refresh:false});
  assert.equal(h.recovery.getSnapshot().status,'checking');assert.equal(await h.recovery.checkReceipt(1),false);await h.account.refresh();assert.equal(h.recovery.getSnapshot().items.length,0);assert.ok(storage.getItem(storageKey));assert.equal(h.calls.length,0);
  await h.account.refresh();assert.equal(h.recovery.getSnapshot().items.length,1);assert.equal(h.calls.length,0);
 }
});

test('canonical initial session401 and credential mutation clear quarantined hints before accepting another session',async t=>{
 const storage=memoryStorage(JSON.stringify([locator()]));const h=await harness(t,{storage,auth:(url,init)=>init.method==='POST'?json(session(other,'c'.repeat(64))):json(error(),401)});
 assert.equal(storage.getItem(storageKey),null);assert.equal(h.recovery.getSnapshot().items.length,0);
 storage.setItem(storageKey,JSON.stringify([locator()]));h.recovery.detachPreservingLocators();h.recovery.attach(h.account);
 await h.account.authenticate('login','synthetic@example.test','a'.repeat(15));assert.equal(storage.getItem(storageKey),null);assert.equal(h.account.getSnapshot().session.user.user_id,other);
});

test('foreign owner/project/research hints never authorize a receipt request or private panel',async t=>{
 for(const operation of ['create_research','revise_brief']){
  const foreign=await harness(t,{operation,storage:memoryStorage(JSON.stringify([locator(operation)])),auth:()=>json(session(other,'c'.repeat(64)))});assert.equal(foreign.storage.getItem(storageKey),null);assert.equal(foreign.recovery.getSnapshot().items.length,0);assert.equal(await foreign.recovery.checkReceipt(1),false);assert.equal(foreign.calls.length,0);
  const h=await harness(t,{operation,storage:memoryStorage(JSON.stringify([locator(operation)]))});h.recovery.selectRoute(`/projects/${other}/research`);assert.equal(h.recovery.getSnapshot().items.length,0);assert.equal(await h.recovery.checkReceipt(1),false);
  h.recovery.selectRoute(`/projects/${project}/research/${other}`);assert.equal(h.recovery.getSnapshot().items.length,0);assert.equal(await h.recovery.checkReceipt(1),false);assert.equal(h.calls.length,0);
 }
});

test('receipt identity/operation/key/nested version/status mismatches remain unknown without changing storage',async t=>{
 for(const value of [receipt('create_research',{operation:'revise_brief'}),receipt('create_research',{request_key:other}),receipt('create_research',{project_id:other}),receipt('create_research',{user_id:other}),receipt('create_research',{research_id:other}),receipt('create_research',{brief_version:2}),receipt('create_research',{brief:{...base(),versions:{...versions,brief:null,plan:null}}}),receipt('create_research',{brief:{...base(),status:'confirmed'}}),receipt('create_research',{private:'extra'})]){
  const storage=memoryStorage(JSON.stringify([locator()])),h=await harness(t,{storage,fetcher:async()=>json(value)}),before=storage.getItem(storageKey),item=h.recovery.getSnapshot().items[0];assert.equal(await h.recovery.checkReceipt(item.handle),false);assert.equal(h.recovery.getSnapshot().items[0].status,'unknown');assert.equal(storage.getItem(storageKey),before);
 }
});

test('explicit receipt deduplicates actions and route change aborts then drops late private success',async t=>{
 let release,signal;const h=await harness(t,{storage:memoryStorage(JSON.stringify([locator()])),fetcher:async(_url,init)=>{signal=init.signal;return new Promise(resolve=>release=()=>resolve(json(receipt())));}});
 const item=h.recovery.getSnapshot().items[0],pending=h.recovery.checkReceipt(item.handle);assert.equal(await h.recovery.checkReceipt(item.handle),false);assert.equal(h.calls.length,1);
 h.recovery.selectRoute(`/projects/${other}/research`);assert.equal(signal.aborted,true);release();assert.equal(await pending,false);assert.equal(h.recovery.getSnapshot().items.length,0);assert.ok(h.storage.getItem(storageKey));h.recovery.selectRoute(path('create_research'));assert.equal(h.recovery.getSnapshot().items[0].status,'unknown');
});

test('passive checking hides/aborts receipt and matching verification restores the exact locator without automatic GET',async t=>{
 let release,authReads=0,signal;const storage=memoryStorage(JSON.stringify([locator()]));const h=await harness(t,{storage,auth:()=>++authReads===2?json(error(),503):json(session()),fetcher:async(_url,init)=>{signal=init.signal;return new Promise(resolve=>release=()=>resolve(json(receipt())));}});
 const original=storage.getItem(storageKey),pending=h.recovery.checkReceipt(h.recovery.getSnapshot().items[0].handle);await h.account.refresh();assert.equal(signal.aborted,true);assert.equal(h.recovery.getSnapshot().status,'checking');assert.equal(h.recovery.getSnapshot().items.length,0);release();assert.equal(await pending,false);assert.equal(storage.getItem(storageKey),original);
 await h.account.refresh();assert.equal(h.recovery.getSnapshot().items[0].status,'unknown');assert.equal(storage.getItem(storageKey),original);assert.equal(h.calls.length,1,'matching verification cannot trigger recovery');
});

test('real RetryAfter1 resumes from its original deadline after same-session passive refresh and never polls',async t=>{
 const h=await harness(t,{storage:memoryStorage(JSON.stringify([locator()])),fetcher:async()=>json(error(1),503)}),item=h.recovery.getSnapshot().items[0];await h.recovery.checkReceipt(item.handle);assert.equal(h.recovery.getSnapshot().items[0].retryAfterSeconds,1);
 await new Promise(resolve=>setTimeout(resolve,550));await h.account.refresh();assert.equal(h.recovery.getSnapshot().items[0].retryAfterSeconds,1);assert.equal(await h.recovery.checkReceipt(item.handle),false);
 await new Promise(resolve=>setTimeout(resolve,650));assert.equal(h.recovery.getSnapshot().items[0].retryAfterSeconds,null);assert.equal(h.calls.length,1);await h.recovery.checkReceipt(item.handle);assert.equal(h.calls.length,2);
});

test('observed token rotation/owner change/logout/expiry and broadcast-equivalent hard purge remove stored locators and abort',async t=>{
 for(const loss of ['rotation','owner','logout','expiry','broadcast']){
  let reads=0,release,signal,clock=Date.now();const h=await harness(t,{now:()=>clock,storage:memoryStorage(JSON.stringify([locator()])),auth:()=>json(reads++===0?session(owner,csrf,clock+60000):loss==='owner'?session(other,'c'.repeat(64)):session(owner,'c'.repeat(64))),fetcher:async(_url,init)=>{signal=init.signal;return new Promise(resolve=>release=()=>resolve(json(receipt())));}});
  const pending=h.recovery.checkReceipt(h.recovery.getSnapshot().items[0].handle);
  if(loss==='rotation'||loss==='owner')await h.account.refresh();else if(loss==='logout')await h.account.logout();else if(loss==='expiry'){clock+=60001;h.account.checkExpiry();}else h.recovery.hardPurge();
  assert.equal(signal.aborted,true);assert.equal(h.storage.getItem(storageKey),null);release();assert.equal(await pending,false);assert.equal(h.recovery.getSnapshot().items.length,0);
 }
});

test('stale protected401 CAS precedes stale-drop and cannot clear a newer owner/token locator',async t=>{
 let phase=0,release,requests=0;const h=await harness(t,{storage:memoryStorage(JSON.stringify([locator()])),auth:()=>json(phase?session(other,'c'.repeat(64)):session()),fetcher:async()=>++requests===1?new Promise(resolve=>release=()=>resolve(json(error(),401))):json(error(),503)});
 const old=h.recovery.checkReceipt(h.recovery.getSnapshot().items[0].handle);h.account.invalidate();phase=1;await h.account.refresh();const before=h.account.getSnapshot();
 h.recovery.selectRoute(`/projects/${other}/research`);const source=h.creations.acquire(`/projects/${other}/research`,other);source.setInput({original_idea:'Different synthetic owner'});await source.createResearch();const newer=h.storage.getItem(storageKey);assert.equal(JSON.parse(newer)[0].owner_id,other);
 release();assert.equal(await old,false);assert.equal(h.account.getSnapshot(),before);assert.equal(h.storage.getItem(storageKey),newer);assert.equal(before.status,'authenticated');assert.equal(before.session.user.user_id,other);
});

test('late canonical401 purges matching suspended locator even after failed sessionGET discarded global CAS lineage',async t=>{
 let reads=0,release;const h=await harness(t,{storage:memoryStorage(JSON.stringify([locator()])),auth:()=>++reads===1?json(session()):json(error(),503),fetcher:async()=>new Promise(resolve=>release=()=>resolve(json(error(),401)))});
 const pending=h.recovery.checkReceipt(h.recovery.getSnapshot().items[0].handle);await h.account.refresh();assert.ok(h.storage.getItem(storageKey));release();assert.equal(await pending,false);assert.equal(h.storage.getItem(storageKey),null);
});

test('malformed401/403/404/network receipt failures preserve global auth and raw details never enter snapshots/storage',async t=>{
 for(const failure of [()=>json({},401),()=>json(error(),403),()=>json(error(),404),()=>{throw Error('private details');}]){
  const h=await harness(t,{storage:memoryStorage(JSON.stringify([locator()])),fetcher:failure});await h.recovery.checkReceipt(h.recovery.getSnapshot().items[0].handle);assert.equal(h.account.getSnapshot().status,'authenticated');assert.equal(h.recovery.getSnapshot().items[0].status,'unknown');assert.ok(h.storage.getItem(storageKey));assert.equal(JSON.stringify(h.recovery.getSnapshot()).includes('Private server text'),false);assert.equal(h.storage.getItem(storageKey).includes(csrf),false);
 }
});

test('fixed TTL never extends on404/verification/reload; expiration removes UUID without a replacement POST',async t=>{
 let clock=Date.now();const storage=memoryStorage(JSON.stringify([locator('create_research',{expires_at_ms:clock+2000})]));const h=await harness(t,{storage,now:()=>clock,fetcher:async()=>json(error(),404)}),item=h.recovery.getSnapshot().items[0];
 const original=storage.getItem(storageKey);await h.recovery.checkReceipt(item.handle);await h.account.refresh();assert.equal(storage.getItem(storageKey),original);clock+=2001;assert.equal(await h.recovery.checkReceipt(item.handle),false);assert.equal(h.recovery.getSnapshot().items[0].status,'expired');assert.equal(storage.getItem(storageKey),null);assert.equal(await h.send(),false);assert.equal(h.calls.length,1);
});

test('max16 unresolved locators never silently evict or allocate a replacement key',async t=>{
 const values=Array.from({length:limit},(_,n)=>locator('create_research',{project_id:`10000000-0000-4000-8000-${String(n).padStart(12,'0')}`,request_key:`20000000-0000-4000-8000-${String(n).padStart(12,'0')}`})),storage=memoryStorage(JSON.stringify(values));let keys=0;const h=await harness(t,{storage,keys:()=>{keys++;return key;}});assert.equal(await h.send(),false);assert.equal(h.calls.length,0);assert.equal(keys,0);assert.deepEqual(JSON.parse(storage.getItem(storageKey)),values);
});

test('duplicate-tab copied locators permit independent GET only and foreign owner copy is purged',async t=>{
 const raw=JSON.stringify([locator()]),a=await harness(t,{storage:memoryStorage(raw),fetcher:async()=>json(error(),404)}),b=await harness(t,{storage:memoryStorage(raw),fetcher:async()=>json(error(),404)});
 await a.recovery.checkReceipt(a.recovery.getSnapshot().items[0].handle);assert.equal(a.calls.length,1);assert.equal(b.calls.length,0);assert.equal(await a.send(),false);assert.equal(await b.send(),false);a.recovery.hardPurge();assert.equal(a.storage.getItem(storageKey),null);assert.equal(b.storage.getItem(storageKey),raw,'separate tab sessionStorage is not a shared private body store');b.recovery.hardPurge();assert.equal(b.storage.getItem(storageKey),null);
});

test('late mutation401 after failed passiveGET purges its opaque hint while accepted stale401 CAS still runs',async t=>{
 let reads=0,release;const h=await harness(t,{auth:()=>++reads===2?json(error(),503):json(session()),fetcher:async()=>new Promise(resolve=>release=()=>resolve(json(error(),401)))});
 const pending=h.send();await h.account.refresh();assert.ok(h.storage.getItem(storageKey));release();assert.equal(await pending,false);assert.equal(h.storage.getItem(storageKey),null);await h.account.refresh();assert.equal(h.recovery.getSnapshot().items.length,0);
});

test('stale auth-session401 cannot erase a newer authenticated owner and its locator',async t=>{
 let reads=0,release;const h=await harness(t,{refresh:false,storage:memoryStorage(JSON.stringify([locator()])),auth:()=>++reads===1?new Promise(resolve=>release=()=>resolve(json(error(),401))):json(session(other,'c'.repeat(64)))});
 const old=h.account.refresh();h.account.invalidate();await h.account.refresh();h.recovery.selectRoute(`/projects/${other}/research`);const source=h.creations.acquire(`/projects/${other}/research`,other);source.setInput({original_idea:'New synthetic owner'});await source.createResearch();const newer=h.storage.getItem(storageKey);release();assert.equal(await old,false);assert.equal(h.account.getSnapshot().status,'authenticated');assert.equal(h.storage.getItem(storageKey),newer);
});
