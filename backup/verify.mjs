import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'backup/manifest.json'),'utf8'));
const failures=[];
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
for(const item of manifest.files){
 if(path.isAbsolute(item.path)||item.path.split('/').includes('..'))throw new Error('Unsafe manifest path');
 const p=path.join(root,item.path);
 if(!fs.existsSync(p)){failures.push({path:item.path,reason:'missing'});continue}
 const b=fs.readFileSync(p);
 if(b.length!==item.size||digest(b)!==item.sha256)failures.push({path:item.path,reason:'size/hash mismatch'});
}
for(const closure of manifest.restore_source_closures){
 for(const source of closure.sources){
  const b=fs.readFileSync(path.join(root,source.path));
  if(digest(b)!==source.sha256)failures.push({path:source.path,reason:'restore source closure mismatch'});
 }
}
const adopted=JSON.parse(fs.readFileSync(path.join(root,'fpga/results/throughput-20260929/s4-p16-timing7-production-adoption-v1.json'),'utf8'));
if(!manifest.files.some(x=>x.sha256===adopted.candidate_core_sha256))failures.push({reason:'adopted exact core missing'});
const originalPrefix='fpga/results/throughput-20260929/trackS-c2-storage2-route14-v1/project/';
const original=JSON.parse(fs.readFileSync(path.join(root,originalPrefix+'manifest.json'),'utf8'));
for(const [name,expected] of Object.entries(original.source_sha256)){
 const actual=digest(fs.readFileSync(path.join(root,originalPrefix+'rtl/'+name)));
 if(actual!==expected)failures.push({path:originalPrefix+'rtl/'+name,reason:'original53 native manifest mismatch'});
}
if(Object.keys(original.source_sha256).length!==53)failures.push({reason:'original53 closure incomplete'});
for(const f of fs.readdirSync(path.join(root,'fpga/results/throughput-20260929')).filter(x=>x.includes('production-adoption'))){
 const j=JSON.parse(fs.readFileSync(path.join(root,'fpga/results/throughput-20260929',f),'utf8'));
 if(!manifest.files.some(x=>x.sha256===j.candidate_core_sha256))failures.push({path:f,reason:'fallback adopted exact core missing'});
}
console.log(JSON.stringify({retained_files:manifest.files.length,retained_bytes:manifest.files.reduce((n,x)=>n+x.size,0),omissions:manifest.omissions.length,source_closures:manifest.restore_source_closures.map(x=>({job:x.job,sources:x.sources.length})),failures},null,2));
if(failures.length)process.exitCode=1;
