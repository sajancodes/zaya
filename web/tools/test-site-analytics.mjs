import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/data/siteAnalytics.ts',import.meta.url),'utf8');
const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function browser() {
  const storage=new Map();const events=[];const exports={};let now=1800000000000;
  const context={exports,localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},navigator:{doNotTrack:'0'},location:{origin:'https://zaya.test',hostname:'zaya.test'},document:{referrer:'https://www.google.com/search?q=private-query'},URL,crypto:{randomUUID},Date:class extends Date{static now(){return now;}},fetch:(_url,options)=>{events.push(JSON.parse(options.body));return Promise.resolve();}};
  vm.runInNewContext(code,context);
  return {api:exports,context,storage,events,advance:milliseconds=>{now+=milliseconds;}};
}
test('consent, strict-mode deduplication, session expiry and withdrawal',()=>{
  const b=browser();b.api.trackPage('/');assert.equal(b.events.length,0);
  b.api.setPreference('yes');b.api.trackPage('/');b.api.trackPage('/');assert.equal(b.events.length,1);
  b.api.trackPage('/features');assert.equal(b.events[0].session_id,b.events[1].session_id);
  assert.equal(b.events[0].source,'search');assert.equal(JSON.stringify(b.events).includes('private-query'),false);
  b.advance(31*60000);b.api.trackPage('/download');assert.notEqual(b.events[0].session_id,b.events[2].session_id);
  assert.equal(b.events[0].visitor_id,b.events[2].visitor_id);
  b.api.trackDownload({target:{closest:()=>({href:'https://github.com/sajancodes/zaya-companion-releases/releases/download/linux-0.5.0-beta.1/Zaya.deb'})}},'/download');
  assert.equal(b.events.at(-1).platform,'linux');assert.equal(b.events.at(-1).kind,'download');
  const publicCount=b.events.length;b.api.trackPage('/admin');assert.equal(b.events.length,publicCount);
  b.api.trackPage('/download');assert.equal(b.events.length,publicCount+1);
  const before=b.events.length;
  b.api.setPreference('no');b.api.trackPage('/features');assert.equal(b.events.length,before);
  assert.equal(b.storage.has('zaya-site-visitor'),false);assert.equal(b.storage.has('zaya-site-session'),false);
});
test('privacy signals stop all tracking even with an existing opt-in',()=>{
  for(const setting of ['doNotTrack','globalPrivacyControl']){
    const b=browser();b.api.setPreference('yes');b.context.navigator[setting]=setting==='doNotTrack'?'1':true;
    b.api.trackPage('/');assert.equal(b.events.length,0);
  }
});
