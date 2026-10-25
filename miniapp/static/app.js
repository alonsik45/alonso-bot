/* ═══════════════════════════════════════════════════════════
   Alonso БОТ — мини-приложение: дизайн из нового макета + реальный API бота.
   Игра «Карточки» — в game.js.
═══════════════════════════════════════════════════════════ */
'use strict';
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

let currentIdeaType = 'ideas';
let currentQuestionType = 'anonymous';
let currentBroadcastType = 'subscribers';
let isAdmin = false;
let twitchUrl = '';

const $id = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const escapeHtml = esc;
const sleep = ms => new Promise(r => setTimeout(r, ms));
function errMsg(detail, fallback) { return (typeof detail === 'string' && detail) ? detail : fallback; }

/* ── Toast (текст вставляется как textContent — безопасно для ников и ответов сервера) ── */
function showToast(msg, type = 'success') {
  const c = $id('toast-container');
  if (!c) return;
  const t = document.createElement('div');
  t.className = 'toast toast-' + (type === 'error' ? 'error' : 'success');
  const ic = document.createElement('span'); ic.textContent = type === 'error' ? '⚠️' : '✅';
  const tx = document.createElement('span'); tx.textContent = String(msg);
  t.append(ic, tx); c.appendChild(t);
  setTimeout(() => {
    t.style.transition = 'opacity .28s, transform .28s';
    t.style.opacity = '0'; t.style.transform = 'translateX(110%)';
    setTimeout(() => t.remove(), 300);
  }, 3200);
}

/* ── Ripple ── */
function rippleEffect(btn, e) {
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 2;
  const x = ((e?.clientX ?? rect.left + rect.width / 2) - rect.left) - size / 2;
  const y = ((e?.clientY ?? rect.top + rect.height / 2) - rect.top) - size / 2;
  const r = document.createElement('span');
  r.className = 'ripple';
  r.style.cssText = `width:${size}px;height:${size}px;left:${x}px;top:${y}px`;
  btn.appendChild(r);
  r.addEventListener('animationend', () => r.remove());
}
document.addEventListener('click', e => {
  const btn = e.target.closest('.btn,.quick-btn');
  if (btn) rippleEffect(btn, e);
});

/* ── Навигация ── */
document.querySelectorAll('.nav-pill-btn[data-section]').forEach(btn =>
  btn.addEventListener('click', () => goTo(btn.dataset.section))
);

function goTo(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-pill-btn[data-section]').forEach(b => b.classList.remove('active'));
  $id(id)?.classList.add('active');
  document.querySelector(`.nav-pill-btn[data-section="${id}"]`)?.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.body.classList.toggle('ai-open', id === 'ai');
  if (id === 'profile') loadProfile();
  if (id === 'top') loadTop();
  if (id === 'interact') { loadChbdStatus(); loadTrashStatus(); }
  if (id === 'ai') aiRender();
  if (id === 'admin') { loadChbdStatusAdmin(); loadTrashStatusAdmin(); }
  if (id === 'game' && window.loadGame) loadGame();
}
function goToTab(sectionId, tabId) {
  goTo(sectionId);
  setTimeout(() => switchTab(tabId), 50);
}

/* ── Вкладки ── */
document.querySelectorAll('.tab-btn[data-tab]').forEach(btn =>
  btn.addEventListener('click', () => switchTab(btn.dataset.tab))
);
function switchTab(tabId) {
  const btn = document.querySelector('.tab-btn[data-tab="' + tabId + '"]');
  if (!btn) return;
  const tabRow = btn.closest('.card');
  (tabRow || document.body).querySelectorAll('.tab-btn[data-tab]').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const section = btn.closest('.section') || document.body;
  (tabRow || section).querySelectorAll('.tab-btn[data-tab]').forEach(b => $id('tab-' + b.dataset.tab)?.classList.remove('active'));
  $id('tab-' + tabId)?.classList.add('active');
  const hero = $id('game-hero-neuro');
  if (hero) hero.style.display = (tabId === 'g-shop') ? 'none' : '';
  if (tabId === 'chbd') loadChbdStatus();
  if (tabId === 'trash') loadTrashStatus();
  if (tabId === 'g-coll' && window.renderCollection) renderCollection();
  if (tabId === 'g-friends') loadFriends();
  if (tabId === 'g-pvp' && window.renderPvPCards) { renderPvPCards(); renderFriendCards(); }
}

/* ── Переключатели (тип вопроса, категория идеи, тип рассылки) ── */
document.addEventListener('click', e => {
  const b = e.target.closest('.toggle-btn');
  if (!b) return;
  b.parentElement.querySelectorAll('.toggle-btn').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  if (b.dataset.type) currentQuestionType = b.dataset.type;
  if (b.dataset.ideaType) currentIdeaType = b.dataset.ideaType;
  if (b.dataset.broadcastType) currentBroadcastType = b.dataset.broadcastType;
});

/* ── Аккордеон на главной ── */
document.querySelectorAll('.accordion-trigger').forEach(trigger => {
  trigger.addEventListener('click', () => {
    const item = trigger.closest('.accordion-item');
    const content = item.querySelector('.accordion-content');
    const body = item.querySelector('.accordion-body');
    const isOpen = item.classList.contains('open');
    item.closest('.accordion')?.querySelectorAll('.accordion-item.open').forEach(o => {
      if (o !== item) { o.querySelector('.accordion-content').style.height = '0'; o.classList.remove('open'); }
    });
    if (isOpen) { content.style.height = '0'; item.classList.remove('open'); }
    else { item.classList.add('open'); content.style.height = body.scrollHeight + 'px'; }
  });
});

