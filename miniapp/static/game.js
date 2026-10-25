/* ═══════════════════════════════════════════════════════════
   ИГРА «КАРТОЧКИ» — дизайн нового макета + серверная логика бота (/api/game/*).
   Случайность, монеты, звёзды, дуэли и обмен — только на сервере; здесь отрисовка.
═══════════════════════════════════════════════════════════ */

/* Иконки/цвета карточек из макета. У карточек без своей иконки — иконка по редкости. */
const CARD_ART = {"viewer":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\"/><circle cx=\"12\" cy=\"12\" r=\"3\"/></svg>","tc":"0 0% 22%"},"chatter":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z\"/></svg>","tc":"210 30% 20%"},"supporter":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z\"/></svg>","tc":"142 70% 20%"},"ideator":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><line x1=\"12\" y1=\"2\" x2=\"12\" y2=\"6\"/><path d=\"M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12z\"/><line x1=\"12\" y1=\"22\" x2=\"12\" y2=\"18\"/><line x1=\"4.22\" y1=\"4.22\" x2=\"5.64\" y2=\"5.64\"/><line x1=\"18.36\" y1=\"18.36\" x2=\"19.78\" y2=\"19.78\"/><line x1=\"2\" y1=\"12\" x2=\"6\" y2=\"12\"/><line x1=\"18\" y1=\"12\" x2=\"22\" y2=\"12\"/></svg>","tc":"45 80% 25%"},"streamer":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><polygon points=\"23 7 16 12 23 17 23 7\"/><rect x=\"1\" y=\"5\" width=\"15\" height=\"14\" rx=\"2\"/></svg>","tc":"220 80% 30%"},"mod":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z\"/></svg>","tc":"200 70% 25%"},"legend":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M6 9H4.5a2.5 2.5 0 0 1 0-5H6\"/><path d=\"M18 9h1.5a2.5 2.5 0 0 0 0-5H18\"/><path d=\"M4 22h16\"/><path d=\"M18 2H6v7a6 6 0 0 0 12 0V2Z\"/></svg>","tc":"270 60% 30%"},"alonso":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><polygon points=\"12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2\"/></svg>","tc":"35 90% 35%"},"hungry":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M3 11h18\"/><path d=\"M5 11a7 7 0 0 1 14 0\"/><path d=\"M4 15h16\"/><path d=\"M5 19h14\"/></svg>","tc":"25 60% 22%"},"sleepy":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z\"/></svg>","tc":"235 50% 25%"},"kind":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z\"/></svg>","tc":"150 60% 25%"},"evil":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M13 2L3 14h8l-1 8 10-12h-8z\"/></svg>","tc":"0 75% 28%"},"boss":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M2 18l3-11 5 5 2-8 2 8 5-5 3 11z\"/><path d=\"M2 21h20\"/></svg>","tc":"48 90% 35%"},"sly":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z\"/><path d=\"M8 12h8\"/></svg>","tc":"200 60% 25%"},"glam":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M6 3h12l4 6-10 12L2 9z\"/><path d=\"M2 9h20\"/></svg>","tc":"320 70% 30%"},"happy":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M8 14s1.5 2 4 2 4-2 4-2\"/><path d=\"M9 9h.01M15 9h.01\"/></svg>","tc":"30 80% 30%"},"melon":{"icon":"<svg width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M3 12a9 9 0 0 0 18 0z\"/><path d=\"M7 15h.01M12 17h.01M16 15h.01\"/></svg>","tc":"130 60% 25%"}};
const RARITY_ICON_FROM = { common:'viewer', uncommon:'supporter', rare:'mod', epic:'legend', legendary:'alonso' };
const RARITY_ORDER = ['common','uncommon','rare','epic','legendary'];
const RARITY_COLORS = {
  common:   { label:'Common',    cls:'common' },
  uncommon: { label:'Uncommon',  cls:'uncommon' },
  rare:     { label:'Rare',      cls:'rare' },
  epic:     { label:'Epic',      cls:'epic' },
  legendary:{ label:'Legendary', cls:'legendary' },
};
const RARITY_GLOW = { common:'#a1a1aa', uncommon:'#4ade80', rare:'#60a5fa', epic:'#c084fc', legendary:'#fbbf24' };

let ALL_CARDS = [];
function _hue(id) { let h = 0; for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }

/* Фон карточки: cards/<id>.jpg → role_*.jpg → старое фото → градиент (игра работает и без фото) */
function buildCatalog(cat) {
  ALL_CARDS = cat.map(c => {
    const art = CARD_ART[c.id] || CARD_ART[RARITY_ICON_FROM[c.rarity]];
    const sat = { common: 18, uncommon: 45, rare: 60, epic: 55, legendary: 75 }[c.rarity] || 30;
    const layers = [];
    if (c.photo) layers.push("url('" + c.photo + "')");
    (c.role_imgs || []).forEach(f => layers.push("url('" + f + "')"));
    if (c.legacy_img) layers.push("url('" + c.legacy_img + "')");
    layers.push('linear-gradient(145deg, hsl(' + _hue(c.id) + ' ' + sat + '% 26%), hsl(' + ((_hue(c.id) + 40) % 360) + ' ' + sat + '% 10%))');
    return { id: c.id, name: c.name, rarity: c.rarity, desc: c.desc, icon: art.icon, tc: art.tc, bg: layers.join(', ') };
  });
  document.querySelectorAll('.pk-ph[data-card]').forEach(el => {
    const c = ALL_CARDS.find(x => x.id === el.dataset.card);
    if (c) el.style.backgroundImage = c.bg;
  });
}

/* ═══ Состояние (приходит с сервера) ═══ */
let GAME = { stars: 0, collection: [], counts: {}, pvpWins: 0, challenge: null, trade: [], packs: {}, exchange: null };
let gameBusy = false, gameFxStarted = false;

function applyServerState(st) {
  if (!st) return;
  if (st.catalog && !ALL_CARDS.length) buildCatalog(st.catalog);
  const coll = [];
  Object.entries(st.cards || {}).forEach(([id, n]) => { for (let i = 0; i < n; i++) coll.push(id); });
  GAME = { stars: st.coins || 0,   // «stars» в коде = монеты 🪙
    collection: coll, counts: st.cards || {}, pvpWins: st.pvp_wins || 0, challenge: st.challenge || null,
    openCost: st.open_cost || 20, daily: st.daily || null, showStars: !!st.show_stars,
    trade: st.trade || [], contest: st.contest || null, completed: !!st.completed,
    packs: st.packs || {}, starsCap: st.stars_cap, pvpLeft: st.pvp_left, exchange: st.exchange || null,
    starter: st.starter || null, donor: st.donor || null, gifts: st.gifts || [], giftPrices: st.gift_prices || {}, giftItems: st.gift_items || [],
    botUsername: st.bot_username || (GAME && GAME.botUsername) || '' };
}
function getState() { return GAME; }
function countOf(id) { return (GAME.counts && GAME.counts[id]) || 0; }
function cardById(id) { return ALL_CARDS.find(c => c.id === id); }

async function gameApi(action, body) {
  const res = await fetch('/api/game/' + action, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '' },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) throw new Error('Сессия устарела. Закрой приложение и открой заново');
  if (!res.ok) throw new Error(errMsg(data.detail, 'Ошибка. Попробуй ещё раз'));
  applyServerState(data.state);
  return data;
}

function checkRewardToast(r) {
  if (r && r.reward_unlocked) {
    const c = GAME.contest || {};
    showToast('🏁 Ты собрал все карточки! Место в конкурсе: №' + (r.contest_place || '?') + '. ' + (c.everyone_reward ? 'Награда: ' + c.everyone_reward + '.' : ''));
  }
}

async function loadGame() {
  try {
    await gameApi('state');
    renderGame();
    renderPendingChallenge();
    claimPacks(0, true);   // купленные, но ещё не показанные паки
  } catch (e) { showToast(e.message, 'error'); }
  if (!gameFxStarted) {
    gameFxStarted = true;   // тяжёлые шейдеры запускаем, только когда игру открыли
    try { initNeuroNoise(); } catch (e) { console.error(e); }
    try { initPortal(); } catch (e) { console.error(e); }
    try {
      mountAurora($id('shop-canvas'), 0.6);
      mountAurora($id('exch-canvas'), 0.5, { c1:[.10,.01,.02], c2:[.72,.07,.12], c3:[1.0,.42,.22] });
    } catch (e) { console.error(e); }
  }
  handleChallengeLink();
}

const openCost = () => GAME.openCost || 20;

