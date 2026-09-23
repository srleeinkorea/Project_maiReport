const fs=require('fs');const path=require('path');
const builderPath=path.join(__dirname,'gpt_build-home-preview.cjs');
let builder=fs.readFileSync(builderPath,'utf8');
builder=builder.replace(/<section class="home-report-card">[\s\S]*?<\/section>/,'');
builder=builder.split('\n').filter(line=>!line.includes("document.getElementById('homeReport")).join('\n');
builder=builder.replace("'<style>'+css+'</style></head>'","'<style>'+css+fs.readFileSync(path.join(__dirname,'gpt_ui-refinement.css'),'utf8')+'</style></head>'");
fs.writeFileSync(builderPath,builder,'utf8');
require(builderPath);