/* ── Фото на главной (стрелки + свайп + автопрокрутка) ── */
let currentPanel = 0;
const TOTAL_PANELS = document.querySelectorAll('.media-tab-panel').length || 3;
function goToPanel(idx) {
  currentPanel = (idx + TOTAL_PANELS) % TOTAL_PANELS;
  document.querySelectorAll('.media-tab-panel').forEach((p, i) => p.classList.toggle('active', i === currentPanel));
  document.querySelectorAll('.media-dot').forEach((d, i) => d.classList.toggle('active', i === currentPanel));
}
$id('media-prev')?.addEventListener('click', () => { goToPanel(currentPanel - 1); resetAuto(); });
$id('media-next')?.addEventListener('click', () => { goToPanel(currentPanel + 1); resetAuto(); });
let autoTimer = setInterval(() => goToPanel(currentPanel + 1), 5000);
function resetAuto() { clearInterval(autoTimer); autoTimer = setInterval(() => goToPanel(currentPanel + 1), 5000); }
(function () {
  const card = $id('media-card'); if (!card) return;
  let sx = 0;
  card.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, { passive: true });
  card.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 40) { goToPanel(currentPanel + (dx < 0 ? 1 : -1)); resetAuto(); }
  }, { passive: true });
})();

/* ── Таймер до стрима ── */
let _cdTimer = null;
async function loadCountdown() {
  const info = $id('stream-info');
  try {
    const res = await fetch('/api/countdown');
    const data = await res.json();
    twitchUrl = data.twitch_url || '';
    if (_cdTimer) { clearInterval(_cdTimer); _cdTimer = null; }
    const cd = document.querySelector('.countdown');
    if (data.is_live) {
      info.textContent = '🔴 СТРИМ ИДЁТ СЕЙЧАС!';
      info.style.color = 'var(--danger)';
      if (cd) cd.style.display = 'none';
    } else if (data.target_iso) {
      info.style.color = ''; if (cd) cd.style.display = '';
      const target = new Date(data.target_iso).getTime();
      info.textContent = `${data.when_label}, ${data.time_label} мск`;
      tickCountdown(target);
      _cdTimer = setInterval(() => tickCountdown(target), 1000);
    } else {
      info.textContent = 'Расписание стримов пока не задано';
    }
  } catch (e) {
    console.error(e);
    info.textContent = 'Ошибка загрузки';
  }
}
function tickCountdown(targetMs) {
  const diff = Math.max(0, targetMs - Date.now());
  $id('cd-days').textContent = Math.floor(diff / 86400000);
  $id('cd-hours').textContent = String(Math.floor((diff % 86400000) / 3600000)).padStart(2, '0');
  $id('cd-mins').textContent = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0');
}
function openTwitch() {
  if (!twitchUrl) { showToast('Ссылка на стрим пока не задана', 'error'); return; }
  if (tg?.openLink) tg.openLink(twitchUrl); else window.open(twitchUrl, '_blank');
}

/* ── Топ (в стиле макета: медали, строки lb-item) ── */
async function loadTop(sort) {
  sort = sort || window.__topSort || 'score';
  window.__topSort = sort;
  document.querySelectorAll('.top-sort-btn').forEach(b => b.classList.toggle('active', b.dataset.sort === sort));
  const list = $id('top-list');
  list.innerHTML = '<div class="lb-empty">Загрузка...</div>';
  try {
    const res = await fetch('/api/top?limit=10&sort=' + encodeURIComponent(sort));
    const data = await res.json();
    if (!data || !data.length) {
      const empty = { cards: 'Пока ни у кого нет карточек', coins: 'Пока ни у кого нет монет',
        stars: 'Пока никто не включил показ звёзд в топе' }[sort] || 'Пока никого нет в топе';
      list.innerHTML = '<div class="lb-empty">' + empty + '</div>';
      return;
    }
    const medal = ['#f5c518', '#c0c0c0', '#cd7f32'], cls = ['lb-gold', 'lb-silver', 'lb-bronze'];
    const star = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>';
    const right = u => ({ score: u.score + ' 📍', cards: u.cards_unique + ' 🃏', coins: u.coins + ' 🪙', stars: (u.stars || 0) + ' ⭐' }[sort]);
    list.innerHTML = data.map((u, i) => {
      const display = (u.username ? '@' + u.username : 'ID:' + u.user_id) + (u.donor ? ' 💎' : '');
      const meta = [u.status || '', '🃏 ' + (u.cards_unique || 0), '🪙 ' + (u.coins || 0), u.stars != null ? '⭐ ' + u.stars : ''].filter(Boolean).join(' · ');
      const rank = i < 3 ? `<div class="lb-rank lb-medal" style="color:${medal[i]}">${star}</div>` : `<div class="lb-rank lb-num">${i + 1}</div>`;
      const letter = esc((u.username || String(u.user_id) || '?').charAt(0).toUpperCase());
      return `<div class="lb-item ${cls[i] || ''}">${rank}
        <div class="lb-ava"><span>${letter}</span><img src="/api/avatar/${encodeURIComponent(u.user_id)}" alt="" loading="lazy" onerror="this.remove()"></div>
        <div class="lb-info"><div class="lb-name">${esc(display)}</div><div class="lb-role">${esc(meta)}</div></div>
        <div class="lb-score">${esc(right(u))}</div></div>`;
    }).join('');
  } catch (e) {
    console.error(e);
    list.innerHTML = '<div class="lb-empty">Ошибка загрузки</div>';
  }
}