function renderGame() {
  const s = GAME;
  const owned = [...new Set(s.collection)];
  const set = (id, v) => { const el = $id(id); if (el) el.textContent = v; };
  set('g-count', owned.length);
  set('g-count-sub', 'из ' + ALL_CARDS.length + ' карточек');
  set('shop-balance', s.stars); set('g-stars', s.stars); set('g-stars-hint', s.stars); set('g-open-cost', openCost());

  const ranks = [{min:0,name:'Новичок'},{min:.1,name:'Коллекционер'},{min:.3,name:'Охотник'},{min:.6,name:'Эксперт'},{min:1,name:'Легенда'}];
  const share = ALL_CARDS.length ? owned.length / ALL_CARDS.length : 0;
  set('g-rank-badge', (ranks.slice().reverse().find(r => share >= r.min) || ranks[0]).name);
  set('reward-progress-text', owned.length + ' / ' + ALL_CARDS.length);
  const rpb = $id('reward-progress-bar'); if (rpb) rpb.style.width = Math.round(share * 100) + '%';

  // цены магазина — с сервера (game.py → PACKS), в HTML они только запасные
  Object.entries(s.packs || {}).forEach(([k, p]) => {
    document.querySelectorAll('[data-pack-price="' + k + '"]').forEach(el => el.textContent = p.stars);
  });
  const note = $id('shop-note');
  if (note) note.textContent = 'Оплата проходит через звёзды Telegram ⭐ в окне Telegram.' +
    (s.starsCap ? ' Лимит покупок — ' + s.starsCap + ' ⭐ в сутки (сбрасывается в 00:00 МСК).' : '');
  const spt = $id('stars-public-toggle');
  if (spt) { spt.checked = !!s.showStars; $id('stars-public-row').style.display = 'flex'; }
  set('pvp-left', s.pvpLeft ?? '—');
  const ss = $id('shop-status'); if (ss) ss.textContent = s.donor?.active ? '💎 Донатер · бонусы активны' : 'Паки — за звёзды Telegram ⭐';

  renderDaily(); renderOffers(); renderTrade(); renderContest(); renderCollection(); renderPvPCards(); renderFriendCards();
}

/* ═══ Ежедневный бонус ═══ */
function renderDaily() {
  const box = $id('daily-card'), d = GAME.daily;
  if (!box || !d) return;
  box.style.display = 'flex';
  const dtag = GAME.donor?.active ? ' · 💎 ×' + GAME.donor.daily_mult : '';
  const day = d.available ? d.streak + 1 : d.streak;
  const dots = Array.from({ length: 7 }, (_, i) => `<span class="daily-dot${i < ((day - 1) % 7) + (d.available ? 0 : 1) ? ' on' : ''}"></span>`).join('');
  if (d.available) {
    box.innerHTML = `<div><div class="daily-title">🎁 Ежедневный бонус: +${d.amount} 🪙${dtag}</div>
      <div class="daily-sub">${d.streak > 0 ? 'Серия: ' + d.streak + ' дн. — не пропускай, бонус растёт' : 'Заходи каждый день — бонус растёт'}</div>
      <div class="daily-dots">${dots}</div></div>
      <button class="btn btn-primary" style="height:38px;font-size:13px;flex:0 0 auto;width:auto;padding:0 16px" onclick="claimDaily()">Забрать</button>`;
  } else {
    box.innerHTML = `<div><div class="daily-title">✅ Бонус получен</div>
      <div class="daily-sub">Серия: ${d.streak} дн. Завтра +${d.amount} 🪙</div><div class="daily-dots">${dots}</div></div>`;
  }
}
async function claimDaily() {
  if (gameBusy) return;
  gameBusy = true;
  try { const r = await gameApi('daily'); showToast('+' + r.amount + ' 🪙 · серия ' + r.streak + ' дн.'); }
  catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; renderGame(); }
}
async function toggleStarsPublic() {
  if (gameBusy) return;
  gameBusy = true;
  try { await gameApi('toggle_stars_public'); } catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; renderGame(); }
}

/* ═══ Открытие карточки + анимация раскрытия (из макета) ═══ */
let revealed = null, revealQueue = [], revealTotal = 1, revealTimers = [];

function revealItems(items) {   // items: [{card, isNew}] — от слабой к сильной, финал всегда лучший
  items = items.slice().sort((a, b) => RARITY_ORDER.indexOf(a.card.rarity) - RARITY_ORDER.indexOf(b.card.rarity));
  revealQueue = items.slice(1); revealTotal = items.length;
  showCardOverlay(items[0].card, items[0].isNew);
}
function showCardOverlay(card, isNew) {
  const rc = RARITY_COLORS[card.rarity];
  const ov = $id('card-overlay'), st = $id('rv-stage');
  if (!ov || !st) return;
  revealTimers.forEach(clearTimeout); revealTimers = [];
  revealed = { card, isNew, done: false };
  const cn = $id('rv-counter');
  if (cn) cn.textContent = revealTotal > 1 ? (revealTotal - revealQueue.length) + ' / ' + revealTotal : '';
  st.className = 'rv-stage rv-' + card.rarity;
  st.style.setProperty('--rv', RARITY_GLOW[card.rarity] || '#a1a1aa');
  $id('ov-rarity').textContent = rc.label + (isNew ? ' · новая' : ' · дубликат');
  $id('ov-img').style.backgroundImage = card.bg;
  $id('ov-icon').innerHTML = card.icon;
  $id('ov-name').textContent = card.name;
  $id('ov-desc').textContent = card.desc;
  const keep = $id('rv-keep'); if (keep) keep.textContent = revealQueue.length ? 'Дальше' : 'Забрать';
  ov.classList.add('active');
  document.body.style.overflow = 'hidden';
  st.classList.remove('rv-in', 'rv-flip', 'rv-done');
  void st.offsetWidth;
  st.classList.add('rv-in');
  revealTimers.push(setTimeout(() => st.classList.add('rv-flip'), 1300));
  revealTimers.push(setTimeout(() => { st.classList.add('rv-done'); revealed.done = true; }, 3000));
}
function finishReveal() {
  revealTimers.forEach(clearTimeout); revealTimers = [];
  $id('card-overlay')?.classList.remove('active');
  $id('rv-stage')?.classList.remove('rv-in', 'rv-flip', 'rv-done');
  document.body.style.overflow = '';
  revealed = null;
}
function keepCard() {
  if (!revealed || !revealed.done) return;
  const next = revealQueue.shift();
  if (next) {
    $id('rv-stage').classList.remove('rv-in', 'rv-flip', 'rv-done');
    revealed = null;
    setTimeout(() => showCardOverlay(next.card, next.isNew), 700);
    return;
  }
  revealTotal = 1;
  finishReveal();
  renderGame();
}
function closeOverlay(e) {   // клик по фону = «забрать» (только когда анимация закончилась)
  if (e && e.target !== $id('card-overlay')) return;
  if (revealed && revealed.done) keepCard();
}
$id('card-flip')?.addEventListener('click', openCard);

async function openCard() {
  if (gameBusy || revealed) return;
  const flip = $id('card-flip');
  if (GAME.stars < openCost()) {
    showToast('Недостаточно монет. Нужно ' + openCost() + ' 🪙 — забирай ежедневный бонус, их дают за вопросы, идеи и ЧБД', 'error');
    if (flip) { flip.classList.add('shake'); setTimeout(() => flip.classList.remove('shake'), 400); }
    return;
  }
  gameBusy = true;
  try {
    const r = await gameApi('open');
    const card = cardById(r.cards[0]), isNew = r.new[0];
    const finish = () => { revealItems([{ card, isNew }]); renderGame(); checkRewardToast(r); };
    if (flip) {
      flip.style.transition = 'transform .1s';
      flip.style.transform = 'scale(.92) rotateZ(-3deg)';
      setTimeout(() => { flip.style.transform = 'scale(1.06) rotateZ(3deg)';
        setTimeout(() => { flip.style.transform = ''; finish(); }, 100); }, 100);
    } else finish();
  } catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; }
}

