// ---- the review harness: render a conversation through the SHIPPED page.
globalThis.__render = function(d, locale, opts){
  opts = opts || {};
  applyLocaleQuiet(locale);
  activeChatId = opts.chat || 'c1';
  newTaskMode = false;
  optimisticSend = opts.optimisticSend || null;
  liveDraft = opts.liveDraft || null;
  liveThinking = opts.liveThinking || null;
  lastState = d;
  renderConversation(d);
  let html = document.getElementById('conversation').innerHTML;
  if(locale==='zh') html = simulateLocaleObserver(html);
  return html;
};
function applyLocaleQuiet(locale){ currentLocale = locale==='zh'?'zh':'en'; }
// The page's locale observer translates every TEXT NODE through zhValue.
// Reproduce that over rendered HTML so a ZH pane here is what a ZH pane is.
function simulateLocaleObserver(html){
  return String(html).replace(/>([^<]+)</g, (m, text) => '>' + translatePreservingSpace(text) + '<')
    .replace(/^([^<]+)/, (m, text) => translatePreservingSpace(text));
}
globalThis.__textOf = function(html){
  // Text as a reader sees it: one line per block, tags stripped, entities back.
  let s = String(html);
  s = s.replace(/<canvas\b[^>]*aria-label="([^"]*)"[^>]*>\s*<\/canvas>/g, '[orb:$1]');
  s = s.replace(/<canvas\b[^>]*>\s*<\/canvas>/g, '[orb:UNLABELLED]');
  s = s.replace(/<button\b[^>]*>/g, '\n[button] ').replace(/<\/button>/g, '\n');
  s = s.replace(/<textarea\b[^>]*>/g, '\n[textarea] ').replace(/<\/textarea>/g, '\n');
  s = s.replace(/<(details|summary|div|p|article|section|li|tr|h[1-6]|label|time|b|span)\b[^>]*>/g, m=>/(summary|details|div|p|article|section|li|tr|h[1-6]|label)/.test(m)?'\n':'');
  s = s.replace(/<\/(details|summary|div|p|article|section|li|tr|h[1-6]|label|time|b|span)>/g, ' ');
  s = s.replace(/<[^>]+>/g, ' ');
  s = s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
  return s.split('\n').map(l=>l.replace(/[ \t]+/g,' ').trim()).filter(Boolean).join('\n');
};
// The FIRST PAINT: what is on the screen before anyone opens anything.
// A <details> that is not `open` contributes only its <summary>.
globalThis.__firstPaint = function(html){
  const tokens = String(html).split(/(<[^>]+>)/);
  let out=[]; const stack=[]; let hidden=0;
  // A <summary> is painted by the <details> it belongs to, so it is on the
  // screen when every details ABOVE its own is open — and a summary nested
  // inside a closed fold is not on the screen at all. Counting summaries
  // instead of resolving them against the stack showed the labels of folded
  // sub-rows as if a person could read them without opening anything.
  const summaries=[]; let shownSummaries=0;
  const visible=()=>hidden===0||shownSummaries>0;
  for(const tk of tokens){
    if(tk.startsWith('<')){
      const close = tk.startsWith('</');
      const name = (tk.match(/^<\/?\s*([a-zA-Z0-9-]+)/)||[])[1];
      if(name==='details'){
        if(close){ const st=stack.pop(); if(st&&st.hid) hidden--; }
        else if(!/\/>$/.test(tk)){ const open=/\sopen(\s|>|=)/.test(tk); stack.push({hid:!open}); if(!open) hidden++; }
        out.push(' ');continue;
      }
      if(name==='summary'){
        if(close){ if(summaries.pop()) shownSummaries--; }
        else { const own=stack.length?stack[stack.length-1]:null;
               const shown=(hidden-((own&&own.hid)?1:0))===0;
               summaries.push(shown); if(shown) shownSummaries++; }
        out.push(' ');continue; }
      if(name==='canvas' && !close){
        const lab=(tk.match(/aria-label="([^"]*)"/)||[])[1];
        if(visible()) out.push(' [orb:'+(lab===undefined?'UNLABELLED':lab)+'] ');
        continue;
      }
      if(/^(div|p|article|section|li|tr|h[1-6]|label|details|summary|button|textarea|br)$/.test(name||'')) out.push('\n');
      else out.push(' ');
      continue;
    }
    if(visible()) out.push(tk);
  }
  let s=out.join('');
  s = s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
  return s.split('\n').map(l=>l.replace(/\s+/g,' ').trim()).filter(Boolean).join('\n');
};

globalThis.row_html=function(r){return row(r,lastState||{});};

// ---- the delegated click handler, driven for real. -----------------------
// `handleActionClick` reads `ev.target.closest('[data-…]')`; the DOM stub has
// no selector engine, so the event hands back the button for exactly the
// attributes that button carries. Everything after that — openResolution,
// openRuntime, api() — is the shipped code.
globalThis.__clickAction = function(attrs){
  const btn = {attrs:Object.assign({},attrs), disabled:false, hidden:false,
    value:'', textContent:'',
    getAttribute(k){return k in this.attrs?this.attrs[k]:null;},
    setAttribute(k,v){this.attrs[k]=String(v);},
    closest(){return null;}, querySelector(){return null;},
    classList:{add(){},remove(){},contains(){return false;}}};
  const ev = {preventDefault(){}, stopPropagation(){},
    target:{closest(sel){
      const key=(String(sel).match(/^\[([a-zA-Z-]+)\]$/)||[])[1];
      return key && Object.prototype.hasOwnProperty.call(attrs,key) ? btn : null;}}};
  handleActionClick(ev);
  return btn;
};
// Whether anything on the page has become modal, and whether the composer is
// still there. Read AFTER a render or a click.
globalThis.__shellState = function(){
  const shell = document.querySelector('.app');
  const ids = ['resolution-modal','runtime-modal','project-modal','settings-modal',
               'mcp-modal','compute-host-modal','delete-project-modal'];
  return {
    shell_inert: shell ? shell.getAttribute('inert') !== null : false,
    body_deciding: document.body.classList.contains('deciding'),
    modals_on: ids.filter(id => document.getElementById(id).classList.contains('on')),
    say_disabled: Boolean(document.getElementById('say').disabled),
    send_disabled: Boolean(document.getElementById('send').disabled),
    composer_inert: document.querySelector('.composer-wrap').getAttribute('inert') !== null,
  };
};
// Every action the rendered conversation offers, as its attribute bag.
globalThis.__actionsIn = function(html){
  const out=[];
  const re=/<button\b([^>]*)>/g; let m;
  while((m=re.exec(String(html)))){
    const attrs={}; const ar=/([a-zA-Z-]+)="([^"]*)"/g; let a;
    while((a=ar.exec(m[1]))) attrs[a[1]]=a[2];
    out.push(attrs);
  }
  return out;
};
globalThis.__globals = function(names){
  const out={};
  for(const n of names) out[n]=eval(n);
  return out;
};