/* ── Админ ── */
async function checkIsAdmin() {
  try {
    if (!tg?.initData) return;
    const res = await fetch('/api/admin/check', { headers: { 'X-Telegram-Init-Data': tg.initData } });
    if (res.ok) {
      isAdmin = (await res.json()).is_admin;
      const b = $id('admin-nav-btn'); if (b) b.style.display = isAdmin ? 'inline-flex' : 'none';
    }
  } catch (e) { console.error('Ошибка проверки админа:', e); }
}
let activePanel = null;
function adminAction(action) {
  if (action === 'chbd') { adminToggleChbd(!window.__chbdOn); return; }
  if (action === 'trash') { adminToggleTrash(!window.__trashOn); return; }
  document.querySelectorAll('.admin-panel').forEach(p => p.style.display = 'none');
  if (activePanel === action) { activePanel = null; return; }
  activePanel = action;
  const panel = $id('panel-' + action);
  if (panel) { panel.style.display = 'block'; setTimeout(() => panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50); }
}

async function adminBroadcast() {
  const text = document.getElementById('broadcast-text').value.trim();
  const type = document.querySelector('[data-broadcast-type].toggle-btn.active')?.getAttribute('data-broadcast-type') || 'subscribers';

  if (!text) {
    showToast('Напиши текст!', 'error');
    return;
  }

  try {
    const initData = tg?.initData;
    if (!initData) {
      showToast('Ошибка: нет initData', 'error');
      return;
    }

    const endpoint = type === 'all' ? '/api/admin/super_broadcast' : '/api/admin/broadcast';
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: JSON.stringify({ text: text })
    });

    if (!res.ok) {
      showToast('Ошибка при отправке', 'error');
      return;
    }

    const data = await res.json();
    showToast(`✅ Отправлено! (${data.sent || 0} человек)`, 'success');
    document.getElementById('broadcast-text').value = '';
    updateCharCount('broadcast-text', 'broadcast-count');
  } catch (e) {
    console.error(e);
    showToast('Ошибка сети', 'error');
  }
}

async function adminToggleChbd(state) {
  try {
    const initData = tg?.initData;
    if (!initData) return;

    const endpoint = state ? '/api/admin/chbd_on' : '/api/admin/chbd_off';
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'X-Telegram-Init-Data': initData }
    });

    if (!res.ok) throw new Error('Failed');

    showToast(state ? '✅ ЧБД включена!' : '❌ ЧБД выключена!', 'success');
    loadChbdStatusAdmin();
    loadChbdStatus();
  } catch (e) {
    console.error(e);
    showToast('Ошибка', 'error');
  }
}

async function loadChbdStatusAdmin() {
  try {
    const res = await fetch('/api/chbd_status');
    const data = await res.json();
    const status = document.getElementById('chbd-admin-status');
    const badge = document.getElementById('chbd-badge');

    window.__chbdOn = !!data.enabled;
    if (status) status.textContent = data.enabled ? '🟢 ЧБД ВКЛЮЧЕНА' : '🔴 ЧБД ВЫКЛЮЧЕНА';
    if (badge) { badge.className = data.enabled ? 'admin-badge-on' : 'admin-badge-off'; badge.textContent = data.enabled ? 'ВКЛ' : 'ВЫКЛ'; }
  } catch (e) {
    console.error(e);
  }
}

async function adminSms() {
  const userId = document.getElementById('dm-userid').value.trim();
  const text = document.getElementById('dm-text').value.trim();

  if (!userId) {
    showToast('Введи ID пользователя', 'error');
    return;
  }
  if (!text) {
    showToast('Напиши текст сообщения', 'error');
    return;
  }

  try {
    const initData = tg?.initData;
    if (!initData) {
      showToast('Ошибка: нет initData', 'error');
      return;
    }

    const res = await fetch('/api/admin/sms', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: JSON.stringify({
        user_id: parseInt(userId),
        text: text
      })
    });

    if (!res.ok) {
      showToast('Ошибка при отправке', 'error');
      return;
    }

    showToast('✅ Сообщение отправлено!', 'success');
    document.getElementById('dm-userid').value = '';
    document.getElementById('dm-text').value = '';
    updateCharCount('dm-text', 'dm-count');
  } catch (e) {
    console.error(e);
    showToast('Ошибка сети', 'error');
  }
}

async function adminBan() {
  const userId = document.getElementById('ban-userid').value.trim();

  if (!userId) {
    showToast('Введи ID пользователя', 'error');
    return;
  }

  if (!confirm(`⚠️ Уверен, что хочешь забанить пользователя ${userId}?`)) return;

  try {
    const initData = tg?.initData;
    if (!initData) return;

    const res = await fetch(`/api/admin/ban/${userId}`, {
      method: 'POST',
      headers: { 'X-Telegram-Init-Data': initData }
    });

    if (!res.ok) throw new Error('Failed');

    document.getElementById('ban-userid').value = '';
    showToast('✅ Пользователь забанен!', 'success');
  } catch (e) {
    console.error(e);
    showToast('Ошибка при бане', 'error');
  }
}

async function adminGetStats() {
  const userId = document.getElementById('stats-userid').value.trim();
  const result = document.getElementById('stats-result');

  if (!userId) {
    showToast('Введи ID пользователя', 'error');
    return;
  }

  try {
    const initData = tg?.initData;
    if (!initData) return;

    const res = await fetch(`/api/admin/stats/${userId}`, {
      headers: { 'X-Telegram-Init-Data': initData }
    });

    if (!res.ok) {
      showToast('Пользователь не найден', 'error');
      result.style.display = 'none';
      return;
    }

    const data = await res.json();
    result.innerHTML = `
      <strong>ID:</strong> ${escapeHtml(data.user_id)}<br>
      <strong>Ник:</strong> ${escapeHtml(data.username) || 'нет'}<br>
      <strong>Вопросы:</strong> ${(data.questions_anonymous||0) + (data.questions_named||0)}<br>
      <strong>Идеи:</strong> ${(data.ideas||0) + (data.ads||0) + (data.cooperation||0) + (data.other_proposals||0)}<br>
      <strong>ЧБД:</strong> ${data.story||0}<br>
      <strong>Статус:</strong> ${data.status}
    `;
    result.style.display = 'block';
    showToast('✅ Статистика загружена', 'success');
  } catch (e) {
    console.error(e);
    showToast('Ошибка', 'error');
  }
}