/* ═══ Покупка пака за звёзды Telegram ═══ */
let invoiceOpen = false;
// type: ключ пака | 'starter' | 'donor' | 'gift:<ключ пака>'
async function buyPack(type) {
  if (gameBusy || invoiceOpen) return;
  const t = window.Telegram?.WebApp;
  if (!t?.openInvoice) { showToast('Открой приложение внутри Telegram, чтобы оплатить звёздами', 'error'); return; }
  let r;
  gameBusy = true;
  try { r = await gameApi('pack_invoice', { pack: type }); }
  catch (e) { showToast(e.message, 'error'); return; }
  finally { gameBusy = false; }   // busy только на время запроса: зависшее окно оплаты не блокирует игру
  const prevUntil = GAME.donor?.until || 0, prevGifts = (GAME.gifts || []).length;
  invoiceOpen = true;
  const unlock = setTimeout(() => { invoiceOpen = false; }, 120000);
  try {
    t.openInvoice(r.url, status => {
      clearTimeout(unlock); invoiceOpen = false;
      if (status === 'paid') afterPayment(type, prevUntil, prevGifts);
      else if (status === 'failed') showToast('Оплата не прошла. Попробуй ещё раз', 'error');
    });
  } catch (e) { clearTimeout(unlock); invoiceOpen = false; showToast('Не удалось открыть окно оплаты', 'error'); }
}
function afterPayment(type, prevUntil, prevGifts) {
  if (type === 'donor') {
    showToast('Оплата прошла! Активируем статус…');
    waitState(() => (GAME.donor?.until || 0) > prevUntil, '💎 Ты теперь донатер! Бонусы уже работают');
  } else if (type.startsWith('gift:')) {
    showToast('Оплата прошла! Готовим подарок…');
    waitState(() => (GAME.gifts || []).length > prevGifts, '🎁 Подарок готов — отправь ссылку другу',
      () => $id('gift-list')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  } else {
    showToast('Оплата прошла! Открываем пак…');
    claimPacks(0);
  }
}
// бот зачисляет платёж за секунду-две: опрашиваем состояние, пока не появится результат
async function waitState(cond, doneMsg, after) {
  for (let i = 0; i < 10; i++) {
    try { await gameApi('state'); renderGame(); if (cond()) { showToast(doneMsg); if (after) after(); return; } }
    catch (e) { console.error(e); }
    await new Promise(r => setTimeout(r, 1500));
  }
  showToast('Оплата прошла. Если результат не появился — обнови приложение через минуту 🙏');
}
function buyGift() { const sel = $id('gift-select'); if (sel && sel.value) buyPack('gift:' + sel.value); }

/* ═══ Магазин: стартовый набор, донатер, подарки ═══ */
function fmtShortDate(ts) { return new Date(ts * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }); }
function renderOffers() {
  const st = GAME.starter;
  // карточка донатера показывается всегда; если сервер почему-то не прислал данные — берём запасные
  const dn = GAME.donor || { stars: 300, active: false, until: 0, days: 30, daily_mult: 2, pvp_limit: 8, coin_cap: 80, base_pvp_limit: 5, base_coin_cap: 40 };
  const sc = $id('starter-card');
  if (sc) {
    sc.style.display = st && st.available ? 'block' : 'none';
    if (st) {
      $id('starter-price').textContent = st.stars;
      $id('starter-old').textContent = st.value > st.stars ? st.value : '';
      $id('starter-save').textContent = '';
      $id('starter-desc').textContent = st.cards + ' карточек (1 Epic, 5 Rare и 4 Uncommon или Rare) и ' + st.coins + ' 🪙 в подарок. Покупается один раз.' +
        (st.save_pct > 0 ? ' Экономия ' + st.save_pct + '%' : '');
    }
  }
  const dc = $id('donor-card');
  if (dc) {
    dc.style.display = 'block';
    $id('donor-price').textContent = dn.stars;
    $id('donor-perks').innerHTML = [
      'Ежедневный бонус монет ×' + dn.daily_mult,
      dn.pvp_limit + ' дуэлей с ареной в сутки вместо ' + dn.base_pvp_limit,
      'До ' + dn.coin_cap + ' 🪙 в сутки за действия вместо ' + dn.base_coin_cap,
      'Значок 💎 рядом с ником в топе и конкурсе',
    ].map(x => '<li>' + x + '</li>').join('');
    const days = dn.active ? Math.max(1, Math.ceil((dn.until * 1000 - Date.now()) / 86400000)) : 0;
    $id('donor-status').textContent = dn.active ? '💎 Статус активен до ' + fmtShortDate(dn.until) + ' (ещё ' + days + ' дн.)' : 'Действует ' + dn.days + ' дней';
    $id('donor-buy-label').textContent = dn.active ? 'Продлить на ' + dn.days + ' дней' : 'Стать донатером';
  }
  const sel = $id('gift-select');
  if (sel && Object.keys(GAME.packs || {}).length) {
    const cur = sel.value;
    const items = (GAME.giftItems && GAME.giftItems.length) ? GAME.giftItems
      : Object.entries(GAME.packs).map(([k, p]) => ({ key: k, title: p.title, stars: (GAME.giftPrices && GAME.giftPrices[k]) || p.stars }));
    sel.innerHTML = items.map(x => `<option value="${esc(x.key)}">${esc(x.title)} — ${x.stars} ⭐</option>`).join('');
    if (cur && items.some(x => x.key === cur)) sel.value = cur;
  }
  const gl = $id('gift-list');
  if (gl) gl.innerHTML = (GAME.gifts || []).map(x => `<div class="gift-item"><div>🎁 ${esc(x.title)}<small>Ждёт друга · если не заберёт, через ${x.self_claim_days} дн. откроешь сам</small></div>
    <div class="gift-actions"><button onclick="shareGift('${esc(x.id)}')">Отправить</button><button class="ghost" onclick="copyGift('${esc(x.id)}')">Ссылка</button></div></div>`).join('');
}
function giftLink(id) { return GAME.botUsername ? 'https://t.me/' + GAME.botUsername + '?start=gift_' + id : ''; }
function copyGift(id) {
  const link = giftLink(id); if (!link) { showToast('Не удалось собрать ссылку, обнови приложение', 'error'); return; }
  const done = () => showToast('Ссылка скопирована! Отправь другу.');
  const fallback = () => {
    const ta = document.createElement('textarea'); ta.value = link; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { showToast('Скопируй ссылку вручную: ' + link, 'error'); }
    document.body.removeChild(ta);
  };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(link).then(done).catch(fallback); else fallback();
}
function shareGift(id) {
  const link = giftLink(id); if (!link) { showToast('Не удалось собрать ссылку, обнови приложение', 'error'); return; }
  const t = window.Telegram?.WebApp;
  const url = 'https://t.me/share/url?url=' + encodeURIComponent(link) + '&text=' + encodeURIComponent('🎁 Дарю тебе подарок в карточной игре! Забирай 👇');
  if (t?.openTelegramLink) t.openTelegramLink(url); else copyGift(id);
}
// карточки зачисляются, когда бот получит подтверждение платежа — это секунда-две
async function claimPacks(tries, silent) {
  try {
    const r = await gameApi('claim');
    if (r.packs && r.packs.length) {
      const items = [];
      r.packs.forEach(p => p.cards.forEach((id, i) => { const c = cardById(id); if (c) items.push({ card: c, isNew: p.new[i] }); }));
      renderGame();
      goToTab('game', 'g-coll');
      if (items.length) revealItems(items);
      checkRewardToast(r);
      return;
    }
  } catch (e) { console.error(e); }
  if (silent) return;
  if (tries < 10) setTimeout(() => claimPacks(tries + 1, silent), 1500);
  else showToast('Оплата прошла. Карточки появятся в коллекции в течение минуты 🙏');
}

/* ═══ Коллекция, лайтбокс, карусель (из макета) ═══ */
let collView = 'pack';
document.addEventListener('click', e => {
  const btn = e.target.closest('.coll-view-btn'); if (!btn || btn.dataset.view === collView) return;
  collView = btn.dataset.view;
  document.querySelectorAll('.coll-view-btn').forEach(x => x.classList.toggle('active', x.dataset.view === collView));
  renderCollection();
});


function renderCollection() {
  const container = document.getElementById('coll-container');
  if (!container) return;
  const s = getState();
  const owned = [...new Set(s.collection)];
  container.innerHTML = '';
  container.dataset.view = collView;

  if (collView === 'pack') { renderPackView(container, owned); return; }

  // GALLERY GRID (для list и card — общий grid в стиле GalleryGridBlock)
  if (collView === 'list') {
    ALL_CARDS.forEach((card, idx) => {
      const has = owned.includes(card.id);
      const rc  = RARITY_COLORS[card.rarity];
      const row = document.createElement('div');
      row.className = 'coll-list-row' + (has ? '' : ' coll-locked');
      row.style.animationDelay = (idx * 0.04) + 's';
      if (has) {
        row.innerHTML =
          '<div class="coll-list-thumb" style="background-image:' + card.bg + '"></div>' +
          '<div class="coll-list-info"><div class="coll-list-name">' + card.name + (countOf(card.id) > 1 ? '<span class="count-inline">×' + countOf(card.id) + '</span>' : '') + '</div><div class="coll-list-sub">' + rc.label + '</div></div>' +
          '<div class="dest-card-rarity ' + rc.cls + '">' + rc.label + '</div>';
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => openGalleryLightbox(card));
      } else {
        row.innerHTML =
          '<div class="coll-list-thumb coll-thumb-locked"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>' +
          '<div class="coll-list-info"><div class="coll-list-name" style="color:var(--muted-fg)">???</div><div class="coll-list-sub">' + rc.label + '</div></div>' +
          '<div class="dest-card-rarity ' + rc.cls + '" style="opacity:.4">' + rc.label + '</div>';
      }
      container.appendChild(row);
    });
    return;
  }

  // CARD / GALLERY GRID
  const grid = document.createElement('div');
  grid.className = 'gallery-grid';
  container.appendChild(grid);

  ALL_CARDS.forEach((card, idx) => {
    const has = owned.includes(card.id);
    const rc  = RARITY_COLORS[card.rarity];
    const item = document.createElement('div');
    item.className = 'gallery-item' + (has ? '' : ' gallery-item-locked');
    item.style.animationDelay = (idx * 0.05) + 's';

    if (has) {
      item.innerHTML =
        (countOf(card.id) > 1 ? '<div class="count-badge">×' + countOf(card.id) + '</div>' : '') +
        '<div class="gallery-item-img" style="background-image:' + card.bg + '">' +
          '<div class="gallery-item-overlay">' +
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>' +
            '<div class="gallery-item-overlay-name">' + card.name + '</div>' +
            '<div class="dest-card-rarity ' + rc.cls + '">' + rc.label + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="gallery-item-footer">' +
          '<div class="gallery-item-name">' + card.icon + ' ' + card.name + '</div>' +
          '<div class="dest-card-rarity ' + rc.cls + '">' + rc.label + '</div>' +
        '</div>';
      item.addEventListener('click', () => openGalleryLightbox(card));
    } else {
      item.innerHTML =
        '<div class="gallery-item-img gallery-item-img-locked">' +
          '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>' +
        '</div>' +
        '<div class="gallery-item-footer">' +
          '<div class="gallery-item-name" style="color:var(--muted-fg)">???</div>' +
          '<div class="dest-card-rarity ' + rc.cls + '" style="opacity:.4">' + rc.label + '</div>' +
        '</div>';
    }
    grid.appendChild(item);
  });
}
/* ══════════════════════════════════════════
   GALLERY LIGHTBOX
══════════════════════════════════════════ */
let galleryLightboxCards = [];
let galleryLightboxIdx = 0;

