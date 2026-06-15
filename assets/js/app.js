// رابط کاربری تعاملی گاهشمار اعتراضات

const colorMap = {
  rose: '#fb7185', red: '#f43f5e', orange: '#fb923c', amber: '#fbbf24',
  yellow: '#facc15', emerald: '#34d399', teal: '#2dd4bf', cyan: '#22d3ee',
  blue: '#60a5fa', indigo: '#818cf8', purple: '#c084fc', fuchsia: '#e879f9',
  green: '#4ade80', gray: '#9ca3af'
};

let currentFilter = 'all';
let currentSearch = '';

function getColor(c) { return colorMap[c] || '#9ca3af'; }

// رندر خط زمانی کارت‌ها
function renderTimeline() {
  const container = document.getElementById('timeline');
  const filtered = PROTESTS.filter(p => {
    const matchDecade = currentFilter === 'all' || p.decade === currentFilter;
    const s = currentSearch.trim();
    const matchSearch = !s ||
      p.title.includes(s) || p.summary.includes(s) ||
      p.category.includes(s) || p.scope.includes(s) ||
      (p.details && p.details.includes(s)) || p.date.includes(s);
    return matchDecade && matchSearch;
  });

  document.getElementById('result-count').textContent =
    `${toFa(filtered.length)} رویداد`;

  if (filtered.length === 0) {
    container.innerHTML = `<div class="text-center py-20 text-gray-500">
      <i class="fa-solid fa-magnifying-glass text-4xl mb-4 block"></i>
      موردی یافت نشد. عبارت دیگری را امتحان کنید.</div>`;
    return;
  }

  container.innerHTML = filtered.map((p, i) => {
    const color = getColor(p.color);
    const side = i % 2 === 0;
    return `
    <article class="relative md:w-1/2 ${side ? 'md:pl-10 md:mr-auto md:text-right' : 'md:pr-10 md:ml-auto'} pr-14 md:pr-0 fade-in" style="animation-delay:${i*0.04}s">
      <!-- نقطه خط زمانی -->
      <span class="tl-dot absolute top-7 ${side ? 'md:-right-2.5' : 'md:-left-2.5'} right-3.5 md:right-auto" style="color:${color}"></span>

      <div class="protest-card p-5 cursor-pointer" onclick="openModal('${p.id}')">
        <div class="flex items-start gap-3 mb-2">
          <span class="flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center text-lg"
                style="background:${color}22;color:${color}">
            <i class="fa-solid ${p.icon}"></i>
          </span>
          <div class="flex-1 min-w-0">
            <h3 class="font-bold text-lg leading-tight">${p.title}</h3>
            <div class="text-sm mt-1" style="color:${color}">
              <i class="fa-regular fa-calendar text-xs"></i> ${p.date}
            </div>
          </div>
        </div>
        <p class="text-sm text-gray-300 leading-relaxed mb-3">${p.summary}</p>
        <div class="flex flex-wrap gap-2 items-center text-xs">
          <span class="cat-badge" style="background:${color}1f;color:${color}">${p.category}</span>
          <span class="text-gray-400"><i class="fa-solid fa-location-dot"></i> ${p.scope}</span>
        </div>
        <div class="mt-3 pt-3 border-t border-white/5 flex items-center justify-between text-xs">
          <span class="text-rose-300"><i class="fa-solid fa-triangle-exclamation"></i> ${shorten(p.casualties)}</span>
          <span class="text-gray-500 hover:text-white transition">جزئیات کامل <i class="fa-solid fa-arrow-left text-[10px]"></i></span>
        </div>
      </div>
    </article>`;
  }).join('');
}

function shorten(t) { return t.length > 38 ? t.slice(0, 38) + '…' : t; }

// مودال جزئیات
function openModal(id) {
  const p = PROTESTS.find(x => x.id === id);
  if (!p) return;
  const color = getColor(p.color);
  const m = document.getElementById('modal');
  document.getElementById('modal-content').innerHTML = `
    <div class="flex items-start gap-4 mb-5">
      <span class="flex-shrink-0 w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
            style="background:${color}22;color:${color}">
        <i class="fa-solid ${p.icon}"></i>
      </span>
      <div>
        <h2 class="text-2xl font-extrabold leading-tight">${p.title}</h2>
        <div class="mt-1 text-sm" style="color:${color}">
          <i class="fa-regular fa-calendar"></i> ${p.date}
          <span class="mx-2 text-gray-600">|</span>
          <span class="cat-badge" style="background:${color}1f;color:${color}">${p.category}</span>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
      ${infoBox('fa-location-dot', 'گستره', p.scope, color)}
      ${infoBox('fa-skull-crossbones', 'آمار جان‌باختگان', p.casualties, '#f43f5e')}
      ${infoBox('fa-handcuffs', 'بازداشت‌شدگان', p.arrested, '#fbbf24')}
    </div>

    ${block('fa-bolt', 'جرقه و علت', p.spark, color)}
    ${block('fa-circle-info', 'شرح رویداد', p.details, color)}
    ${block('fa-flag-checkered', 'پیامد و نتیجه', p.outcome, color)}

    <div class="mt-5 pt-4 border-t border-white/10 text-xs text-gray-400">
      <i class="fa-solid fa-book"></i> منابع: ${p.source}
    </div>
  `;
  m.classList.remove('hidden');
  m.classList.add('flex');
  document.body.style.overflow = 'hidden';
}

function infoBox(icon, label, val, color) {
  return `<div class="bg-white/5 rounded-xl p-3 border border-white/5">
    <div class="text-xs text-gray-400 mb-1"><i class="fa-solid ${icon}" style="color:${color}"></i> ${label}</div>
    <div class="text-sm font-semibold">${val}</div>
  </div>`;
}
function block(icon, title, body, color) {
  return `<div class="mb-4">
    <h4 class="font-bold mb-1.5 flex items-center gap-2"><i class="fa-solid ${icon}" style="color:${color}"></i> ${title}</h4>
    <p class="text-sm text-gray-300 leading-relaxed">${body}</p>
  </div>`;
}

function closeModal() {
  const m = document.getElementById('modal');
  m.classList.add('hidden');
  m.classList.remove('flex');
  document.body.style.overflow = '';
}

// فیلترها
function setFilter(f, el) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  renderTimeline();
}

// جدول جمع‌بندی آماری
function renderTable() {
  const big = PROTESTS.filter(p => p.decade !== 'صنفی');
  document.getElementById('summary-table').innerHTML = big.map(p => `
    <tr class="border-b border-white/5 hover:bg-white/5 transition cursor-pointer" onclick="openModal('${p.id}')">
      <td class="py-3 px-3 font-semibold">${p.title}</td>
      <td class="py-3 px-3 text-gray-400 whitespace-nowrap">${p.date}</td>
      <td class="py-3 px-3 text-gray-300 text-sm hidden md:table-cell">${p.spark.length > 60 ? p.spark.slice(0,60)+'…' : p.spark}</td>
      <td class="py-3 px-3 text-rose-300 text-sm">${p.casualties}</td>
    </tr>
  `).join('');
}

// تبدیل اعداد به فارسی
function toFa(n) {
  return String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

// راه‌اندازی
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('stat-total').textContent = toFa(STATS.totalProtests) + '+';
  renderTimeline();
  renderTable();

  document.getElementById('search').addEventListener('input', e => {
    currentSearch = e.target.value;
    renderTimeline();
  });

  document.getElementById('modal').addEventListener('click', e => {
    if (e.target.id === 'modal') closeModal();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
});