async function adminGetMessages(type) {
  const result = document.getElementById('messages-result');
  result.style.display = 'none';
  result.textContent = 'Загрузка...';
  result.style.display = 'block';

  try {
    const initData = tg?.initData;
    if (!initData) return;

    const res = await fetch(`/api/admin/messages?type=${type}`, {
      headers: { 'X-Telegram-Init-Data': initData }
    });

    if (!res.ok) throw new Error('Failed');

    const data = await res.json();
    if (!data.messages || data.messages.length === 0) {
      result.textContent = 'Нет сообщений';
      return;
    }

    result.innerHTML = data.messages.map(m => `
      <div style="margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,.1)">
        <strong>${escapeHtml(m.username || m.user_id)}</strong><br>
        ${escapeHtml(m.text)}
      </div>
    `).join('');
  } catch (e) {
    console.error(e);
    result.textContent = 'Ошибка загрузки';
  }
}
// ═══ Профиль ═══
async function loadProfile() {
  const initData = tg?.initData;
  if (!initData) {
    showToast('Открой приложение через кнопку в боте', 'error');
    return;
  }

  try {
    const res = await fetch('/api/profile', {
      headers: { 'X-Telegram-Init-Data': initData }
    });

    if (!res.ok) throw new Error('auth failed');

    const u = await res.json();
    const name = u.username ? '@' + escapeHtml(u.username) : escapeHtml(u.first_name || 'Ты');
    const initial = (u.first_name || u.username || '?').charAt(0).toUpperCase();

    document.getElementById('user-name').textContent = name;
    document.getElementById('avatar-letter').textContent = initial;
    setProfileAvatar();
    document.getElementById('user-score').textContent = `${u.score || 0} очков`;

    const totalQ = (u.questions_anonymous || 0) + (u.questions_named || 0);
    const totalP = (u.ideas || 0) + (u.ads || 0) + (u.cooperation || 0) + (u.other_proposals || 0);
    
    document.getElementById('stat-questions').textContent = totalQ;
    document.getElementById('stat-proposals').textContent = totalP;
    document.getElementById('stat-chbd').textContent = u.story || 0;

    // Статус считает бот (или админ выдал вручную) — просто показываем его
    const status = u.status || '🌟 Новичок';
    const currentScore = u.score || 0;
    const GOAL = 50; // 50 действий — статус «Легенда»

    document.getElementById('user-rank').textContent = status;
    document.getElementById('rank-current').textContent = status;

    const RANKS = [
      { key: 'Новичок',   label: '🌟 Новичок',   need: 'старт' },
      { key: 'Вопросник', label: '💬 Вопросник', need: '5 вопросов' },
      { key: 'Идеатор',   label: '💡 Идеатор',   need: '3 идеи или предложения' },
      { key: 'Сценарист', label: '🎬 Сценарист', need: '5 продолжений в ЧБД' },
      { key: 'Легенда',   label: '💎 Легенда',   need: '50 действий всего' },
    ];
    document.getElementById('ranks-list').innerHTML = RANKS.map(r =>
      `<div class="rank-row${status.includes(r.key) ? ' active-rank' : ''}">${r.label} — ${r.need}</div>`
    ).join('');

    if (currentScore < GOAL) {
      document.getElementById('rank-next').textContent = '💎 Легенда →';
      document.getElementById('progress-fill').style.width = Math.min(100, (currentScore / GOAL) * 100) + '%';
      document.getElementById('progress-text').textContent = `${currentScore} / ${GOAL} действий до Легенды`;
    } else {
      document.getElementById('rank-next').textContent = '';
      document.getElementById('progress-fill').style.width = '100%';
      document.getElementById('progress-text').textContent = 'Максимальный уровень!';
    }
  } catch (e) {
    console.error(e);
    showToast('Не удалось загрузить профиль', 'error');
  }
}

// ═══ Формы ═══
async function submitQuestion() {
  const text = document.getElementById('question-text').value.trim();
  const anonymous = document.querySelector('[data-type].toggle-btn.active')?.getAttribute('data-type') === 'anonymous';

  if (!text) {
    showToast('Напиши вопрос!', 'error');
    return;
  }

  try {
    const initData = tg?.initData;
    if (!initData) {
      showToast('Ошибка: не найдены данные Telegram', 'error');
      return;
    }

    const res = await fetch('/api/question', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: JSON.stringify({
        text: text,
        anonymous: anonymous,
      }),
    });

    if (!res.ok) {
      const error = await res.json();
      showToast(errMsg(error.detail, 'Ошибка при отправке'), 'error');
      return;
    }

    showToast('✅ Вопрос отправлен! Спасибо! 👀', 'success');
    document.getElementById('question-text').value = '';
    updateCharCount('question-text', 'question-count');
  } catch (e) {
    console.error('Ошибка:', e);
    showToast('Ошибка сети. Попробуй ещё раз', 'error');
  }
}

async function submitStory() {
  const text = document.getElementById('chbd-text').value.trim();

  if (!text) {
    showToast('Напиши, что было дальше!', 'error');
    return;
  }

  try {
    const initData = tg?.initData;
    if (!initData) {
      showToast('Ошибка: не найдены данные Telegram', 'error');
      return;
    }

    const res = await fetch('/api/story', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: JSON.stringify({
        text: text,
      }),
    });

    if (!res.ok) {
      const error = await res.json();
      showToast(errMsg(error.detail, 'Ошибка при отправке'), 'error');
      return;
    }

    showToast('✅ Продолжение отправлено! Удачи в конкурсе ЧБД! 🚀', 'success');
    document.getElementById('chbd-text').value = '';
    updateCharCount('chbd-text', 'chbd-count');
  } catch (e) {
    console.error('Ошибка:', e);
    showToast('Ошибка сети. Попробуй ещё раз', 'error');
  }
}