function openGalleryLightbox(card) {
  const s = getState();
  const owned = [...new Set(s.collection)];
  galleryLightboxCards = ALL_CARDS.filter(c => owned.includes(c.id));
  galleryLightboxIdx = galleryLightboxCards.findIndex(c => c.id === card.id);
  renderLightbox();
  const lb = document.getElementById('gallery-lightbox');
  if (lb) lb.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function renderLightbox() {
  const card = galleryLightboxCards[galleryLightboxIdx];
  if (!card) return;
  const rc = RARITY_COLORS[card.rarity];
  const img = document.getElementById('lb-img');
  const name = document.getElementById('lb-name');
  const desc = document.getElementById('lb-desc');
  const rarity = document.getElementById('lb-rarity');
  if (img)    img.style.backgroundImage = card.bg;
  if (name)   name.textContent = card.name;
  if (desc)   desc.textContent = card.desc;
  if (rarity) { rarity.className = 'dest-card-rarity ' + rc.cls; rarity.textContent = rc.label; }
  document.getElementById('lb-prev').disabled = galleryLightboxIdx === 0;
  document.getElementById('lb-next').disabled = galleryLightboxIdx === galleryLightboxCards.length - 1;
}

function closeLightbox() {
  const lb = document.getElementById('gallery-lightbox');
  if (lb) lb.classList.remove('active');
  document.body.style.overflow = '';
}
function lbPrev() { if (galleryLightboxIdx > 0) { galleryLightboxIdx--; renderLightbox(); } }
function lbNext() { if (galleryLightboxIdx < galleryLightboxCards.length - 1) { galleryLightboxIdx++; renderLightbox(); } }

// Coverflow state
let coverflowIndex = 0;
let coverflowAutoplay = null;

function renderPackView(container, owned) {
  if (coverflowAutoplay) { clearInterval(coverflowAutoplay); coverflowAutoplay = null; }
  const cards = ALL_CARDS;
  const isOwned = c => owned.includes(c.id);
  const firstOwned = cards.findIndex(isOwned);
  coverflowIndex = firstOwned >= 0 ? firstOwned : 0;
  container.innerHTML = '';

  const head = document.createElement('div');
  head.className = 'cf-head';
  head.innerHTML = `<div class="cf-count"><b>${owned.length}</b> / ${cards.length}</div>
    <div class="cf-progress"><div class="cf-progress-fill" style="width:${Math.round(owned.length/cards.length*100)}%"></div></div>`;
  container.appendChild(head);

  const wrap = document.createElement('div');
  wrap.className = 'coverflow';
  wrap.id = 'coverflow';
  wrap.tabIndex = 0;

  cards.forEach((card, i) => {
    const rc = RARITY_COLORS[card.rarity];
    const own = isOwned(card);
    const slide = document.createElement('div');
    slide.className = 'coverflow-slide' + (own ? '' : ' cf-locked');
    slide.dataset.index = i;
    slide.style.setProperty('--tc', rc.tc);
    slide.innerHTML = own ? `
      <div class="coverflow-card">
        <div class="coverflow-card-bg" style="background-image:${card.bg}"></div>
        <div class="coverflow-card-overlay" style="background:linear-gradient(to top,${rc.grd},transparent 60%)"></div>
        <div class="coverflow-card-shine"></div>
        <div class="coverflow-card-content">
          <div class="dest-card-rarity ${rc.cls}">${rc.label}</div>
          <h3 class="coverflow-card-name">${card.icon} ${card.name}</h3>
          <p class="coverflow-card-desc">${card.desc}</p>
        </div>
      </div>` : `
      <div class="coverflow-card cf-locked-card">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <div class="cf-locked-name">???</div>
        <div class="dest-card-rarity ${rc.cls}">${rc.label}</div>
      </div>`;
    wrap.appendChild(slide);
  });

  const info = document.createElement('div');
  info.className = 'cf-info';
  info.id = 'cf-info';

  const controls = document.createElement('div');
  controls.className = 'coverflow-controls';
  controls.innerHTML = `
    <button class="coverflow-arrow" id="cf-prev" aria-label="Назад">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
    </button>
    <div class="coverflow-dots" id="cf-dots"></div>
    <button class="coverflow-arrow" id="cf-next" aria-label="Вперёд">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
    </button>`;

  container.appendChild(wrap);
  container.appendChild(info);
  container.appendChild(controls);

  const dotsEl = document.getElementById('cf-dots');
  cards.forEach((c, i) => {
    const dot = document.createElement('span');
    dot.className = 'coverflow-dot' + (isOwned(c) ? ' owned' : '');
    dot.dataset.index = i;
    dot.addEventListener('click', () => cfGo(i));
    dotsEl.appendChild(dot);
  });

  const max = cards.length - 1;
  const cfGo = i => { coverflowIndex = Math.max(0, Math.min(max, i)); updateCoverflow(); };
  document.getElementById('cf-prev').addEventListener('click', () => cfGo(coverflowIndex - 1));
  document.getElementById('cf-next').addEventListener('click', () => cfGo(coverflowIndex + 1));

  // Drag / swipe (мышь и палец)
  let sx = null, moved = false;
  wrap.addEventListener('pointerdown', e => { sx = e.clientX; moved = false; });
  if (window.__cfUp) window.removeEventListener('pointerup', window.__cfUp);   // не копим обработчики при перерисовке
  window.__cfUp = e => {
    if (sx === null) return;
    const dx = e.clientX - sx; sx = null;
    if (Math.abs(dx) > 40) { moved = true; cfGo(coverflowIndex + (dx < 0 ? 1 : -1)); }
  };
  window.addEventListener('pointerup', window.__cfUp);
  // Клик: боковая карточка -> в центр, центральная -> просмотр
  wrap.addEventListener('click', e => {
    if (moved) { moved = false; return; }
    const slide = e.target.closest('.coverflow-slide');
    if (!slide) return;
    const i = parseInt(slide.dataset.index);
    if (i !== coverflowIndex) { cfGo(i); return; }
    if (isOwned(cards[i])) openGalleryLightbox(cards[i]);
  });
  wrap.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight') cfGo(coverflowIndex + 1);
    if (e.key === 'ArrowLeft')  cfGo(coverflowIndex - 1);
    if (e.key === 'Enter' && isOwned(cards[coverflowIndex])) openGalleryLightbox(cards[coverflowIndex]);
  });

  updateCoverflow();
}

function updateCoverflow() {
  const slides = document.querySelectorAll('.coverflow-slide');
  const dots   = document.querySelectorAll('.coverflow-dot');
  if (!slides.length) return;
  const narrow = window.innerWidth < 480;
  const ROT = 38, SPACING = narrow ? 82 : 128, DEPTH = 110, SCALE_STEP = 0.13;

  slides.forEach((slide, i) => {
    const offset = i - coverflowIndex;
    const absOff = Math.abs(offset);
    const dir = offset > 0 ? 1 : -1;
    const rotateY = absOff === 0 ? 0 : -dir * ROT;
    const translateX = offset * SPACING;
    const translateZ = -absOff * DEPTH;
    const scale = Math.max(1 - absOff * SCALE_STEP, 0.4);
    slide.style.transform = `translateX(${translateX}px) translateZ(${translateZ}px) rotateY(${rotateY}deg) scale(${scale})`;
    slide.style.opacity = absOff > 3 ? 0 : 1;
    slide.style.pointerEvents = absOff > 3 ? 'none' : 'auto';
    slide.style.filter = absOff === 0 ? 'none' : `brightness(${Math.max(0.35, 1 - absOff * 0.22)})`;
    slide.style.zIndex = slides.length - absOff;
    slide.classList.toggle('coverflow-active', absOff === 0);
  });
  dots.forEach((d, i) => d.classList.toggle('active', i === coverflowIndex));

  const card = ALL_CARDS[coverflowIndex];
  const own = [...new Set(getState().collection)].includes(card.id);
  const info = document.getElementById('cf-info');
  if (info) info.innerHTML = own
    ? `<span class="cf-info-name">${card.icon} ${card.name}</span><span class="cf-info-hint">нажми на карточку, чтобы открыть</span>`
    : `<span class="cf-info-name">Не открыта</span><span class="cf-info-hint">выбей её во вкладке «Открыть»</span>`;
  const prev = document.getElementById('cf-prev'), next = document.getElementById('cf-next');
  if (prev) prev.disabled = coverflowIndex === 0;
  if (next) next.disabled = coverflowIndex === ALL_CARDS.length - 1;
}

/* ═══ PvP ═══ */
function myProfile() {
  const u = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (u) return { name: u.username ? '@' + u.username : ([u.first_name, u.last_name].filter(Boolean).join(' ') || ('id' + u.id)),
                  photo: u.photo_url || null, ini: (u.username || u.first_name || 'U')[0].toUpperCase() };
  return { name: 'Гость', photo: null, ini: 'Г' };
}
function avatarHtml(p, cls) {
  const ini = (p.ini || (p.name || '?').replace('@','')[0] || '?').toUpperCase();
  let h = 0; for (const ch of String(p.name)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  if (p.photo) return `<div class="bt-ava ${cls||''}"><img src="${esc(p.photo)}" alt="" onerror="this.remove()"><span>${esc(ini)}</span></div>`;
  if (p.emoji) return `<div class="bt-ava ${cls||''}" style="background:linear-gradient(135deg,#27272a,#09090b)"><span style="font-size:22px">${p.emoji}</span></div>`;
  return `<div class="bt-ava ${cls||''}" style="background:linear-gradient(135deg,hsl(${h} 70% 45%),hsl(${(h+50)%360} 70% 30%))"><span>${esc(ini)}</span></div>`;
}
const ARENA = { name: 'Арена', emoji: '🤖' };
let pvpSelected = null, friendSelected = null, challengeLink = '', pvpSearching = false;

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-pvp]');
  if (!btn) return;
  const mode = btn.dataset.pvp;
  document.querySelectorAll('[data-pvp]').forEach(b => b.classList.toggle('active', b.dataset.pvp === mode));
  $id('pvp-random-panel').style.display = mode === 'random' ? 'block' : 'none';
  $id('pvp-friend-panel').style.display = mode === 'friend' ? 'block' : 'none';
  if (mode === 'friend') renderFriendCards();
});

