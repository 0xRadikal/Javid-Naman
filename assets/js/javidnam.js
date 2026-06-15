// ===== جاویدنام‌های راه آزادی ایران — منطق صفحه =====
let ALL = [];
let EVENTS = {};
let META = {};
let filterEvent = 'all';
let filterVerif = 'all';
let searchQ = '';
let shown = 0;
const PAGE = 60;

const FA = ['۰','۱','۲','۳','۴','۵','۶','۷','۸','۹'];
function toFa(n){ return String(n).replace(/[0-9]/g, d => FA[d]); }

// نقشهٔ رنگ ثابت برای هر رویداد (رنگ واقعی به‌جای کلاس پویای Tailwind که با CDN رندر نمی‌شود)
const EVENT_COLORS = {
  kuye_daneshgah_78: '#fbbf24', green_88: '#34d399', dey_96: '#fb923c',
  darvish_96: '#2dd4bf', mordad_97: '#facc15', kazerun_97: '#a3e635',
  aban_98: '#f87171', khuzestan_1400: '#22d3ee', khizesh_1401: '#e879f9',
  khizesh_1404: '#fb7185', executions: '#c084fc', deaths_in_custody: '#94a3b8'
};
function evColor(e){ return EVENT_COLORS[e] || '#9ca3af'; }
// تبدیل hex به rgba با شفافیت دلخواه
function hexA(hex, a){
  const h = hex.replace('#',''); const r=parseInt(h.slice(0,2),16), g=parseInt(h.slice(2,4),16), b=parseInt(h.slice(4,6),16);
  return `rgba(${r},${g},${b},${a})`;
}

async function init(){
  const statusEl = document.getElementById('load-status');
  try {
    const res = await fetch('assets/data/javidnam.lite.json');
    const data = await res.json();
    META = data.meta; EVENTS = data.events; ALL = data.people;
    statusEl && (statusEl.style.display = 'none');
    renderStats();
    renderEventFilters();
    applyAndRender(true);
    wireEvents();
  } catch(err){
    if(statusEl){ statusEl.innerHTML = '<span class="text-rose-400"><i class="fa-solid fa-triangle-exclamation"></i> خطا در بارگذاری داده‌ها. دوباره تلاش کنید.</span>'; }
    console.error(err);
  }
}

function renderStats(){
  document.getElementById('jv-total').textContent = toFa(META.total) + '+';
  document.getElementById('jv-notable').textContent = toFa(META.notable);
  const evCount = Object.keys(META.by_event || {}).length;
  document.getElementById('jv-events').textContent = toFa(evCount);
}

function renderEventFilters(){
  const wrap = document.getElementById('event-filters');
  const order = Object.entries(EVENTS).sort((a,b)=>(a[1].order||0)-(b[1].order||0));
  let html = `<button data-ev="all" class="ev-btn active px-3 py-1.5 rounded-full text-sm border border-white/15 transition">همه (${toFa(META.total)})</button>`;
  for(const [key,ev] of order){
    const c = META.by_event[key] || 0;
    if(!c) continue;
    html += `<button data-ev="${key}" class="ev-btn px-3 py-1.5 rounded-full text-sm border border-white/15 transition">${ev.title} (${toFa(c)})</button>`;
  }
  wrap.innerHTML = html;
}

function getFiltered(){
  return ALL.filter(p=>{
    if(filterEvent !== 'all' && p.e !== filterEvent) return false;
    if(filterVerif !== 'all' && p.v !== filterVerif) return false;
    if(searchQ){
      const hay = (p.n+' '+(p.ne||'')+' '+(p.c||'')+' '+(p.pr||'')+' '+(p.ca||'')+' '+(p.oc||'')+' '+(p.s||'')).toLowerCase();
      if(!hay.includes(searchQ)) return false;
    }
    return true;
  });
}

let filteredCache = [];
function applyAndRender(reset){
  if(reset){ filteredCache = getFiltered(); shown = 0; document.getElementById('jv-grid').innerHTML=''; }
  const slice = filteredCache.slice(shown, shown + PAGE);
  const grid = document.getElementById('jv-grid');
  const frag = document.createDocumentFragment();
  slice.forEach(p=>{ const el = document.createElement('div'); el.innerHTML = cardHTML(p); frag.appendChild(el.firstElementChild); });
  grid.appendChild(frag);
  shown += slice.length;
  document.getElementById('jv-count').textContent = toFa(filteredCache.length);
  const more = document.getElementById('load-more');
  more.style.display = shown < filteredCache.length ? 'inline-flex' : 'none';
  document.getElementById('jv-empty').style.display = filteredCache.length === 0 ? 'block' : 'none';
}