async function submitIdea() {
  const text = document.getElementById('suggest-text').value.trim();
  if (!text) {
    showToast('Напиши идею!', 'error');
    return;
  }

  const initData = tg?.initData;
  if (!initData) {
    showToast('Ошибка: не найдены данные Telegram', 'error');
    return;
  }

  try {
    const res = await fetch('/api/idea', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: JSON.stringify({ text: text, idea_type: currentIdeaType }),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      showToast(errMsg(error.detail, 'Ошибка при отправке'), 'error');
      return;
    }

    showToast('✅ Идея отправлена! Спасибо за предложение! 💡', 'success');
    document.getElementById('suggest-text').value = '';
    updateCharCount('suggest-text', 'suggest-count');
  } catch (e) {
    console.error(e);
    showToast('Ошибка сети. Попробуй ещё раз', 'error');
  }
}
async function loadChbdStatus() {
  try {
    const res = await fetch('/api/chbd_status');
    const data = await res.json();

    const statusBox = document.getElementById('chbd-status-info');
    const form = document.getElementById('chbd-form');

    if (data.enabled) {
      statusBox.style.display = 'none';
      form.style.display = 'block';
    } else {
      statusBox.textContent = '🔴 ЧБД сейчас выключена — режим включается во время стрима. Следи за анонсами!';
      statusBox.style.display = 'block';
      form.style.display = 'none';
    }
  } catch (e) {
    console.error('Ошибка при загрузке статуса ЧБД:', e);
  }
}


// ═══════════════════════════════════════════════
// МЕДИА → РОМЕ (запись и отправка идёт в чате с ботом)
// ═══════════════════════════════════════════════

function openBotMedia() {
  const url = 'https://t.me/alonsochbot?start=media';
  if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, '_blank');
}

// ═══════════════════════════════════════════════
// ТРЕШ ИСТОРИИ
// ═══════════════════════════════════════════════

async function submitTrash() {
  const text = document.getElementById('trash-text').value.trim();
  if (!text) { showToast('Напиши свою историю!', 'error'); return; }
  try {
    const initData = tg?.initData;
    if (!initData) { showToast('Ошибка: не найдены данные Telegram', 'error'); return; }
    const res = await fetch('/api/trash', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      showToast(errMsg(error.detail, 'Ошибка при отправке'), 'error');
      return;
    }
    showToast('✅ История отправлена Роме! Удачи 🍀', 'success');
    document.getElementById('trash-text').value = '';
    updateCharCount('trash-text', 'trash-count');
  } catch (e) {
    console.error('Ошибка:', e);
    showToast('Ошибка сети. Попробуй ещё раз', 'error');
  }
}

async function loadTrashStatus() {
  try {
    const res = await fetch('/api/trash_status');
    const data = await res.json();
    const box = document.getElementById('trash-status-info');
    const form = document.getElementById('trash-form');
    if (!box || !form) return;
    if (data.enabled) {
      box.style.display = 'none';
      form.style.display = 'block';
    } else {
      box.textContent = '🔴 Приём треш историй закрыт — его открывают, когда на стриме объявляют треш истории. Следи за анонсами!';
      box.style.display = 'block';
      form.style.display = 'none';
    }
  } catch (e) {
    console.error('Ошибка при загрузке статуса треш историй:', e);
  }
}

async function adminToggleTrash(state) {
  try {
    const initData = tg?.initData;
    if (!initData) return;
    const res = await fetch(state ? '/api/admin/trash_on' : '/api/admin/trash_off', {
      method: 'POST',
      headers: { 'X-Telegram-Init-Data': initData }
    });
    if (!res.ok) throw new Error('Failed');
    showToast(state ? '✅ Треш истории открыты!' : '❌ Треш истории закрыты!', 'success');
    loadTrashStatusAdmin();
    loadTrashStatus();
  } catch (e) {
    console.error(e);
    showToast('Ошибка', 'error');
  }
}

async function loadTrashStatusAdmin() {
  try {
    const res = await fetch('/api/trash_status');
    const data = await res.json();
    const badge = document.getElementById('trash-badge');
    window.__trashOn = !!data.enabled;
    if (badge) { badge.className = data.enabled ? 'admin-badge-on' : 'admin-badge-off'; badge.textContent = data.enabled ? 'ВКЛ' : 'ВЫКЛ'; }
  } catch (e) {
    console.error(e);
  }
}

// ═══════════════════════════════════════════════
// РАБОТА С СИМВОЛАМИ
// ═══════════════════════════════════════════════

function updateCharCount(textareaId, countId) {
  const textarea = document.getElementById(textareaId);
  const counter = document.getElementById(countId);
  const length = textarea.value.length;
  counter.textContent = `${length} симв.`;
}

// ═══ Аватар ═══
async function setProfileAvatar() {
  const img = document.getElementById('avatar-img');
  const letter = document.getElementById('avatar-letter');
  if (!img) return;

  const show = (src) => {
    img.onload = () => {
      img.style.display = 'block';
      if (letter) letter.style.display = 'none';
    };
    img.onerror = () => { img.style.display = 'none'; };
    img.src = src;
  };

  // Основной способ: бот сам достаёт фото профиля (работает всегда, не только
  // когда Telegram передаёт photo_url).
  try {
    const res = await fetch('/api/my_avatar', {
      headers: { 'X-Telegram-Init-Data': tg?.initData || '' }
    });
    if (res.ok) {
      show(URL.createObjectURL(await res.blob()));
      return;
    }
  } catch (e) {
    console.error(e);
  }

  // Запасной вариант
  const photoUrl = tg?.initDataUnsafe?.user?.photo_url;
  if (photoUrl) show(photoUrl);
}