function cardPickList(listId, onPick) {
  const list = $id(listId); if (!list) return null;
  const owned = [...new Set(GAME.collection)].map(cardById).filter(Boolean);
  if (!owned.length) { list.innerHTML = '<div style="color:var(--muted-fg);font-size:13px;text-align:center;padding:20px 0">Нет карточек. Открой во вкладке «Открыть».</div>'; return false; }
  list.innerHTML = '';
  owned.forEach(card => {
    const rc = RARITY_COLORS[card.rarity], n = countOf(card.id);
    const btn = document.createElement('button');
    btn.className = 'pvp-card-btn';
    btn.innerHTML = `<div class="pvp-card-thumb" style="background-image:${card.bg}"></div>
      <span class="pvp-card-info"><span class="pvp-card-name">${esc(card.name)}${n > 1 ? '<span class="count-inline">×' + n + '</span>' : ''}</span>
      <span class="pvp-card-rarity ${rc.cls}">${rc.label}</span></span><span class="pvp-check"></span>`;
    btn.addEventListener('click', () => { list.querySelectorAll('.pvp-card-btn').forEach(b => b.classList.remove('selected')); btn.classList.add('selected'); onPick(card); });
    list.appendChild(btn);
  });
  return true;
}
function renderPvPCards() {
  if (pvpSearching) return;
  pvpSelected = null;
  const sb = $id('pvp-start-btn'); if (sb) sb.disabled = true;
  const c = $id('pvp-stake-count'); if (c) c.textContent = '—';
  cardPickList('pvp-card-select', card => {
    pvpSelected = card.id; if (sb) sb.disabled = false;
    if (c) c.textContent = card.name + ' · ' + RARITY_COLORS[card.rarity].label;
  });
}
function renderFriendCards() {
  friendSelected = null;
  const cb = $id('pvp-challenge-btn'); if (cb) cb.disabled = true;
  cardPickList('pvp-friend-card-select', card => { friendSelected = card.id; if (cb) cb.disabled = false; });
}
function pvpShow(sel, search) {
  const a = $id('pvp-select-card'), b = $id('pvp-search-card');
  if (a) a.style.display = sel ? '' : 'none';
  if (b) b.style.display = search ? '' : 'none';
}
const fmtTime = ms => { const s = Math.floor(ms/1000); return Math.floor(s/60) + ':' + String(s%60).padStart(2,'0'); };

/* Соперник — «Арена» (бот): шансы 50/50 при той же редкости. Результат считает сервер. */
async function startPvP() {
  if (!pvpSelected || pvpSearching || gameBusy) return;
  const myCard = cardById(pvpSelected);
  pvpSearching = true; gameBusy = true;
  $id('pvp-result-card').style.display = 'none';
  $id('pvs-state').className = 'pvs-state searching';
  $id('pvs-title').textContent = 'Выходим на арену';
  $id('pvs-sub').textContent = 'Арена подбирает карточку той же редкости…';
  $id('pvs-scan').textContent = ''; $id('pvs-found').innerHTML = '';
  const me = myProfile();
  $id('pvs-my').innerHTML = avatarHtml(me) + `<div><div class="pvs-my-name">${esc(me.name)}</div><div class="pvs-my-rar">${esc(myCard.name)} · ${RARITY_COLORS[myCard.rarity].label}</div></div>`;
  $id('pvs-cancel').style.display = 'none';
  pvpShow(false, true);
  $id('pvp-search-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  const t0 = Date.now(), timer = setInterval(() => { $id('pvs-timer').textContent = fmtTime(Date.now() - t0); }, 250);
  let r, err = null;
  try { [r] = await Promise.all([gameApi('pvp', { card: pvpSelected }), sleep(2200)]); }
  catch (e) { err = e; }
  clearInterval(timer);
  gameBusy = false;
  if (err) { pvpSearching = false; showToast(err.message, 'error'); pvpShow(true, false); return; }
  $id('pvs-state').className = 'pvs-state found';
  $id('pvs-title').textContent = 'Соперник найден';
  $id('pvs-sub').textContent = 'Готовим дуэль…';
  $id('pvs-found').innerHTML = avatarHtml(ARENA) + `<div><div class="pvs-my-name">Арена</div><div class="pvs-my-rar">ставка скрыта 🔒</div></div>`;
  await sleep(1600);
  pvpSearching = false; pvpSelected = null;
  pvpShow(false, false);
  await showBattle(r, ARENA, `Ты выиграл <strong>${esc(cardById(r.opp).name)}</strong>!`, `Карточка <strong>${esc(cardById(r.my).name)}</strong> потеряна. Шансы были 50/50.`);
  checkRewardToast(r);
}
function cancelSearch() { pvpShow(true, false); }

function btCardHtml(c) {
  return `<div class="bt-card" data-rar="${c.rarity}" style="--rv:${RARITY_GLOW[c.rarity]}">
    <div class="bt-face bt-cb"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,.5)" stroke-width="1.4" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>
    <div class="bt-face bt-cf" style="background-image:${c.bg}"><div class="bt-cshade"></div><div class="bt-cname">${esc(c.name)}</div><div class="bt-cpow">${RARITY_COLORS[c.rarity].label}</div></div>
  </div>`;
}
/* Анимация дуэли из макета; исход (win) приходит от сервера */
async function showBattle(r, oppProfile, winText, loseText) {
  const my = cardById(r.my), opp = cardById(r.opp), me = myProfile();
  const outcome = r.win ? 'win' : 'loss';
  const side = (p, c, id, label) => `<div class="bt-side" id="${id}">${avatarHtml(p)}<div class="bt-name">${esc(p.name)}</div>
      <div class="bt-label">${label}</div><div class="bt-cards">${btCardHtml(c)}</div>
      <div class="bt-power"><span>редкость</span><b style="font-size:18px">${RARITY_COLORS[c.rarity].label}</b></div></div>`;
  const card = $id('pvp-result-card'), inner = $id('pvp-result-inner');
  const tab = $id('tab-g-pvp'); if (card.parentElement !== tab) tab.appendChild(card);
  const lab = card.querySelector('.card-label'); if (lab) lab.textContent = 'Дуэль';
  inner.innerHTML = `<div class="bt" id="bt">${side(me, my, 'bt-a', 'твоя ставка')}<div class="bt-mid"><div class="bt-vs">VS</div></div>${side(oppProfile, opp, 'bt-b', 'ставка')}</div>
    <div class="bt-banner" id="bt-banner"></div><p class="bt-note" id="bt-note"></p>`;
  card.style.display = 'block';
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  const bt = $id('bt');
  await sleep(1400);
  document.querySelector('#bt-a .bt-card').classList.add('flip'); await sleep(1100);
  document.querySelector('#bt-b .bt-card').classList.add('flip'); await sleep(1300);
  bt.classList.add('clash'); await sleep(1100);
  bt.classList.remove('clash'); bt.classList.add('done', 'res-' + outcome);
  const banner = $id('bt-banner');
  banner.className = 'bt-banner show ' + outcome;
  banner.textContent = r.win ? 'ПОБЕДА' : 'ПОРАЖЕНИЕ';
  $id('bt-note').innerHTML = r.win ? winText : loseText;
  const again = document.createElement('button');
  again.className = 'btn btn-secondary bt-again'; again.textContent = 'Сыграть ещё';
  again.onclick = () => { card.style.display = 'none'; renderPvPCards(); pvpShow(true, false); $id('pvp-select-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };
  inner.appendChild(again);
  requestAnimationFrame(() => again.classList.add('show'));
  showToast(r.win ? 'Победа!' : 'Поражение. Карточка потеряна.', r.win ? 'success' : 'error');
  renderGame();
}

/* ── Вызов друга ── */
async function createChallenge() {
  if (!friendSelected || gameBusy) return;
  gameBusy = true;
  try {
    const r = await gameApi('challenge_create', { card: friendSelected });
    challengeLink = r.link;
    $id('pvp-link-text').textContent = challengeLink;
    const lc = $id('pvp-link-card'); lc.style.display = 'block'; lc.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    friendSelected = null;
    renderGame(); renderPendingChallenge(); copyChallenge();
  } catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; }
}
function copyChallenge() {
  if (!challengeLink) return;
  const done = () => showToast('Ссылка скопирована! Отправь другу.');
  const fallback = () => {
    const ta = document.createElement('textarea'); ta.value = challengeLink; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { showToast('Скопируй ссылку вручную', 'error'); }
    document.body.removeChild(ta);
  };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(challengeLink).then(done).catch(fallback); else fallback();
}
function shareChallenge() {
  if (!challengeLink) return;
  const t = window.Telegram?.WebApp;
  const url = 'https://t.me/share/url?url=' + encodeURIComponent(challengeLink) + '&text=' + encodeURIComponent('⚔️ Вызываю тебя на дуэль карточек! Принимай вызов 👇');
  if (t?.openTelegramLink) t.openTelegramLink(url); else copyChallenge();
}
function renderPendingChallenge() {
  const panel = $id('pvp-friend-panel'); if (!panel) return;
  let box = $id('challenge-pending');
  if (!box) { box = document.createElement('div'); box.id = 'challenge-pending'; box.className = 'card'; panel.insertBefore(box, panel.firstChild); }
  if (GAME.challenge) {
    const c = cardById(GAME.challenge.card);
    box.style.display = 'block';
    box.innerHTML = `<div class="rv-challenge">⏳ У тебя есть активный вызов. Карточка <strong>${c ? esc(c.name) : ''}</strong> заморожена до ответа друга (максимум 24 часа, потом вернётся к тебе).</div>`;
  } else box.style.display = 'none';
}
/* Принять вызов друга (ссылка t.me/бот?start=pvp_ID открывает приложение с ?challenge=ID) */
async function handleChallengeLink() {
  const cid = new URLSearchParams(location.search).get('challenge');
  if (!cid || window.__challengeShown) return;
  window.__challengeShown = true;
  goToTab('game', 'g-pvp');
  const tabEl = $id('tab-g-pvp');
  let box = $id('accept-card');
  if (!box) { box = document.createElement('div'); box.id = 'accept-card'; box.className = 'card'; tabEl.insertBefore(box, tabEl.firstChild); }
  try {
    const info = await gameApi('challenge_info', { id: cid });
    const rl = RARITY_COLORS[info.rarity].label;
    const owned = [...new Set(GAME.collection)].filter(id => cardById(id).rarity === info.rarity);
    if (!owned.length) {
      box.innerHTML = `<div class="card-label">⚔️ ${esc(info.owner)} вызывает тебя на дуэль</div><p class="rv-challenge">Он поставил карточку редкости <strong>${rl}</strong>, а у тебя такой нет. Дуэль честная — ставить можно только карточку той же редкости. Открой больше карточек и возвращайся по ссылке.</p>`;
      return;
    }
    box.innerHTML = `<div class="card-label">⚔️ ${esc(info.owner)} вызывает тебя на дуэль</div>
      <p class="rv-challenge">Его карточка скрыта до результата, но известна её редкость: <strong>${rl}</strong>. Поставь свою такой же редкости. Победитель забирает обе.</p>
      <select id="accept-select" class="admin-input">${owned.map(id => { const c = cardById(id); return `<option value="${id}">${esc(c.name)} (${RARITY_COLORS[c.rarity].label})${countOf(id) > 1 ? ' ×' + countOf(id) : ''}</option>`; }).join('')}</select>
      <button class="btn btn-primary" style="margin-top:10px" onclick="acceptChallenge('${esc(cid)}')">Принять вызов</button>`;
  } catch (e) { box.innerHTML = `<div class="card-label">⚔️ Вызов</div><p class="rv-challenge">${esc(e.message)}</p>`; }
}
async function acceptChallenge(cid) {
  if (gameBusy) return;
  const sel = $id('accept-select'); if (!sel) return;
  gameBusy = true;
  try {
    const r = await gameApi('challenge_accept', { id: cid, card: sel.value });
    $id('accept-card')?.remove();
    history.replaceState(null, '', location.pathname);
    window.__challengeShown = false;
    $id('pvp-random-panel').style.display = 'block'; $id('pvp-friend-panel').style.display = 'none';
    document.querySelectorAll('[data-pvp]').forEach(b => b.classList.toggle('active', b.dataset.pvp === 'random'));
    pvpShow(false, false);
    gameBusy = false;
    await showBattle(r, { name: 'Друг', ini: 'Д' },
      `Ты выиграл обе карточки: <strong>${esc(cardById(r.opp).name)}</strong>!`, `Твоя карточка <strong>${esc(cardById(r.my).name)}</strong> ушла сопернику.`);
    checkRewardToast(r);
  } catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; renderGame(); }
}
document.addEventListener('DOMContentLoaded', () => { if (new URLSearchParams(location.search).get('challenge')) goTo('game'); });

/* ═══ Обмен дубликатов на редкость выше ═══ */
function renderTrade() {
  const box = $id('trade-list'); if (!box) return;
  box.innerHTML = (GAME.trade || []).map(t => {
    const from = RARITY_COLORS[t.rarity], to = RARITY_COLORS[t.to];
    const pct = Math.min(100, Math.round(t.have / t.need * 100));
    return `<div class="trade-row${t.can ? ' trade-can' : ''}">
      <div class="trade-top"><div><strong>${t.need} × ${from.label}</strong> → <strong>${to.label}</strong></div><div class="trade-chance">${t.chance}%</div></div>
      <div class="trade-sub">Лишних копий: ${t.have} из ${t.need}. Не повезло — вернётся 1 карточка ${from.label}.</div>
      <div class="progress-bar" style="margin:8px 0 10px"><div class="progress-fill" style="width:${pct}%"></div></div>
      <button class="btn ${t.can ? 'btn-primary' : 'btn-secondary'}" style="height:38px;font-size:13px" ${t.can ? '' : 'disabled'} onclick="doTrade('${t.rarity}')">Обменять</button></div>`;
  }).join('');
}
async function doTrade(rarity) {
  if (gameBusy) return;
  gameBusy = true;
  try {
    const r = await gameApi('trade', { rarity });
    const card = cardById(r.got);
    revealItems([{ card, isNew: r.new }]);
    showToast(r.success ? '🎉 Обмен удался: ' + card.name : 'Не повезло: вернулась ' + card.name, r.success ? 'success' : 'error');
    checkRewardToast(r);
  } catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; renderGame(); }
}

