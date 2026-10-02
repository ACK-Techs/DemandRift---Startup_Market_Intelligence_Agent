import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { createBackendProxy, backendRequestLimit, backendResponseLimit, backendDeadlineMs } from '../lib/api/backend-proxy.ts';
import { createApiClient } from '../lib/api/client.ts';
import { parseWire } from '../lib/api/wire.ts';
import { readFile } from 'node:fs/promises';

const origin='http://127.0.0.1:18082';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const input=(path='/api/v1/projects',init={})=>new Request(`http://127.0.0.1:3100/api/backend${path}`,init);
async function fixture(t, handler, deadlineMs=1000) {
  let count=0, connections=0;
  const server=createServer((req,res)=>{count++;handler(req,res);});
  server.on('connection',()=>{connections++;});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(async()=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));});
  return {server,proxy:createBackendProxy(origin,{port:server.address().port,deadlineMs}),count:()=>count,connections:()=>connections};
}
async function safeError(response,status) {
  assert.equal(response.status,status);const raw=await response.text();
  const parsed=parseWire('ApiError',raw);assert.equal(parsed.ok,true,'generated error matches canonical contract');
  assert.equal(parsed.data.retryable,false);assert.equal(parsed.data.retry_after_seconds,null);
  assert.equal(response.headers.get('cache-control'),'no-store');
  assert.equal(/private|password|secret-cookie|upstream-sentinel/.test(raw),false,'no upstream details in error');
  assert.equal(/^[0-9a-f-]{36}$/.test(parsed.data.request_id),true,'opaque fresh UUID');
  return parsed.data;
}

test('fixed runtime target uses strict existing origin validator, safe unconfigured503 and no rewrite bypass',async()=>{
  await safeError(await createBackendProxy(undefined)(input()),503);
  for(const bad of ['', 'http://localhost:18082','http://127.0.0.1:18083','http://user:password@127.0.0.1:18082','http://127.0.0.1:18082/?target=private']) assert.throws(()=>createBackendProxy(bad));
  for(const fixture of [{port:0},{port:65536},{port:1,deadlineMs:0},{port:1,deadlineMs:45001}]) assert.throws(()=>createBackendProxy(origin,fixture));
  const config=await readFile(new URL('../next.config.ts',import.meta.url),'utf8');
  const route=await readFile(new URL('../app/api/backend/[...path]/route.ts',import.meta.url),'utf8');
  assert.equal(config.includes('backendRewrites(process.env.DEMANDRIFT_BACKEND_ORIGIN)'),true);
  assert.equal(/async rewrites|httpAgentOptions/.test(config),false);
  assert.equal(route.includes('createBackendProxy(process.env.DEMANDRIFT_BACKEND_ORIGIN)'),true);
  assert.equal(/fixture|request\.url|searchParams/.test(route),false,'production route has no target injection');
  assert.equal(backendDeadlineMs,45000);assert.equal(backendRequestLimit,65536);assert.equal(backendResponseLimit,10485760);
});

test('actual HTTP idle requests each use a fresh connection with close even when upstream advertises keepalive',async(t)=>{
  const f=await fixture(t,(_req,res)=>{res.setHeader('Connection','keep-alive');res.end('ok');});f.server.keepAliveTimeout=40;
  assert.equal(await (await f.proxy(input())).text(),'ok');await delay(100);
  assert.equal(await (await f.proxy(input())).text(),'ok');
  assert.equal(f.count(),2);assert.equal(f.connections(),2,'no idle socket reuse');
});

test('Cookie Origin CSRF idempotency and Unicode bytes reach one actual upstream without host rewrite',async(t)=>{
  const body='\uFEFF  😀 exact sparse body',cookie='synthetic=secret-cookie; other=two',csrf='a'.repeat(64),key=crypto.randomUUID();
  let exact=false;
  const f=await fixture(t,(req,res)=>{const chunks=[];req.on('data',c=>chunks.push(c));req.on('end',()=>{
    exact=req.url==='/api/v1/projects?cursor=opaque%26value&limit=25'&&req.method==='POST'&&req.headers.cookie===cookie&&req.headers.origin==='http://127.0.0.1:3100'&&req.headers['x-csrf-token']===csrf&&req.headers['idempotency-key']===key&&req.headers.connection==='close'&&req.headers.host===`127.0.0.1:${f.server.address().port}`&&Buffer.concat(chunks).equals(Buffer.from(body));res.writeHead(201,{'Content-Type':'application/json'});res.end('{}');});});
  const response=await f.proxy(input('/api/v1/projects?cursor=opaque%26value&limit=25',{method:'POST',body,headers:{Cookie:cookie,Origin:'http://127.0.0.1:3100','X-CSRF-Token':csrf,'Idempotency-Key':key,Host:'evil.example'}}));
  assert.equal(response.status,201);assert.equal(exact,true,'captured auth and body sent exactly');assert.equal(f.count(),1);
});