// ═══ Время стрима (админ) ═══
async function adminSetStreamTime() {
  const value = document.getElementById('stream-time-input').value;
  if (!value) {
    showToast('Выбери дату и время', 'error');
    return;
  }
  try {
    const res = await fetch('/api/admin/stream_time', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': tg?.initData || '',
      },
      body: JSON.stringify({ target_iso: value }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showToast(errMsg(data.detail, 'Ошибка'), 'error');
      return;
    }
    showToast('✅ Время стрима обновлено', 'success');
    loadCountdown();
  } catch (e) {
    console.error(e);
    showToast('Ошибка сети', 'error');
  }
}

async function adminClearStreamTime() {
  try {
    const res = await fetch('/api/admin/stream_time/clear', {
      method: 'POST',
      headers: { 'X-Telegram-Init-Data': tg?.initData || '' },
    });
    if (!res.ok) {
      showToast('Ошибка', 'error');
      return;
    }
    showToast('✅ Таймер снова считает по расписанию', 'success');
    loadCountdown();
  } catch (e) {
    console.error(e);
    showToast('Ошибка сети', 'error');
  }
}

// ═══ Индикатор отправки ═══
function wrapBusy(fnName, busyText) {
  const original = window[fnName];
  if (typeof original !== 'function') return;

  window[fnName] = async function (...args) {
    const btn = document.querySelector(`[onclick^="${fnName}("]`);
    if (btn && btn.disabled) return;

    const oldHtml = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.style.opacity = '0.7';
      btn.textContent = busyText || 'Отправляем...';
    }
    try {
      return await original.apply(this, args);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.style.opacity = '';
        btn.innerHTML = oldHtml;
      }
    }
  };
}

['submitQuestion', 'submitStory', 'submitTrash', 'submitIdea'].forEach(n => wrapBusy(n, 'Отправляем...'));
['adminBroadcast', 'adminSms'].forEach(n => wrapBusy(n, 'Отправляем... (рассылка может занять время)'));
['adminBan', 'adminSetStreamTime', 'adminClearStreamTime'].forEach(n => wrapBusy(n, 'Подожди...'));

/* ═══════════════════════════════════════════════════════════
   AI-чат «Алонс» (интерфейс макета + сервер бота: /api/ai/chat, /api/ai/reset)
═══════════════════════════════════════════════════════════ */
const AI_KEY = 'alonso_ai_v2';
let aiHistory = (() => { try { return JSON.parse(localStorage.getItem(AI_KEY) || '[]'); } catch { return []; } })();
let aiBusy = false;
const aiOrb = { amp: 0, ampTarget: 0, spin: 0.35, spinTarget: 0.35, kick: 0 };
const AI_CHIPS = ['Когда следующий стрим?', 'Кто такой Рома Алонсо?', 'Где все соцсети Ромы?', 'Как работают статусы и топ?'];

function aiSave() { try { localStorage.setItem(AI_KEY, JSON.stringify(aiHistory.slice(-40))); } catch (e) {} }
function aiScroll() { requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })); }

const FWD_LABELS = { question: '❓ Отправить Роме как вопрос', idea: '💡 Отправить Роме как идею', story: '🎬 Отправить в ЧБД' };
function aiMsgHtml(m, i) {
  const bubble = `<div class="ai-bubble">${esc(m.text)}</div>`;
  if (m.role === 'user') return `<div class="ai-msg me">${bubble}</div>`;
  let extra = '';
  if (FWD_LABELS[m.intent] && m.orig) {
    extra = `<div class="ai-extra"><div class="ai-note">⚠️ Роме это пока не отправлено — отвечает ИИ.</div>
      <button class="ai-forward-btn" onclick="aiForward(${i})">${FWD_LABELS[m.intent]}</button></div>`;
  }
  return `<div class="ai-msg bot">${bubble}${extra}</div>`;
}
function aiRender() {
  const box = $id('ai-thread'); if (!box) return;
  if (!aiHistory.length) {
    box.innerHTML = `<div class="ai-hello"><div class="ai-hello-t">Привет, я Алонс 🤖</div>
      <div class="ai-hello-s">Я нейросеть, а не Рома. Расскажу про Рому, стримы и соцсети, помогу разобраться в боте.</div>
      <div class="ai-warning">⚠️ <strong>Роме этот чат не приходит.</strong> Чтобы Рома получил вопрос, идею или продолжение ЧБД, отправь их во вкладке «Вопросы».</div>
      <div class="ai-chips">${AI_CHIPS.map(c => `<button class="ai-forward-btn" onclick="aiSend(this.textContent)">${esc(c)}</button>`).join('')}</div></div>`;
    return;
  }
  box.innerHTML = aiHistory.map(aiMsgHtml).join('');
}
function aiForward(i) {
  const m = aiHistory[i]; if (!m) return;
  const map = { question: ['questions', 'question-text', 'question-count'], idea: ['suggest', 'suggest-text', 'suggest-count'], story: ['chbd', 'chbd-text', 'chbd-count'] }[m.intent];
  if (!map) return;
  goToTab('interact', map[0]);
  setTimeout(() => { const f = $id(map[1]); if (f) { f.value = m.orig; updateCharCount(map[1], map[2]); } }, 120);
  showToast('Текст подставлен — проверь и нажми «Отправить»');
}