/* ═══ Промокод ═══ */
async function redeemPromo() {
  if (gameBusy) return;
  const inp = $id('promo-input'), code = (inp?.value || '').trim();
  if (!code) { showToast('Введи промокод', 'error'); return; }
  gameBusy = true;
  try {
    const r = await gameApi('promo', { code });
    const parts = [];
    if (r.coins) parts.push('+' + r.coins + ' 🪙');
    if (r.cards && r.cards.length) parts.push(r.cards.map(id => cardById(id).name).join(', '));
    showToast('Промокод активирован: ' + parts.join(' и '));
    if (inp) inp.value = '';
    if (r.cards && r.cards.length) revealItems(r.cards.map((id, i) => ({ card: cardById(id), isNew: r.new[i] })));
    checkRewardToast(r);
  } catch (e) { showToast(e.message, 'error'); }
  finally { gameBusy = false; renderGame(); }
}

/* ═══ Конкурс ═══ */
function renderContest() {
  const box = $id('contest-card'), c = GAME.contest;
  if (!box || !c) return;
  const total = ALL_CARDS.length, owned = new Set(GAME.collection).size, pct = total ? Math.round(owned / total * 100) : 0;
  const places = (c.places || []).map(p => `<li>${esc(p)}</li>`).join('');
  box.style.display = c.active ? 'block' : 'none';
  box.innerHTML = `<div class="card-label">🏆 ${esc(c.title)}</div>
    <div class="game-reward-title">Приз: ${esc(c.prize)}</div>
    <div class="game-reward-desc" style="margin:6px 0 10px">${esc(c.rules)}${c.ends ? ' Конкурс идёт до ' + esc(c.ends) + '.' : ''}</div>
    ${places ? `<ul class="contest-places">${places}</ul>` : ''}
    <div class="game-reward-desc" style="margin:10px 0">🎁 Всем, кто соберёт коллекцию: <strong>${esc(c.everyone_reward)}</strong>.</div>
    <div class="game-reward-prog-row"><span>Твой прогресс</span><span>${owned} / ${total}</span></div>
    <div class="progress-bar" style="margin-bottom:10px"><div class="progress-fill" style="width:${pct}%"></div></div>
    ${GAME.completed ? '<div class="contest-done">✅ Коллекция собрана! Ты в списке на награду.</div>' : ''}
    <div id="contest-board" style="margin-top:10px"></div>`;
  loadContestBoard();
}
let _contestLoadedAt = 0;
async function loadContestBoard() {
  if (Date.now() - _contestLoadedAt < 15000) return;
  _contestLoadedAt = Date.now();
  try {
    const r = await gameApi('contest');
    const b = r.board, el = $id('contest-board'); if (!el || !b) return;
    const rows = b.rows.map(x => `<div class="contest-row${x.me ? ' me' : ''}"><span>${x.place}. ${esc(x.name)}</span><span>${x.done ? '✅ собрал' : x.unique + ' / ' + b.total}</span></div>`).join('');
    const mine = b.me && !b.rows.some(x => x.me) ? `<div class="contest-row me"><span>${b.me.place}. Ты</span><span>${b.me.unique} / ${b.total}</span></div>` : '';
    el.innerHTML = `<div class="field-label">Таблица конкурса · собрали всё: ${b.finished}</div>${rows}${mine}`;
  } catch (e) { /* таблица — не критично */ }
}

/* ═══ Обмен карточек на награду от Ромы (заявка уходит админам в Telegram) ═══ */
const EXCH_FALLBACK = { values: { common:15, uncommon:20, rare:30, epic:60, legendary:120 }, rewards: [] };
let exchPick = {}, exchReward = null, exchBodyHTML = '';
const exchCfg = () => GAME.exchange || EXCH_FALLBACK;
const exchValueOf = () => Object.entries(exchPick).reduce((n, [id, k]) => { const c = cardById(id); return n + (c ? (exchCfg().values[c.rarity] || 0) * k : 0); }, 0);
const exchCount = () => Object.values(exchPick).reduce((n, k) => n + k, 0);