function cardHTML(p){
  const c = evColor(p.e);
  const ev = EVENTS[p.e] ? EVENTS[p.e].title : p.e;
  const meta = [];
  if(p.a!=null) meta.push(toFa(p.a)+' ساله');
  if(p.c) meta.push(p.c);
  const verifBadge = p.v==='documented'
    ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">مستند</span>'
    : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/20">گزارش‌شده</span>';
  const star = p.nt ? '<i class="fa-solid fa-star text-amber-400 text-xs mr-1" title="چهرهٔ سرشناس"></i>' : '';
  return `<article class="jv-card rounded-xl p-4 border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] transition cursor-pointer" style="border-right:3px solid ${hexA(c,0.5)}" onclick="openPerson('${p.id}')">
    <div class="flex items-start justify-between gap-2 mb-2">
      <h3 class="font-bold text-[15px] leading-snug">${star}${escapeHtml(p.n)}</h3>
      ${verifBadge}
    </div>
    <div class="text-xs mb-1.5" style="color:${c}"><i class="fa-solid fa-location-dot ml-1"></i>${ev}</div>
    <div class="text-xs text-gray-400">${meta.map(escapeHtml).join(' · ')}</div>
    ${p.ca?`<div class="text-[11px] text-gray-500 mt-1.5 line-clamp-1">${escapeHtml(p.ca)}</div>`:''}
  </article>`;
}

function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

async function openPerson(id){
  const p = ALL.find(x=>x.id===id);
  if(!p) return;
  const modal = document.getElementById('jv-modal');
  const box = document.getElementById('jv-modal-content');
  const ev = EVENTS[p.e] ? EVENTS[p.e].title : p.e;
  const c = evColor(p.e);
  const rows = [];
  if(p.a!=null) rows.push(['سن', toFa(p.a)+' سال']);
  if(p.g) rows.push(['جنسیت', p.g]);
  if(p.dj) rows.push(['تاریخ', toFa(p.dj)]);
  if(p.c) rows.push(['شهر', p.c]);
  if(p.pr) rows.push(['استان', p.pr]);
  if(p.oc) rows.push(['شغل', p.oc]);
  if(p.ca) rows.push(['شرح جان‌باختن', p.ca]);
  box.innerHTML = `
    <div class="text-center mb-4">
      <div class="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-3" style="background:${hexA(c,0.15)};border:1px solid ${hexA(c,0.3)}">
        <i class="fa-solid fa-dove text-xl" style="color:${c}"></i>
      </div>
      <h2 class="text-2xl font-extrabold">${p.nt?'<i class="fa-solid fa-star text-amber-400 text-lg ml-1"></i>':''}${escapeHtml(p.n)}</h2>
      ${p.ne?`<div class="text-sm text-gray-400 mt-1" dir="ltr">${escapeHtml(p.ne)}</div>`:''}
      <div class="inline-block mt-2 text-sm px-3 py-1 rounded-full" style="color:${c};background:${hexA(c,0.1)};border:1px solid ${hexA(c,0.2)}">${ev}</div>
    </div>
    <div class="grid grid-cols-2 gap-2 text-sm mb-4">
      ${rows.map(([k,v])=>`<div class="bg-white/[0.04] rounded-lg p-2.5"><div class="text-gray-500 text-xs mb-0.5">${k}</div><div>${escapeHtml(v)}</div></div>`).join('')}
    </div>
    ${p.s?`<div class="bg-white/[0.03] rounded-lg p-4 text-sm leading-7 text-gray-300" style="border-right:2px solid ${hexA(c,0.4)}">${escapeHtml(p.s)}</div>`:''}
    <div class="text-xs text-gray-500 mt-4 text-center">سطح اعتبار: ${p.v==='documented'?'مستند (تأییدشده)':'گزارش‌شده'}</div>
  `;
  modal.style.display = 'flex';
}
function closePerson(){ document.getElementById('jv-modal').style.display='none'; }

function wireEvents(){
  document.getElementById('event-filters').addEventListener('click', e=>{
    const btn = e.target.closest('.ev-btn'); if(!btn) return;
    filterEvent = btn.dataset.ev;
    document.querySelectorAll('.ev-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    applyAndRender(true);
  });
  document.querySelectorAll('.verif-btn').forEach(b=>{
    b.addEventListener('click', ()=>{
      filterVerif = b.dataset.v;
      document.querySelectorAll('.verif-btn').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      applyAndRender(true);
    });
  });
  let t;
  document.getElementById('jv-search').addEventListener('input', e=>{
    clearTimeout(t);
    t = setTimeout(()=>{ searchQ = e.target.value.trim().toLowerCase(); applyAndRender(true); }, 200);
  });
  document.getElementById('load-more').addEventListener('click', ()=>applyAndRender(false));
  document.getElementById('jv-modal').addEventListener('click', e=>{ if(e.target.id==='jv-modal') closePerson(); });
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') closePerson(); });
}

window.openPerson = openPerson;
window.closePerson = closePerson;
document.addEventListener('DOMContentLoaded', init);
