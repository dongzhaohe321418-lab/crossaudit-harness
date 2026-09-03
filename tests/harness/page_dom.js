// A deliberately dumb DOM stub, enough to LOAD the shipped page script under node.
function mkEl(tag){
  const el={
    nodeType:1, tagName:(tag||'div').toUpperCase(), _tag:tag||'div',
    children:[], childNodes:[], parentElement:null, ownerDocument:null,
    attrs:{}, style:{_p:{},setProperty(k,v){this._p[k]=v;},removeProperty(k){delete this._p[k];},getPropertyValue(k){return this._p[k]||'';}},
    dataset:{}, hidden:false, disabled:false, value:'', checked:false,
    scrollTop:0, scrollHeight:0, clientHeight:0, offsetWidth:100, offsetHeight:20,
    _html:'', _text:'',
    classList:{_s:new Set(),
      add(...c){c.forEach(x=>this._s.add(x));},remove(...c){c.forEach(x=>this._s.delete(x));},
      toggle(c,f){if(f===undefined){this._s.has(c)?this._s.delete(c):this._s.add(c);}else{f?this._s.add(c):this._s.delete(c);}},
      contains(c){return this._s.has(c);}},
    get className(){return [...this.classList._s].join(' ');},
    set className(v){this.classList._s=new Set(String(v||'').split(/\s+/).filter(Boolean));},
    get innerHTML(){return this._html;}, set innerHTML(v){this._html=String(v);},
    get outerHTML(){return this._html;},
    get textContent(){return this._text;}, set textContent(v){this._text=String(v);},
    setAttribute(k,v){this.attrs[k]=String(v);},
    getAttribute(k){return k in this.attrs?this.attrs[k]:null;},
    removeAttribute(k){delete this.attrs[k];},
    hasAttribute(k){return k in this.attrs;},
    appendChild(c){this.children.push(c);this.childNodes.push(c);if(c)c.parentElement=this;return c;},
    removeChild(c){const i=this.children.indexOf(c);if(i>=0)this.children.splice(i,1);return c;},
    insertBefore(c){return this.appendChild(c);},
    remove(){},
    replaceChildren(){this.children=[];},
    querySelector(){return null;}, querySelectorAll(){return [];},
    _c:null, closest(){return this._c||(this._c=mkEl('label'));}, contains(){return false;},
    addEventListener(){}, removeEventListener(){}, dispatchEvent(){return true;},
    focus(){}, blur(){}, click(){}, scrollIntoView(){}, select(){},
    getBoundingClientRect(){return {top:0,left:0,bottom:0,right:0,width:100,height:20};},
    getContext(){return null;},
    animate(){return {cancel(){},finished:Promise.resolve()};},
    matches(){return false;},
    insertAdjacentHTML(){},
    setSelectionRange(){},
    get firstChild(){return this.children[0]||null;},
    get lastChild(){return this.children[this.children.length-1]||null;},
  };
  return el;
}
const els=Object.create(null);
const doc={
  _els:els,
  nodeType:9, documentElement:mkEl('html'),
  head:mkEl('head'),
  body:mkEl('body'),
  title:'',
  hidden:false, visibilityState:'visible',
  createElement:t=>mkEl(t),
  createTextNode:t=>({textContent:String(t),nodeType:3}),
  createDocumentFragment:()=>mkEl('fragment'),
  getElementById(id){return els[id]||(els[id]=Object.assign(mkEl('div'),{id:id}));},
  _q:Object.create(null),
  querySelector(sel){return this._q[sel]||(this._q[sel]=mkEl('div'));},
  querySelectorAll(sel){return [];},
  addEventListener(){}, removeEventListener(){},
  execCommand(){return true;},
  cookie:'',
  get activeElement(){return null;},
};
globalThis.document=doc;
globalThis.window=globalThis;
globalThis.self=globalThis;
globalThis.location={search:'?t=tok',href:'http://localhost/',pathname:'/',protocol:'http:',host:'localhost',hostname:'localhost',origin:'http://localhost',reload(){},assign(){},replace(){}};
globalThis.history={replaceState(){},pushState(){},state:null};
globalThis.navigator={language:'en-US',languages:['en-US'],userAgent:'node',clipboard:{writeText:()=>Promise.resolve()},platform:'MacIntel'};
globalThis.localStorage={_m:{},getItem(k){return k in this._m?this._m[k]:null;},setItem(k,v){this._m[k]=String(v);},removeItem(k){delete this._m[k];}};
globalThis.sessionStorage=globalThis.localStorage;
globalThis.matchMedia=q=>({matches:false,media:q,addEventListener(){},removeEventListener(){},addListener(){},removeListener(){}});
globalThis.requestAnimationFrame=cb=>0;
globalThis.cancelAnimationFrame=()=>{};
globalThis.setTimeout=(f,ms)=>0;
globalThis.clearTimeout=()=>{};
globalThis.setInterval=()=>0;
globalThis.clearInterval=()=>{};
globalThis.fetch=()=>Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({}),text:()=>Promise.resolve('')});
globalThis.EventSource=function(){this.close=()=>{};this.addEventListener=()=>{};};
globalThis.WebSocket=function(){this.close=()=>{};this.addEventListener=()=>{};this.send=()=>{};};
globalThis.alert=()=>{};globalThis.confirm=()=>true;globalThis.prompt=()=>null;
globalThis.ResizeObserver=function(){this.observe=()=>{};this.disconnect=()=>{};this.unobserve=()=>{};};
globalThis.IntersectionObserver=function(){this.observe=()=>{};this.disconnect=()=>{};this.unobserve=()=>{};};
globalThis.MutationObserver=function(){this.observe=()=>{};this.disconnect=()=>{};this.takeRecords=()=>[];};
globalThis.devicePixelRatio=2;
globalThis.performance={now:()=>Date.now()};
globalThis.crypto=globalThis.crypto||{randomUUID:()=>'x'};
globalThis.getComputedStyle=()=>({getPropertyValue:()=>'' , });
globalThis.CustomEvent=function(t,o){this.type=t;Object.assign(this,o||{});};
globalThis.Event=globalThis.CustomEvent;
globalThis.__mkEl=mkEl;
globalThis.Node={ELEMENT_NODE:1,TEXT_NODE:3,DOCUMENT_NODE:9};
globalThis.NodeFilter={SHOW_TEXT:4,SHOW_ELEMENT:1,FILTER_ACCEPT:1,FILTER_REJECT:2,FILTER_SKIP:3};
doc.createTreeWalker=()=>({nextNode:()=>null,currentNode:null});
globalThis.addEventListener=()=>{};globalThis.removeEventListener=()=>{};globalThis.dispatchEvent=()=>true;
globalThis.scrollTo=()=>{};globalThis.innerWidth=1440;globalThis.innerHeight=900;
globalThis.open=()=>null;globalThis.close=()=>{};