function openExchange() {
  exchPick = {}; exchReward = null;
  const body = $id('exch-body');
  if (body) { if (!exchBodyHTML) exchBodyHTML = body.innerHTML; else if (!$id('exch-cards')) body.innerHTML = exchBodyHTML; }
  renderExchange();
  $id('exch-modal').classList.add('active');
  document.body.style.overflow = 'hidden';
}
function closeExchange() { $id('exch-modal')?.classList.remove('active'); document.body.style.overflow = ''; }

function renderExchange() {
  const grid = $id('exch-cards'); if (!grid) return;
  const ids = ALL_CARDS.filter(c => countOf(c.id));
  grid.innerHTML = ids.length ? '' : '<div class="exch-empty">У тебя пока нет карточек. Открой их во вкладке «Открыть».</div>';
  ids.forEach(c => {
    const picked = exchPick[c.id] || 0, have = countOf(c.id);
    const el = document.createElement('button');
    el.className = 'exch-card' + (picked ? ' on' : '');
    el.style.setProperty('--rv', RARITY_GLOW[c.rarity]);
    el.innerHTML = `<span class="exch-card-img" style="background-image:${c.bg}"></span><span class="exch-card-name">${esc(c.name)}</span>
      <span class="exch-card-val">${exchCfg().values[c.rarity]}</span>
      ${have > 1 ? `<span class="exch-card-cnt">${picked}/${have}</span>` : (picked ? '<span class="exch-card-cnt">✓</span>' : '')}`;
    el.onclick = () => { exchPick[c.id] = picked >= have ? 0 : picked + 1; if (!exchPick[c.id]) delete exchPick[c.id]; renderExchange(); };
    grid.appendChild(el);
  });
  const val = exchValueOf();
  $id('exch-n').textContent = exchCount(); $id('exch-val').textContent = val;
  const box = $id('exch-rewards'); box.innerHTML = '';
  const rewards = exchCfg().rewards;
  if (exchReward && (rewards.find(r => r.id === exchReward)?.cost > val)) exchReward = null;
  rewards.forEach(r => {
    const ok = val >= r.cost;
    const el = document.createElement('button');
    el.className = 'exch-reward' + (exchReward === r.id ? ' on' : '') + (ok ? '' : ' lock');
    el.innerHTML = `<span class="exch-reward-main"><span class="exch-reward-name">${esc(r.name)}</span><span class="exch-reward-desc">${esc(r.desc)}</span></span>
      <span class="exch-reward-cost">${ok ? r.cost : '🔒 ' + r.cost}</span>`;
    el.onclick = () => { if (!ok) { showToast('Не хватает ' + (r.cost - val) + ' ценности — добавь карточек', 'error'); return; } exchReward = (exchReward === r.id ? null : r.id); renderExchange(); };
    box.appendChild(el);
  });
  $id('exch-go').disabled = !exchReward;
}
async function submitExchange() {
  const reward = exchCfg().rewards.find(r => r.id === exchReward);
  if (!reward || exchValueOf() < reward.cost || gameBusy) return;
  const btn = $id('exch-go'); btn.disabled = true; btn.textContent = 'Отправляем…';
  gameBusy = true;
  try {
    const r = await gameApi('exchange', { reward: reward.id, cards: exchPick });
    exchPick = {}; exchReward = null;
    $id('exch-body').innerHTML = `<div class="exch-done"><div class="exch-done-ic"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></div>
      <div class="exch-done-t">Заявка отправлена</div>
      <div class="exch-done-s">${esc(r.reward_name)} · отдано ${r.count} шт.<br>Рома свяжется с тобой в Telegram. Номер заявки <b>${esc(r.request.id)}</b>.</div>
      <button class="exch-go" onclick="closeExchange()">Готово</button></div>`;
  } catch (e) { showToast(e.message, 'error'); btn.textContent = 'Обменять'; renderExchange(); }
  finally { gameBusy = false; renderGame(); }
}

/* ═══ Шейдеры из макета (запускаются при первом открытии игры) ═══ */
function initNeuroNoise() {
  const canvas = document.getElementById('neuro-canvas');
  if (!canvas) return;
  const gl = canvas.getContext('webgl');
  if (!gl) return;

  const vert = 'attribute vec2 a;void main(){gl_Position=vec4(a,0,1);}';

  // Full Neuro Noise fragment shader with all Paper Shaders uniforms
  const frag = '#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\n' +
    'uniform vec3 u_colors[8];\nuniform vec4 u_scene,u_shape,u_surface,u_finish,u_transform,u_space,u_cursor;\n' +
    '#define u_resolution u_scene.xy\n#define u_time u_scene.z\n#define u_colorCount u_scene.w\n' +
    '#define u_scale u_shape.x\n#define u_intensity u_shape.y\n#define u_paramA u_shape.z\n#define u_warp u_shape.w\n' +
    '#define u_detail u_surface.x\n#define u_contrast u_surface.y\n#define u_brightness u_surface.z\n#define u_saturation u_surface.w\n' +
    '#define u_hue u_finish.x\n#define u_vignette u_finish.y\n#define u_blur u_finish.z\n#define u_grain u_finish.w\n' +
    '#define u_seed u_transform.x\n#define u_rotate u_transform.y\n#define u_drift u_transform.z\n' +
    '#define u_offset u_space.xy\n#define u_mouse u_space.zw\n' +
    '#define u_cursorPresence u_cursor.x\n#define u_cursorEffect u_cursor.y\n#define u_cursorStrength u_cursor.z\n#define u_cursorRadius u_cursor.w\n' +
    'float hash21(vec2 p){p=fract(p*vec2(234.34,435.345));p+=dot(p,p+34.23);return fract(p.x*p.y);}\n' +
    'float grainHash(vec2 p){vec3 p3=fract(vec3(p.xyx)*0.1031);p3+=dot(p3,p3.yzx+33.33);return fract((p3.x+p3.y)*p3.z);}\n' +
    'float noise(vec2 p){vec2 i=floor(p);vec2 f=fract(p);vec2 u=f*f*(3.0-2.0*f);return mix(mix(hash21(i),hash21(i+vec2(1,0)),u.x),mix(hash21(i+vec2(0,1)),hash21(i+vec2(1,1)),u.x),u.y);}\n' +
    'vec3 hueRotate(vec3 col,float a){mat3 toYIQ=mat3(0.299,0.596,0.211,0.587,-0.274,-0.523,0.114,-0.322,0.312);mat3 toRGB=mat3(1,1,1,0.956,-0.272,-1.106,0.621,-0.647,1.703);vec3 yiq=toYIQ*col;float ca=cos(a),sa=sin(a);yiq=vec3(yiq.x,yiq.y*ca-yiq.z*sa,yiq.y*sa+yiq.z*ca);return toRGB*yiq;}\n' +
    'vec3 palette(float x){float n=max(u_colorCount-1.0,1.0);float f=clamp(x,0.0,1.0)*n;vec3 col=u_colors[0];for(int i=0;i<7;i++){if(float(i)<n)col=mix(col,u_colors[i+1],smoothstep(0.0,1.0,clamp(f-float(i),0.0,1.0)));}return col;}\n' +
    'vec3 shade(vec2 uv,vec2 p,float t){vec2 q=p*(1.6+u_intensity*2.4);float field=0.0;float weight=0.55;for(int i=0;i<6;i++){float fi=float(i);q+=vec2(sin(q.y*(1.7+fi*0.09)+t*(0.35+fi*0.04)+u_seed),cos(q.x*(1.5+fi*0.11)-t*(0.28+fi*0.03)))*(0.22+u_intensity*0.14);float filaments=abs(sin(q.x+q.y+fi*0.72));field+=weight/(0.08+filaments);weight*=0.62;q=q.yx*vec2(-1.08,1.04);}float glow=1.0-exp(-field*(0.018+u_paramA*0.04));return palette(clamp(glow,0.0,1.0));}\n' +
    'void main(){vec2 uv=gl_FragCoord.xy/u_resolution.xy;vec2 screenUv=uv;vec2 p=(gl_FragCoord.xy-0.5*u_resolution.xy)/min(u_resolution.x,u_resolution.y);' +
    'float cursorMask=0.0;if(u_cursorPresence>0.001){vec2 cursor=(0.5*u_mouse*u_resolution.xy)/min(u_resolution.x,u_resolution.y);vec2 cursorDelta=p-cursor;float cursorDistance=length(cursorDelta);vec2 cursorDir=cursorDelta/max(cursorDistance,0.0001);cursorMask=u_cursorPresence*(1.0-smoothstep(0.0,u_cursorRadius,cursorDistance));}\n' +
    'uv=p*min(u_resolution.x,u_resolution.y)/u_resolution.xy+0.5;p*=u_scale;p+=u_offset;if(u_drift>0.0001)p+=u_drift*vec2(sin(u_time*0.31),cos(u_time*0.23));' +
    'vec3 col=shade(uv,p,u_time);' +
    'if(abs(u_contrast-1.0)>0.0001)col=(col-0.5)*u_contrast+0.5;' +
    'if(abs(u_saturation-1.0)>0.0001){float luma=dot(col,vec3(0.299,0.587,0.114));col=mix(vec3(luma),col,u_saturation);}' +
    'if(abs(u_hue)>0.0001)col=hueRotate(col,u_hue);' +
    'col+=u_brightness;' +
    'if(u_vignette>0.0001){float vd=length(screenUv-0.5)*1.41421356;col*=1.0-u_vignette*smoothstep(0.35,1.0,vd);}' +
    'if(u_cursorPresence>0.001&&u_cursorEffect>3.5)col+=(vec3(0.18)+col*0.12)*cursorMask*u_cursorStrength;' +
    'if(u_grain>0.0001)col+=(grainHash(gl_FragCoord.xy+vec2(u_seed*17.0,u_seed*31.0))-0.5)*u_grain;' +
    'gl_FragColor=vec4(clamp(col,0.0,1.0),1.0);}';

  function mkShader(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.warn('Neuro Noise compile error:', gl.getShaderInfoLog(s));
    return s;
  }
  const prog = gl.createProgram();
  gl.attachShader(prog, mkShader(gl.VERTEX_SHADER, vert));
  gl.attachShader(prog, mkShader(gl.FRAGMENT_SHADER, frag));
  gl.linkProgram(prog);

  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    console.warn('Neuro Noise shader error:', gl.getProgramInfoLog(prog));
    return;
  }
  gl.useProgram(prog);

  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  const aLoc = gl.getAttribLocation(prog, 'a');
  gl.enableVertexAttribArray(aLoc);
  gl.vertexAttribPointer(aLoc, 2, gl.FLOAT, false, 0, 0);

  const U = n => gl.getUniformLocation(prog, n);
  const uScene = U('u_scene'), uShape = U('u_shape'), uSurface = U('u_surface');
  const uFinish = U('u_finish'), uTransform = U('u_transform'), uSpace = U('u_space');
  const uCursor = U('u_cursor'), uColors = U('u_colors');

  // Colors: #03120E #0E7C5A #7CE577 #F4FFC7 + 4 padding
  gl.uniform3fv(uColors, [
    0.012,0.071,0.055,  0.055,0.486,0.353,
    0.486,0.898,0.467,  0.957,1.000,0.780,
    0,0,0, 0,0,0, 0,0,0, 0,0,0
  ]);
  gl.uniform4f(uShape,     1.26, 0.35, 0.28, 0.00);
  gl.uniform4f(uSurface,   1.82, 1.01, 0.06, 1.36);
  gl.uniform4f(uFinish,    5.34, 0.08, 0.005, 0.04);
  gl.uniform4f(uTransform, 242.0, 0.00, 0.12, 0.0);
  gl.uniform4f(uCursor,    0.44, 4.0, 0.44, 0.41);

  let mx = 0.5, my = 0.5, paused = false, start = null;
  document.addEventListener('visibilitychange', () => { paused = document.hidden; });
  canvas.closest('.game-hero-neuro')?.addEventListener('mousemove', e => {
    const r = canvas.getBoundingClientRect();
    mx = (e.clientX - r.left) / r.width * 2 - 1;
    my = -((e.clientY - r.top) / r.height * 2 - 1);
  });

  function resize() {
    const dpr = Math.min(devicePixelRatio, 2);
    const w = (canvas.clientWidth  * dpr) | 0;
    const h = (canvas.clientHeight * dpr) | 0;
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; gl.viewport(0, 0, w, h); }
  }

  function frame(ts) {
    requestAnimationFrame(frame);
    if (paused) return;
    if (!start) start = ts;
    const t = (ts - start) * 0.001 * 0.3;
    resize();
    gl.uniform4f(uScene,   canvas.width, canvas.height, t, 4.0);
    gl.uniform4f(uSpace,   0.04, -0.20, mx, my);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  requestAnimationFrame(frame);
}