test('multiple raw SetCookie including Expires comma survive as distinct response cookies',async(t)=>{
  const cookies=['one=synthetic; Path=/; HttpOnly; SameSite=Lax','two=synthetic; Expires=Wed, 21 Oct 2037 07:28:00 GMT; Path=/; SameSite=Lax'];
  const f=await fixture(t,(_req,res)=>{res.setHeader('Set-Cookie',cookies);res.end('ok');});
  const result=await f.proxy(input());assert.equal(result.headers.getSetCookie().length,2);
  assert.equal(result.headers.getSetCookie().every((v,i)=>v===cookies[i]),true,'cookie bytes preserved separately');
});

test('hop-by-hop and Connection-nominated headers stripped both ways, framing regenerated',async(t)=>{
  let valid=false;
  const f=await fixture(t,(req,res)=>{valid=req.headers['x-remove']===undefined&&req.headers['keep-alive']===undefined&&req.headers['proxy-authorization']===undefined&&req.headers.connection==='close';
    res.writeHead(200,{'Connection':'close, X-Private-Hop','X-Private-Hop':'upstream-sentinel','Keep-Alive':'timeout=90','X-End-To-End':'kept'});res.end('bytes');});
  const result=await f.proxy(input('/api/v1/projects',{headers:{Connection:'keep-alive, X-Remove','X-Remove':'upstream-sentinel','Keep-Alive':'timeout=90','Proxy-Authorization':'upstream-sentinel'}}));
  assert.equal(valid,true);assert.equal(result.headers.has('connection'),false);assert.equal(result.headers.has('x-private-hop'),false);assert.equal(result.headers.has('keep-alive'),false);assert.equal(result.headers.has('transfer-encoding'),false);assert.equal(result.headers.get('x-end-to-end'),'kept');assert.equal(await result.text(),'bytes');
});

test('chunked arbitrary response bytes and compression metadata preserve wire payload without decoding',async(t)=>{
  const bytes=Buffer.from([0,255,195,40,10,200]);
  const f=await fixture(t,(_req,res)=>{res.writeHead(200,{'Content-Type':'application/octet-stream','Content-Encoding':'custom'});res.write(bytes.subarray(0,2));res.end(bytes.subarray(2));});
  const result=await f.proxy(input());assert.equal(Buffer.from(await result.arrayBuffer()).equals(bytes),true);assert.equal(result.headers.get('content-encoding'),'custom');
});

for(const method of ['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS']) test(`${method} has one native attempt and preserves status including empty responses`,async(t)=>{
  let received='';const f=await fixture(t,(req,res)=>{received=req.method;req.resume();req.on('end',()=>{res.writeHead(method==='HEAD'?200:204);res.end();});});
  const result=await f.proxy(input('/api/v1/auth/logout',{method}));assert.equal(result.status,method==='HEAD'?200:204);assert.equal(await result.text(),'');assert.equal(received,method);assert.equal(f.count(),1);
});

test('untrusted URL origin cannot control upstream and invalid path/headers/method never sends',async(t)=>{
  const f=await fixture(t,(_req,res)=>res.end('fixed'));
  assert.equal(await (await f.proxy(new Request('https://evil.example/api/backend/api/v1/projects?target=https%3A%2F%2Fevil.example'))).text(),'fixed');
  for(const path of ['/api/backend/api/v1/%2Fsecret','/api/backend/api/v1/%2e%2e%2fsecret','/api/backend/api/v1/a.b','/api/backend//evil','/other/api/v1/projects','/api/backend/api/v1/projects?q='+ 'x'.repeat(8193),'/api/backend/api/v1/'+ 'x'.repeat(8193)]) await safeError(await f.proxy(new Request('http://127.0.0.1:3100'+path)),400);
  await safeError(await f.proxy(input('/api/v1/projects',{method:'CUSTOM'})),405);
  await safeError(await f.proxy(input('/api/v1/projects',{headers:{'X-Large':'x'.repeat(33000)}})),400);
  assert.equal(f.count(),1);
});

test('request exactly64KiB sent once; oversized buffered/chunked request rejected before upstream',async(t)=>{
  let bytes=0;const f=await fixture(t,(req,res)=>{req.on('data',c=>{bytes+=c.length;});req.on('end',()=>res.end('ok'));});
  assert.equal((await f.proxy(input('/api/v1/projects',{method:'POST',body:Buffer.alloc(backendRequestLimit)}))).status,200);assert.equal(bytes,backendRequestLimit);
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',body:Buffer.alloc(backendRequestLimit+1)})),413);
  const chunks=new ReadableStream({start(c){c.enqueue(new Uint8Array(60000));c.enqueue(new Uint8Array(6000));c.close();}});
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',body:chunks,duplex:'half'})),413);
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',body:'one',headers:{'Content-Length':'4'}})),400);
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',headers:{'Content-Length':'3'}})),400);
  assert.equal(f.count(),1);
});