async function aiSend(text) {
  text = String(text || '').trim();
  if (aiBusy || !text) return;
  if (!tg?.initData) { showToast('Открой приложение через Telegram', 'error'); return; }
  aiBusy = true;
  aiHistory.push({ role: 'user', text });
  aiSave(); aiRender();
  const box = $id('ai-thread');
  const typing = document.createElement('div');
  typing.className = 'ai-msg bot';
  typing.innerHTML = '<div class="ai-bubble ai-typing"><i></i><i></i><i></i></div>';
  box.appendChild(typing); aiScroll();
  aiOrb.kick = 1; aiOrb.spinTarget = 1.3; aiOrb.ampTarget = 0.9;

  let reply = '', intent = null;
  try {
    const res = await fetch('/api/ai/chat', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg.initData },
      body: JSON.stringify({ text }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) reply = errMsg(data.detail, 'Не получилось ответить. Попробуй ещё раз.');
    else { reply = data.answer || 'Пустой ответ, попробуй ещё раз.'; intent = data.intent || null; }
  } catch (e) { console.error(e); reply = 'Ошибка сети. Попробуй ещё раз.'; }

  aiOrb.spinTarget = 0.35; aiOrb.ampTarget = 0;
  const bubble = typing.querySelector('.ai-bubble');
  bubble.classList.remove('ai-typing'); bubble.textContent = '';
  const words = reply.split(/(\s+)/);
  for (let i = 0; i < words.length; i++) {
    bubble.textContent += words[i];
    if (words[i].trim() && i % 2 === 0) await sleep(30);
    if (i % 12 === 0) aiScroll();
  }
  aiHistory.push({ role: 'assistant', text: reply, intent, orig: text });
  aiSave(); aiBusy = false;
  aiRender(); aiScroll();
  const s = $id('ai-send'); if (s) s.disabled = !$id('ai-input').value.trim();
}
async function aiReset() {
  if (aiBusy) return;
  aiHistory = []; aiSave(); aiRender();
  try { await fetch('/api/ai/reset', { method: 'POST', headers: { 'X-Telegram-Init-Data': tg?.initData || '' } }); }
  catch (e) { console.error(e); }
}

(function initAiChat() {
  const form = $id('ai-bar'), input = $id('ai-input'), send = $id('ai-send');
  if (!form) return;
  aiRender();
  input.addEventListener('input', () => {
    send.disabled = !input.value.trim() || aiBusy;
    aiOrb.ampTarget = Math.max(aiOrb.ampTarget, 0.55); aiOrb.kick = Math.min(1, aiOrb.kick + 0.25);
    clearTimeout(input._t); input._t = setTimeout(() => { if (!aiBusy) aiOrb.ampTarget = 0; }, 700);
  });
  input.addEventListener('focus', () => { if (!aiBusy) aiOrb.spinTarget = 0.7; });
  input.addEventListener('blur', () => { if (!aiBusy) aiOrb.spinTarget = 0.35; });
  form.addEventListener('submit', e => {
    e.preventDefault();
    const v = input.value; if (!v.trim() || aiBusy) return;
    input.value = ''; send.disabled = true;
    aiSend(v);
  });
  $id('ai-clear').addEventListener('click', aiReset);

  /* Шар: 3D-шейдер, вращается и деформируется (сильнее при наборе и «раздумьях») */
  const canvas = $id('ai-orb'); const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true });
  if (!gl) return;
  const fs = `precision mediump float;uniform vec2 r;uniform float t,amp,ph;
  mat2 rot(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}
  float hash(vec3 p){p=fract(p*.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
  float noise(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);
   return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
              mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
  float map(vec3 p){p.xz*=rot(ph);p.xy*=rot(ph*.7);
   float d=length(p)-.74;d+=(noise(p*1.9+t*.45)-.5)*(.42+amp*.6);return d*.6;}
  void main(){vec2 uv=(gl_FragCoord.xy-.5*r)/r.y*2.;vec3 ro=vec3(0.,0.,2.3),rd=normalize(vec3(uv,-1.9));
   float tt=0.,hit=0.;for(int i=0;i<44;i++){float d=map(ro+rd*tt);if(d<.003){hit=1.;break;}tt+=d;if(tt>5.)break;}
   if(hit<.5){gl_FragColor=vec4(0.);return;}
   vec3 p=ro+rd*tt;vec2 e=vec2(.012,0.);
   vec3 n=normalize(vec3(map(p+e.xyy)-map(p-e.xyy),map(p+e.yxy)-map(p-e.yxy),map(p+e.yyx)-map(p-e.yyx)));
   vec3 l=normalize(vec3(-.55,.75,.8));float dif=max(dot(n,l),0.);
   float spec=pow(max(dot(reflect(-l,n),-rd),0.),22.);float fres=pow(1.-max(dot(n,-rd),0.),3.);
   vec3 col=vec3(.05)+vec3(.30)*dif+vec3(.85)*spec*.55+fres*vec3(.30,.36,.55)*.75;
   gl_FragColor=vec4(col,1.);}`;
  const mk = (ty, src) => { const s = gl.createShader(ty); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.warn('orb shader', gl.getShaderInfoLog(s)); return s; };
  const p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, 'attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}'));
  gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
  gl.useProgram(p);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(p, 'a'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = n => gl.getUniformLocation(p, n), uR = U('r'), uT = U('t'), uA = U('amp'), uP = U('ph');
  const dpr = Math.min(devicePixelRatio || 1, 2), size = Math.round(56 * dpr);
  canvas.width = size; canvas.height = size; gl.viewport(0, 0, size, size);
  let last = performance.now(), time = 0, phase = 0;
  (function frame(now) {
    requestAnimationFrame(frame);
    if (document.hidden || canvas.offsetParent === null) { last = now; return; }
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    aiOrb.amp  += (aiOrb.ampTarget - aiOrb.amp) * Math.min(1, dt * 4);
    aiOrb.spin += (aiOrb.spinTarget - aiOrb.spin) * Math.min(1, dt * 3);
    aiOrb.kick  = Math.max(0, aiOrb.kick - dt * 1.4);
    time += dt * (0.8 + aiOrb.spin); phase += dt * aiOrb.spin;
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(uR, size, size); gl.uniform1f(uT, time);
    gl.uniform1f(uA, aiOrb.amp + aiOrb.kick * 0.35 + (aiBusy ? 0.15 * Math.sin(now / 280) : 0)); gl.uniform1f(uP, phase);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  })(performance.now());
})();


