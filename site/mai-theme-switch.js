/* Shared theme preference: shell, embedded documents, standalone documents. */
(()=>{
 const key='maireport-document-theme';
 const root=document.documentElement;
 let current='light';
 try{current=localStorage.getItem(key)==='dark'?'dark':'light';}catch{}
 function apply(value){
  current=value==='dark'?'dark':'light';
  root.dataset.maiTheme=current;
  const button=document.getElementById('mai-theme-toggle');
  if(button){button.textContent=current==='dark'?'☀ 라이트 모드':'☾ 다크 모드';button.setAttribute('aria-pressed',String(current==='dark'));}
 }
 apply(current);
 function broadcast(){
  document.querySelectorAll('iframe').forEach(frame=>{
   try{frame.contentWindow.postMessage({type:'maireport-theme',value:current},location.origin);}catch{}
  });
 }
 function select(value){apply(value);try{localStorage.setItem(key,current);}catch{}broadcast();}
 addEventListener('storage',e=>{if(e.key===key){apply(e.newValue);broadcast();}});
 addEventListener('message',e=>{
  if(e.source!==parent||e.origin!==location.origin||e.data?.type!=='maireport-theme')return;
  apply(e.data.value);
 });
 addEventListener('DOMContentLoaded',()=>{
  // A document opened on its own also gets a theme control; iframe copies use the shell control.
  if(window===window.top){
   const button=document.createElement('button');button.id='mai-theme-toggle';button.type='button';button.title='화면 테마 전환';
   button.onclick=()=>select(current==='dark'?'light':'dark');
   const toolbar=document.querySelector('body[data-mai-kind="navigation"] .tools');
   if(toolbar)toolbar.prepend(button);else{button.className='mai-floating-theme';document.body.append(button);}
  }
  document.querySelectorAll('iframe').forEach(frame=>frame.addEventListener('load',broadcast));
  apply(current);broadcast();
 });
})();