test('response exactly10MiB preserves bytes; oversized/truncated upstream becomes safe502',async(t)=>{
  const f=await fixture(t,(req,res)=>{if(req.url.endsWith('/large'))res.end(Buffer.alloc(backendResponseLimit+1));else if(req.url.endsWith('/truncated')){res.writeHead(200,{'Content-Length':100});res.write('upstream-sentinel');setTimeout(()=>res.destroy(),5);}else res.end(Buffer.alloc(backendResponseLimit,1));});
  const exact=await f.proxy(input('/api/v1/exact'));assert.equal((await exact.arrayBuffer()).byteLength,backendResponseLimit);
  await safeError(await f.proxy(input('/api/v1/large')),502);await safeError(await f.proxy(input('/api/v1/truncated')),502);assert.equal(f.count(),3);
});

test('redirect never followed or forwarded and no second upstream request',async(t)=>{
  const f=await fixture(t,(_req,res)=>{res.writeHead(302,{Location:'http://private:password@evil.example/upstream-sentinel','Set-Cookie':'private=secret-cookie'});res.end('upstream-sentinel');});
  const result=await f.proxy(input());await safeError(result,502);assert.equal(result.headers.has('location'),false);assert.equal(result.headers.getSetCookie().length,0);assert.equal(f.count(),1);
});

test('ambiguous committed mutation socket drop has count1 and client remains unknown without automatic retry',async(t)=>{
  let committed=0;const f=await fixture(t,(req,res)=>{req.resume();req.once('end',()=>{committed++;res.destroy();});});
  const client=createApiClient((path,init)=>f.proxy(new Request('http://127.0.0.1:3100'+path,init)));
  const result=await client.request('Project','/api/v1/projects',{method:'POST',body:{name:'synthetic'},csrfToken:'a'.repeat(64),idempotencyKey:crypto.randomUUID()});
  assert.equal(result.ok,false);assert.equal(result.status,502);assert.equal(result.operationState,'unknown');assert.equal(f.count(),1);assert.equal(committed,1);
  await delay(80);assert.equal(f.count(),1,'no delayed replay');
});

test('upstream drop before response and failed connection each return distinct safe errors without retries',async(t)=>{
  const f=await fixture(t,(_req,res)=>res.destroy());await safeError(await f.proxy(input()),502);assert.equal(f.count(),1);
  const temp=createServer();await new Promise(resolve=>temp.listen(0,'127.0.0.1',resolve));const port=temp.address().port;await new Promise(resolve=>temp.close(resolve));
  const failed=createBackendProxy(origin,{port,deadlineMs:100});const first=await safeError(await failed(input()),502),second=await safeError(await failed(input()),502);
  assert.equal(first.request_id!==second.request_id,true,'failure UUID fresh without raw details');
});

test('overall deadline closes upstream and slow client-body read without sending another request',async(t)=>{
  let closed=false;const f=await fixture(t,(req,_res)=>{req.socket.once('close',()=>{closed=true;});req.resume();},40);
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',body:'synthetic'})),504);await delay(30);assert.equal(closed,true);assert.equal(f.count(),1);
  let cancelled=false;const stream=new ReadableStream({pull(){},cancel(){cancelled=true;}});
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',body:stream,duplex:'half'})),504);assert.equal(cancelled,true);assert.equal(f.count(),1);
});

test('client cancellation closes held upstream, discards partial payload and never retries',async(t)=>{
  let closed=false,arrived;const waiting=new Promise(resolve=>{arrived=resolve;});
  const f=await fixture(t,(req,res)=>{req.resume();res.write('upstream-sentinel');req.socket.once('close',()=>{closed=true;});arrived();});
  const controller=new AbortController(),pending=f.proxy(input('/api/v1/projects',{method:'POST',body:'synthetic',signal:controller.signal}));
  await waiting;controller.abort();await safeError(await pending,502);await delay(30);assert.equal(closed,true);assert.equal(f.count(),1);
});

test('pre-aborted client body never opens upstream and releases stream reader',async(t)=>{
  const f=await fixture(t,(_req,res)=>res.end('unexpected'));const controller=new AbortController();controller.abort();
  await safeError(await f.proxy(input('/api/v1/projects',{method:'POST',body:'synthetic',signal:controller.signal})),502);assert.equal(f.count(),0);
});