function initPortal() {
  const iframe = document.getElementById('portal-iframe');
  if (!iframe) return;

  const src = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>*{margin:0;padding:0}body{background:#05060a;overflow:hidden}</style></head><body>
<div id="c" style="position:absolute;inset:0"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"><\/script>
<script>
const c=document.getElementById('c');
const s=new THREE.Scene(),cam=new THREE.OrthographicCamera(-1,1,1,-1,0.1,10);
cam.position.z=1;
const r=new THREE.WebGLRenderer({antialias:true,alpha:true});
r.setSize(window.innerWidth,window.innerHeight);
r.setPixelRatio(Math.min(devicePixelRatio,2));
c.appendChild(r.domElement);
const mat=new THREE.ShaderMaterial({
  vertexShader:'varying vec2 v;void main(){v=uv;gl_Position=vec4(position,1.0);}',
  fragmentShader:\`uniform float t;uniform vec2 res;varying vec2 v;
vec2 hash(vec2 p){p=vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3)));return -1.0+2.0*fract(sin(p)*43758.5453123);}
float noise(in vec2 p){const float K1=0.366025404,K2=0.211324865;vec2 i=floor(p+(p.x+p.y)*K1);vec2 a=p-i+(i.x+i.y)*K2;vec2 o=(a.x>a.y)?vec2(1,0):vec2(0,1);vec2 b=a-o+K2,cc=a-1.0+2.0*K2;vec3 h=max(0.5-vec3(dot(a,a),dot(b,b),dot(cc,cc)),0.0);vec3 n=h*h*h*h*vec3(dot(a,hash(i)),dot(b,hash(i+o)),dot(cc,hash(i+1.0)));return dot(n,vec3(70.0));}
float arc(vec2 p,vec2 cen,float rad,float w,float warp){p.y+=sin(p.x*2.0+t*0.3)*warp;p.x+=noise(p*1.5+t*0.1)*(warp*0.8);return abs(length(p-cen)-rad)-w;}
void main(){vec2 st=gl_FragCoord.xy/res;st.x*=res.x/res.y;vec2 cen=vec2(0.5,0.5);float d1=arc(st,cen,0.6,0.02,0.15),d2=arc(st,cen,0.65,0.06,0.2);float cg=exp(-d1*30.0),fg=exp(-d2*10.0),w=smoothstep(1.5,-0.5,length(st-cen))*0.15;vec3 col=vec3(0);col+=vec3(1)*cg;col+=vec3(0.12,0.08,0.8)*fg;col+=vec3(0.12,0.08,0.8)*w*(sin(t*0.5)*0.2+0.8);float a=clamp(cg+fg+w,0.0,1.0);col=vec3(1)-exp(-col*1.5);gl_FragColor=vec4(col,a*0.7);}\`,
  uniforms:{t:{value:0},res:{value:new THREE.Vector2(window.innerWidth,window.innerHeight)}},
  transparent:true,blending:THREE.AdditiveBlending
});
const mesh=new THREE.Mesh(new THREE.PlaneGeometry(2,2),mat);
s.add(mesh);
const clk=new THREE.Clock();
function anim(){requestAnimationFrame(anim);mat.uniforms.t.value=clk.getElapsedTime();r.render(s,cam);}
anim();
window.addEventListener('resize',()=>{r.setSize(window.innerWidth,window.innerHeight);mat.uniforms.res.value.set(window.innerWidth,window.innerHeight);});
<\/script></body></html>`;

  iframe.srcdoc = src;
}

/* ── Мягкий шейдер (aurora) для шапки магазина и блока пополнения ── */
function mountAurora(canvas, calm, pal) {
  if (!canvas) return;
  const gl = canvas.getContext('webgl');
  if (!gl) return;
  const vs = 'attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}';
  const fs = `precision mediump float;uniform vec2 r;uniform float t;uniform vec3 k1,k2,k3;
  float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
  float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*n(p);p=p*2.02+vec2(3.1,1.7);a*=.5;}return v;}
  void main(){vec2 uv=gl_FragCoord.xy/r;vec2 p=(uv-.5)*vec2(r.x/r.y,1.)*2.4;
   vec2 q=vec2(fbm(p+t*.08),fbm(p+vec2(5.2,1.3)-t*.06));
   float f=fbm(p+3.*q+vec2(t*.05,0.));
   vec3 c1=k1,c2=k2,c3=k3;
   vec3 col=mix(c1,c2,smoothstep(.25,.75,f));
   col=mix(col,c3,smoothstep(.62,.95,f)*.55*q.x);
   col*=.55+.6*smoothstep(1.2,.0,length(uv-vec2(.2,.5)));
   col+=(h(gl_FragCoord.xy+t)-.5)*.02;
   gl_FragColor=vec4(col,1.);}`;
  const mk = (ty, src) => { const s = gl.createShader(ty); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.warn('aurora shader', gl.getShaderInfoLog(s)); return s; };
  const p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
  gl.useProgram(p);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(p, 'a'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const uR = gl.getUniformLocation(p, 'r'), uT = gl.getUniformLocation(p, 't');
  const P = pal || { c1:[.06,.03,.16], c2:[.42,.16,.85], c3:[.98,.72,.2] };
  gl.uniform3fv(gl.getUniformLocation(p, 'k1'), P.c1); gl.uniform3fv(gl.getUniformLocation(p, 'k2'), P.c2); gl.uniform3fv(gl.getUniformLocation(p, 'k3'), P.c3);
  const speed = calm || 0.6;
  let t0 = null;
  (function frame(ts) {
    requestAnimationFrame(frame);
    if (document.hidden || canvas.offsetParent === null) return;
    if (t0 === null) t0 = ts;
    const dpr = Math.min(devicePixelRatio, 1.5), w = (canvas.clientWidth * dpr) | 0, hh = (canvas.clientHeight * dpr) | 0;
    if (canvas.width !== w || canvas.height !== hh) { canvas.width = w; canvas.height = hh; gl.viewport(0, 0, w, hh); }
    gl.uniform2f(uR, canvas.width, canvas.height); gl.uniform1f(uT, (ts - t0) * 0.001 * speed);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  })(0);
}