/* ── Друзья (реферальная программа) ── */
const FR_RARITY = { common: 'обычная', uncommon: 'необычная', rare: 'редкая', epic: 'эпическая', legendary: 'легендарная' };
let frLink = '';

function frDate(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function frRow(name, meta, right) {
  const letter = esc((name.replace('@', '') || '?').charAt(0).toUpperCase());
  return `<div class="lb-item"><div class="lb-ava"><span>${letter}</span></div>
    <div class="lb-info"><div class="lb-name">${esc(name)}</div><div class="lb-role">${esc(meta)}</div></div>
    ${right ? `<div class="lb-score">${esc(right)}</div>` : ''}</div>`;
}

async function loadFriends() {
  const list = $id('fr-list');
  if (!tg?.initData) { showToast('Открой приложение через кнопку в боте', 'error'); return; }
  try {
    const res = await fetch('/api/friends', { headers: { 'X-Telegram-Init-Data': tg.initData } });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(errMsg(d.detail, 'Не удалось загрузить'));
    renderFriends(d);
  } catch (e) {
    console.error(e);
    if (list) list.innerHTML = '<div class="lb-empty">Ошибка загрузки</div>';
    showToast(e.message, 'error');
  }
}

function renderFriends(d) {
  frLink = d.link || '';
  $id('fr-link').value = frLink;
  $id('fr-badge').textContent = d.count;

  // правила: сколько получает друг и пригласивший
  const tiers = (d.tiers || []).map((t, i, a) => {
    const to = a[i + 1] ? a[i + 1].from - 1 : null;
    const range = t.from === to ? `${t.from}-й друг` : (to ? `${t.from}–${to}-й друг` : `${t.from}-й и дальше`);
    return `${range}: +${t.coins} 🪙`;
  }).join(' · ');
  const rules = [`Друг получает +${d.friend_coins} 🪙 сразу.`, `Ты получаешь за каждого друга: ${tiers}.`];
  if (d.daily_limit) rules.push(`Награда за приглашения — до ${d.daily_limit} друзей в сутки.`);
  $id('fr-rules').textContent = rules.join(' ');

  // награды за количество друзей
  $id('fr-milestones').innerHTML = (d.milestones || []).map(m => {
    const cards = (m.cards || []).map(r => (FR_RARITY[r] || r) + ' карточка').join(' + ');
    const prize = [m.coins ? '+' + m.coins + ' 🪙' : '', cards ? cards + ' (или лучше)' : ''].filter(Boolean).join(' и ');
    return `<div class="fr-mile ${m.done ? 'done' : ''}"><span class="fr-mile-n">${m.need}</span>
      <span class="fr-mile-t">${m.done ? '✅' : '🎁'} ${esc(prize)}</span></div>`;
  }).join('');
  const last = (d.milestones || [])[(d.milestones || []).length - 1];
  const nxt = d.next_milestone;
  const goal = nxt ? nxt.need : (last ? last.need : 1);
  $id('fr-progress').style.width = Math.min(100, Math.round(d.count / goal * 100)) + '%';
  $id('fr-progress-text').textContent = nxt
    ? `${d.count} / ${nxt.need} друзей до следующей награды`
    : `Все награды за друзей получены (${d.count}) 🎉`;

  // кто пригласил меня
  const by = d.invited_by;
  $id('fr-by-card').style.display = by ? '' : 'none';
  $id('fr-by').innerHTML = by ? frRow(by.name, 'пригласил(а) тебя · ' + frDate(by.ts), '+' + by.coins + ' 🪙') : '';

  // кого пригласил я
  const list = $id('fr-list');
  list.innerHTML = (d.invited || []).length
    ? d.invited.map(f => frRow(
        f.name,
        frDate(f.ts) + ((f.cards && f.cards.length) ? ' · 🎁 ' + f.cards.join(', ') : '') + (f.rewarded ? '' : ' · лимит за день'),
        f.rewarded ? '+' + f.coins + ' 🪙' : ''
      )).join('')
    : '<div class="lb-empty">Пока никого. Отправь ссылку другу 👆</div>';
}

$id('fr-copy')?.addEventListener('click', async () => {
  if (!frLink) return;
  try { await navigator.clipboard.writeText(frLink); }
  catch (e) {
    const i = $id('fr-link'); i.focus(); i.select();
    try { document.execCommand('copy'); } catch (_) { /* пользователь скопирует вручную */ }
  }
  showToast('Ссылка скопирована');
});

$id('fr-share')?.addEventListener('click', () => {
  if (!frLink) return;
  const text = 'Залетай в бота Ромы Алонсо — карточки, вопросы и призы. По моей ссылке получишь бонус 🎁';
  const url = 'https://t.me/share/url?url=' + encodeURIComponent(frLink) + '&text=' + encodeURIComponent(text);
  if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, '_blank');
});

/* ── Старт ── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-count="true"]').forEach(ta => {
    if (!ta.id) return;
    ta.addEventListener('input', () => updateCharCount(ta.id, ta.id.replace(/-text$/, '') + '-count'));
  });
  loadCountdown();
  loadChbdStatus();
  checkIsAdmin();
  // ссылка из меню бота: ?section=friends открывает игру на под-вкладке «Друзья»
  if (new URLSearchParams(location.search).get('section') === 'friends') goToTab('game', 'g-friends');
  const u = tg?.initDataUnsafe?.user;
  if (u) {
    const un = $id('user-name'); if (un) un.textContent = u.username ? '@' + u.username : (u.first_name || 'Ты');
    const al = $id('avatar-letter'); if (al) al.textContent = (u.first_name || u.username || '?')[0].toUpperCase();
  }
});
