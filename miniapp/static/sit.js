/* ═══════════════════════════════════════════════════════════
   Игра «Ситуации» — мини-апп. Вся логика на сервере (situations.py:
   api_state / api_action / api_media); здесь только отрисовка и опрос.
═══════════════════════════════════════════════════════════ */
'use strict';
(function () {
  const POLL_MS = 2500;
  let S = null;              // последнее состояние
  let pollT = null, tickT = null, busy = false, lastSig = '', endAt = 0, totalSec = 0;
  let vIdx = 0;              // какой ответ листается при голосовании
  let adminOpen = false;
  const MODES = { manual: 'Вручную', random: 'Случайная', suggest: 'Идеи игроков', vote: 'Голосование' };
  const root = () => $id('sit-root');
  const fmt = s => String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');

  async function call(action, payload, quiet) {
    if (!tg?.initData) { if (!quiet) showToast('Открой приложение через Telegram', 'error'); return null; }
    try {
      const res = await fetch('/api/sit/' + action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg.initData },
        body: JSON.stringify(payload || {}),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) { if (!quiet) showToast(errMsg(d.detail, 'Ошибка'), 'error'); return null; }
      if (d.state) apply(d.state);
      return d;
    } catch (e) { console.error(e); if (!quiet) showToast('Ошибка сети', 'error'); return null; }
  }
  async function act(action, payload, okMsg) {
    if (busy) return null;
    busy = true;
    try { const d = await call(action, payload); if (d) { if (d.info) showToast(d.info); else if (okMsg) showToast(okMsg); } return d; }
    finally { busy = false; }
  }
  window.sitA = (a, p, m) => act('a_' + a, p, m);
  window.sitP = (a, p, m) => act(a, p, m);

  function apply(st) {
    S = st;
    if (S.phase === 'work') {
      const left = S.work_left || 0;
      endAt = Date.now() + left * 1000;
      totalSec = Math.max(totalSec, left, (S.work_minutes || 0) * 60);
    }
    const sig = JSON.stringify(S, (k, v) => (k === 'work_left' ? undefined : v)) + '|' + vIdx + '|' + adminOpen;
    if (sig !== lastSig) { lastSig = sig; render(); }
  }

  /* ── жизненный цикл ── */
  window.sitOpen = function () {
    vIdx = 0; lastSig = '';
    call('state', {}, true);
    clearInterval(pollT); pollT = setInterval(() => { if (!document.hidden) call('state', {}, true); }, POLL_MS);
    clearInterval(tickT); tickT = setInterval(tick, 1000);
  };
  window.sitClose = function () { clearInterval(pollT); clearInterval(tickT); pollT = tickT = null; };
  window.sitPeek = async function () {           // метка LIVE на карточке в «Играх»
    const el = $id('hub-sit-live'); if (!el || !tg?.initData) return;
    try {
      const r = await fetch('/api/sit/state', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg.initData }, body: '{}' });
      const d = await r.json(); el.style.display = d.state && d.state.phase !== 'none' && d.state.phase !== 'finished' ? '' : 'none';
    } catch (e) { /* не критично */ }
  };
  function tick() {
    if (!S || S.phase !== 'work') return;
    const left = Math.max(0, Math.round((endAt - Date.now()) / 1000));
    document.querySelectorAll('[data-sit-timer]').forEach(el => { el.textContent = fmt(left); el.classList.toggle('low', left <= 60); });
    const bar = $id('sit-bar'); if (bar && totalSec) bar.style.width = Math.min(100, left / totalSec * 100) + '%';
    const pct = $id('sit-pct'); if (pct && totalSec) pct.textContent = 'Осталось ' + Math.round(left / totalSec * 100) + '% времени';
  }

  /* ── шапка ── */
  function head() {
    const on = S && S.phase !== 'none';
    const r = $id('sit-round');
    if (r) { r.style.display = on ? '' : 'none'; r.textContent = 'РАУНД ' + (S?.round || 1); }
    const sub = $id('sit-sub');
    if (sub) sub.textContent = ({ lobby: 'Game Lobby Room', picking: 'Выбор ситуации', ready: 'Подготовка', work: 'Live Game Arena',
      moderation: 'Проверка ответов', voting: 'Voting Arena', finished: 'Round Results' })[S?.phase] || 'Игровая комната';
    const o = $id('sit-online'); if (o) { o.textContent = on ? '● ОНЛАЙН' : '● ОЖИДАНИЕ'; o.classList.toggle('off', !on); }
  }

  /* ── блоки ── */
  const banner = (phase, title, text, emoji) => `<div class="sit-banner"><div class="em">${emoji || '🎭'}</div>
    <div style="min-width:0"><span class="sit-phase">${esc(phase)}</span><h2>${esc(title)}</h2><p>${esc(text)}</p></div></div>`;
  const chip = (ic, t) => `<div class="sit-chip"><span>${ic}</span>${esc(t)}</div>`;
  const initial = n => esc(String(n || '?').replace('@', '').charAt(0).toUpperCase());
  const noAv = new Set();
  window.sitAvErr = (id, el) => { noAv.add(String(id)); el.remove(); };
  function av(id, name, cls) {             // буква + фото поверх (если есть)
    const img = id && !noAv.has(String(id)) && tg?.initData
      ? `<img src="/api/avatar/${id}?init=${encodeURIComponent(tg.initData)}" alt="" loading="lazy" onerror="sitAvErr('${id}',this)">` : '';
    return `<div class="sit-av${cls ? ' ' + cls : ''}">${initial(name)}${img}</div>`;
  }
  const pl = (n, me, id) => `<div class="sit-pl${me ? ' me' : ''}">${av(id, n)}<span>${esc(n)}</span></div>`;

  function answerHtml(a, tid) {
    if (!a) return '<div class="sit-ans" style="color:var(--muted-fg)">Ответа пока нет</div>';
    let h = '';
    if (a.kind === 'text') h = esc(a.text || '');
    else {
      const url = `/api/sit/media/${tid}?v=${a.ver}&init=${encodeURIComponent(tg?.initData || '')}`;
      if (a.has_file) {
        const m = a.mtype, mime = a.mime || '';
        if (m === 'photo' || mime.startsWith('image/') && !mime.includes('tgsticker')) h += `<img src="${url}" alt="" loading="lazy">`;
        else if (m === 'video' || m === 'video_note' || mime.startsWith('video/')) h += `<video src="${url}" controls playsinline preload="metadata"></video>`;
        else if (m === 'voice' || m === 'audio' || mime.startsWith('audio/')) h += `<audio src="${url}" controls preload="metadata"></audio>`;
        else h += `<a href="${url}" target="_blank" style="color:var(--s-cyan)">📎 Открыть файл</a>`;
      } else h += '<i>Медиа</i>';
      if (a.caption) h += `<div class="cap">${esc(a.caption)}</div>`;
    }
    return `<div class="sit-ans">${h}</div>`;
  }

  /* ── экраны по фазам ── */
  function vNone() {
    return `<div class="sit-card sit-center"><div style="font-size:44px">🎭</div>
      <h3 style="margin:8px 0 4px;color:var(--foreground)">Сейчас игра не идёт</h3>
      <p style="margin:0;font-size:13px">Когда ведущий откроет набор, здесь появится комната. Загляни позже или жди оповещение от бота.</p></div>`;
  }

  function vLobby() {
    const me = S.in_room;
    const size = S.team_size === 3 ? 'Тройки (по 3)' : 'Пары (по 2)';
    let h = banner('Фаза: лобби', 'Набор в игру открыт!', 'Ждём запуска от ведущего…', '🎭');
    h += `<div class="sit-chips">${chip('👥', S.players_count + ' игроков')}${chip('🤝', size)}${chip('⏱️', S.work_minutes + ' минут')}</div>`;
    h += `<div class="sit-card"><div class="sit-me"><div><div class="lb">Твой статус</div>
      <div class="nm">${me ? 'Ты в комнате' : 'Ты не в игре'}</div></div>
      <span class="sit-badge${me ? '' : ' cy'}">${me ? 'В игре' : 'Не в игре'}</span></div>
      ${me ? '<button class="sit-btn sec" onclick="sitP(\'leave\')">Выйти из комнаты</button>'
           : '<button class="sit-btn" onclick="sitP(\'join\',{},\'Ты в игре! 🎭\')">Войти в игру</button>'}</div>`;
    h += `<div class="sit-h3">Как мы играем</div><div class="sit-steps">
      <div class="sit-step"><i>1</i>Вас разделят на случайные команды</div>
      <div class="sit-step"><i>2</i>Вы получите абсурдную ситуацию</div>
      <div class="sit-step"><i>3</i>Придумайте сценку в командном чате</div>
      <div class="sit-step"><i>4</i>Голосуем за самый смешной ответ!</div></div>`;
    return h;
  }

  function vPicking() {
    const p = S.picking || {};
    let h = banner('Фаза: выбор', 'Выбираем ситуацию', ({ manual: 'Ведущий выбирает вручную', random: 'Случайная ситуация из банка',
      suggest: 'Игроки предлагают идеи', vote: 'Игроки голосуют за вариант' })[p.mode] || '', '🎲');
    if (!S.in_room) h += reserveBlock();
    if (p.voting_sit && p.options.length) {
      h += `<div class="sit-card"><div class="sit-lbl">Голосуем за ситуацию</div>` +
        p.options.map((o, i) => `<button class="sit-opt${p.my_vote === i ? ' on' : ''}" onclick="sitP('svote',{index:${i}})"><b>${i + 1}</b><span>${esc(o)}</span></button>`).join('') + '</div>';
    } else if (p.can_suggest) {
      h += `<div class="sit-card"><div class="sit-lbl">Твоя идея для ситуации</div>
        <textarea class="sit-in" id="sit-sg" rows="3" maxlength="800" placeholder="Например: Объясняешь бабушке, что такое NFT" style="width:100%;margin-top:8px">${esc(p.my_suggestion || '')}</textarea>
        <button class="sit-btn" onclick="sitSuggest()">${p.my_suggestion ? 'Обновить идею' : 'Отправить идею'}</button></div>`;
    } else if (p.mode === 'suggest' && p.sg_closed) {
      h += '<div class="sit-card sit-center">💡 Сбор идей закрыт. Ведущий выбирает…</div>';
    } else {
      h += '<div class="sit-card sit-center">⏳ Подожди, ведущий готовит раунд…</div>';
    }
    if (S.team) h += teamCard();
    return h;
  }
  window.sitSuggest = () => { const v = $id('sit-sg')?.value.trim(); if (!v) return showToast('Напиши идею', 'error'); sitP('suggest', { text: v }, 'Идея отправлена 💡'); };

  function reserveBlock() {
    return `<div class="sit-card"><div class="sit-me"><div><div class="lb">Игра уже идёт</div><div class="nm" style="font-size:15px">Можно встать в запас</div></div></div>
      <button class="sit-btn cy" onclick="sitP('reserve',{},'Ты в запасе 🪑')">Отойти в запас</button></div>`;
  }

  function teamCard() {
    const t = S.team;
    return `<div class="sit-card sit-team"><div class="num">#${t.id}</div><div style="min-width:0">
      <div class="sit-lbl">Команда ${t.id}</div>
      <div class="sit-avs">${t.members.map(m => av(m.id, m.name, 'sm')).join('')}</div>
      <div style="font-size:14px;margin-top:2px">${t.members.map(m => esc(m.name)).join(' · ')}</div></div></div>`;
  }

  function vReady() {
    let h = banner('Фаза: старт', 'Ситуация выбрана', 'Ждём команду «Начали» от ведущего…', '🚦');
    if (S.reserve) h += '<div class="sit-card sit-center">🪑 Ты в запасе — если кто-то выпадет, ведущий подставит тебя.</div>';
    else if (S.team) h += teamCard();
    else if (!S.in_room) h += reserveBlock();
    return h;
  }

  function chatHtml() {
    const t = S.team;
    const msgs = (t.chat || []).map(m => {
      const mine = m.uid === S.uid;
      return `<div class="sit-msg${mine ? ' me' : ''}${m.admin ? ' adm' : ''}">${mine ? '' : `<small>${esc(m.name)}${m.admin ? ' (ведущий)' : ''}</small>`}${esc(m.text)}</div>`;
    }).join('') || '<div class="sit-note">Пока тихо — предложи первую идею 👇</div>';
    const ty = (t.typing || []).length ? `<div class="sit-typing"><i></i><i></i><i></i> ${esc(t.typing.join(', '))} печатает…</div>` : '<div class="sit-typing off"></div>';
    return `<div class="sit-card"><div class="sit-lbl">💬 Командный чат</div><div class="sit-chat" id="sit-chat">${msgs}</div>${ty}
      ${t.chat_open ? `<div class="sit-send"><textarea class="sit-in" id="sit-cin" rows="1" placeholder="Идея для сценки…" maxlength="3800"></textarea><button class="sit-go" onclick="sitChat()">➤</button></div>` : ''}</div>`;
  }
  window.sitChat = async () => {
    const el = $id('sit-cin'); const v = el?.value.trim(); if (!v) return;
    el.value = ''; const d = await act('chat_send', { text: v }); if (!d) el.value = v;
  };

  function vWork() {
    if (S.reserve || !S.team) {
      let h = banner('Фаза: сценка', 'Команды работают', 'Идёт раунд. Скоро голосование!', '⏱️');
      h += S.reserve ? '<div class="sit-card sit-center">🪑 Ты в запасе.</div>' : (!S.in_room ? reserveBlock() : '');
      return h;
    }
    const t = S.team, left = S.work_left;
    let h = `<div class="sit-card"><div class="sit-timer"><div><div class="sit-lbl">Фаза сценки</div><div style="font-size:19px;font-weight:800;margin-top:4px">Командный мозгоштурм</div></div>
      <div class="sit-clock" data-sit-timer>${fmt(left)}</div></div>
      <div class="sit-bar"><i id="sit-bar" style="width:${totalSec ? Math.min(100, left / totalSec * 100) : 100}%"></i></div>
      <div class="sit-note" id="sit-pct" style="text-align:left">Раунд ${S.round} · ${S.work_minutes} мин всего</div></div>`;
    h += `<div class="sit-card"><div class="sit-lbl">🎭 Ситуация раунда</div><div class="sit-situation">«${esc(S.situation)}»</div></div>`;
    h += teamCard() + chatHtml();
    h += `<div class="sit-card"><div class="sit-lbl">📝 Ответ команды <span class="sit-badge${t.submitted ? ' cy' : ''}" style="float:right;font-size:10px;padding:4px 9px">${t.submitted ? 'сдан' : 'в процессе'}</span></div>`;
    if (t.submitted) h += `<div style="margin-top:10px">${answerHtml(t.answer, t.id)}</div>`;
    h += `<textarea class="sit-in" id="sit-ans" rows="4" style="width:100%;margin-top:10px" maxlength="3800" placeholder="Текст ответа команды (сценка, диалог, описание)…"></textarea>
      <button class="sit-btn" onclick="sitSubmit()">${t.submitted ? 'Заменить ответ' : 'Сдать ответ'}</button>
      <button class="sit-btn sec" onclick="sitP('submit_media',{},'Открой чат с ботом и пришли фото/видео/гс')">📎 Сдать фото / видео / голос</button>
      <div class="sit-note">Пересдать можно до конца таймера</div></div>`;
    h += `<div class="sit-row"><button class="sit-btn sec" onclick="sitP('contact')">🆘 Ведущий / SOS</button>
      <button class="sit-btn sec" onclick="sitQuit()">🚪 Выйти из игры</button></div>`;
    return h;
  }
  window.sitSubmit = () => { const v = $id('sit-ans')?.value.trim(); if (!v) return showToast('Напиши ответ', 'error'); sitP('submit', { text: v }, 'Ответ сдан ✅').then(d => { if (d) dSet(''); }); };
  window.sitQuit = () => { if (confirm('Точно выйти из игры?')) sitP('quit'); };

  function vModeration() {
    let h = banner('Фаза: проверка', 'Ведущий смотрит ответы', 'Скоро начнётся голосование', '🔍');
    if (S.situation) h += `<div class="sit-card"><div class="sit-lbl">Ситуация</div><div class="sit-situation">«${esc(S.situation)}»</div></div>`;
    if (S.team) h += teamCard() + (S.team.answer ? `<div class="sit-card"><div class="sit-lbl">Ваш ответ</div><div style="margin-top:8px">${answerHtml(S.team.answer, S.team.id)}</div></div>` : '') + chatHtml();
    return h;
  }

  function vVoting() {
    const list = S.answers || [];
    if (!list.length) return banner('Голосование', 'Подождите', 'Ответы готовятся…', '🗳️');
    vIdx = Math.max(0, Math.min(vIdx, list.length - 1));
    const a = list[vIdx];
    let h = `<div class="sit-card"><div class="sit-lbl">Ситуация раунда</div><div class="sit-situation" style="font-size:17px">«${esc(S.situation)}»</div>
      <span class="sit-badge cy">Ответ ${vIdx + 1} из ${list.length}</span></div>`;
    h += `<div class="sit-card"><div style="font-size:18px;font-weight:800;margin-bottom:10px">Ответ №${a.n} ${a.mine ? '<span class="sit-badge" style="font-size:10px">твой</span>' : '<span class="sit-badge cy" style="font-size:10px">аноним 🎭</span>'}</div>
      ${answerHtml(a.answer, a.tid)}</div>`;
    h += `<div class="sit-nav"><button onclick="sitNav(-1)">‹ Пред</button><div class="sit-dots">${list.map((_, i) => `<i class="${i === vIdx ? 'on' : ''}"></i>`).join('')}</div><button onclick="sitNav(1)">След ›</button></div>`;
    const rs = S.react_set || [];
    h += `<div class="sit-reacts">${rs.map(e => `<button class="${a.my_react === e ? 'on' : ''}" ${a.mine ? 'disabled' : ''} onclick="sitReact(${a.tid},'${e}')">${e}${a.reactions && a.reactions[e] ? `<b>${a.reactions[e]}</b>` : ''}</button>`).join('')}</div>`;
    const voted = S.my_vote === a.tid;
    h += a.mine ? '<div class="sit-note">За свою команду голосовать нельзя 😉</div>'
      : `<button class="sit-btn${voted ? ' sec' : ''}" onclick="sitP('vote',{tid:${a.tid}},'Голос принят ✅')">${voted ? '✅ Твой голос здесь' : 'Проголосовать за этот ответ'}</button>
         <div class="sit-note">Выбор можно изменить до конца голосования</div>`;
    return h;
  }
  window.sitReact = (tid, e) => { call('react', { tid, emoji: e }); };
  window.sitNav = d => { vIdx += d; if (S) { const n = (S.answers || []).length; vIdx = (vIdx + n) % n; } lastSig = ''; render(); };

  function vFinished() {
    const r = S.results || [];
    if (!r.length) return banner('Итоги', 'Раунд завершён', 'Ведущий может запустить следующий', '🏁');
    const byv = r.slice(0, 3);
    const pod = (x, cls, n) => x ? `<div class="sit-pod ${cls}"><div class="sit-avs c">${(x.member_ids || []).map((id, i) => av(id, x.members[i], 'sm')).join('')}</div><div class="nm">${esc(x.members.join(' & '))}</div><div class="blk">${n}</div><div class="v">${x.votes} гол.</div></div>` : '';
    let h = `<div class="sit-banner" style="background:linear-gradient(135deg,#3a2a6b,#1b1b22);justify-content:center;text-align:center"><div><span class="sit-phase">Раунд завершён · голоса подсчитаны</span><h2>Авторы раскрыты! 🎭</h2></div></div>`;
    h += `<div class="sit-podium">${pod(byv[1], 'p2', 2)}${pod(byv[0], 'p1', 1)}${pod(byv[2], 'p3', 3)}</div>`;
    const w = r.find(x => x.winner) || r[0];
    h += `<div class="sit-card"><div class="sit-lbl">🏆 Лучшая сценка раунда · Команда #${w.tid}</div><div style="margin:10px 0">${answerHtml(w.answer, w.tid)}</div>
      <div style="font-size:13px;color:var(--muted-fg)">${esc(w.members.join(' & '))}</div></div>`;
    const mine = r.find(x => S.team && x.tid === S.team.id);
    if (mine) h += `<div class="sit-win"><div><div class="sit-lbl">Твой результат</div><div style="font-weight:800;margin-top:4px">${mine.winner ? '+1 победа в профиль! 🌟' : 'Команда #' + mine.tid + ': ' + mine.votes + ' гол.'}</div></div></div>`;
    h += `<button class="sit-btn sec" onclick="goTo('top')">Таблица лидеров</button>`;
    return h;
  }

  /* ── панель ведущего ── */
  function seg(cur, act, vals, labels) {
    return `<div class="sit-seg">${vals.map(v => `<button class="${String(cur) === String(v) ? 'on' : ''}" onclick="sitA('${act}',{value:${JSON.stringify(v)}})">${esc(labels ? labels[v] : v)}</button>`).join('')}</div>`;
  }
  function adminPanel() {
    const ad = S.admin; if (!ad) return '';
    const ph = S.phase; let b = '';
    if (ph === 'none' || ph === 'finished') {
      b += ph === 'none' ? '<button class="sit-btn" onclick="sitA(\'go\',{},\'Набор открыт\')">▶ Открыть набор</button>'
        : '<button class="sit-btn" onclick="sitA(\'again\',{},\'Новый раунд\')">🔁 Следующий раунд</button><button class="sit-btn sec" onclick="sitA(\'stop\')">⏹ Остановить игру</button>';
    } else {
      if (ph === 'lobby') {
        b += `<div class="sit-lbl">Размер команды</div>${seg(S.team_size, 'size', [2, 3], { 2: 'Пары', 3: 'Тройки' })}
          <div class="sit-lbl">Выбор ситуации</div>${seg(ad.sit_mode, 'mode', Object.keys(MODES), MODES)}
          <div class="sit-lbl">Время</div>${seg(S.work_minutes, 'time', ad.time_options, Object.fromEntries(ad.time_options.map(x => [x, x + ' мин'])))}
          <div class="sit-note" style="text-align:left">В комнате: ${ad.players.length}</div>
          <div class="sit-row"><button class="sit-btn sec" onclick="sitA('notify',{},'Оповещение отправлено')">📣 Оповестить</button><button class="sit-btn" onclick="sitA('close')">🔒 Закрыть набор</button></div>`;
      }
      if (ph === 'picking') {
        if (ad.sit_mode === 'manual') b += ad.sit_options.map((o, i) => `<button class="sit-opt" onclick="sitA('pick',{index:${i}})"><b>${i + 1}</b><span>${esc(o)}</span></button>`).join('')
          + '<button class="sit-btn sec" onclick="sitOwn()">✍️ Своя ситуация</button>';
        if (ad.voting_sit) b += ad.sit_options.map((o, i) => `<div class="sit-tr"><span>${i + 1}. ${esc(o)}</span><b>${ad.sit_votes[i] || 0}</b></div>`).join('') + `<div class="sit-note">Проголосовало: ${ad.sit_voted}</div><button class="sit-btn" onclick="sitA('endsvote')">Завершить голосование</button>`;
        if (ad.sit_mode === 'suggest' && !ad.sg_closed) b += '<button class="sit-btn" onclick="sitA(\'endsugg\')">Закрыть сбор идей</button>';
        if (ad.sg_closed && !ad.voting_sit) b += ad.ideas.map(x => `<div class="sit-tr"><span style="${x.kept ? '' : 'opacity:.4;text-decoration:line-through'}">${esc(x.text)}</span>
          <span style="display:flex;gap:6px"><button class="sit-btn sm sec" onclick="sitA('sgx',{index:${x.i}})">✕</button><button class="sit-btn sm" onclick="sitA('sgp',{index:${x.i}})">✓</button></span></div>`).join('')
          + '<div class="sit-row"><button class="sit-btn sec" onclick="sitA(\'sgrand\')">🎲 Случайная</button><button class="sit-btn sec" onclick="sitA(\'sgvote\')">🗳 На голосование</button></div>';
        b += '<button class="sit-btn sec" onclick="sitA(\'reroll\')">🔄 Другая ситуация</button>';
      }
      if (ph === 'ready') b += `<div class="sit-lbl">Ситуация</div><div class="sit-ans" style="margin:6px 0">${esc(S.situation || '—')}</div>
        <button class="sit-btn" onclick="sitA('begin',{},'Раунд начался')">🚀 Начать работу команд</button><button class="sit-btn sec" onclick="sitA('reroll')">🔄 Другая ситуация</button>`;
      if (ph === 'work') b += `<div class="sit-note" style="text-align:left">Сдали: ${ad.submitted} из ${ad.teams_count}</div>
        <div class="sit-row"><button class="sit-btn sec" onclick="sitA('plus',{},'+2 минуты')">+2 мин</button><button class="sit-btn" onclick="sitA('endwork')">Завершить работу</button></div>`;
      if (ph === 'moderation') b += ad.teams.map(t => `<div class="sit-tr"><span>#${t.id} ${esc(t.members.join(' & '))}<br><small style="color:var(--muted-fg)">${t.submitted ? '✅ ответ есть' : '— нет ответа'}</small></span>
          ${t.submitted ? `<span style="display:flex;gap:6px"><button class="sit-btn sm ${t.kept === false ? '' : 'sec'}" onclick="sitA('keep',{tid:${t.id},keep:false})">✕</button><button class="sit-btn sm ${t.kept === true ? '' : 'sec'}" onclick="sitA('keep',{tid:${t.id},keep:true})">✓</button></span>` : ''}</div>`).join('')
        + '<div class="sit-row"><button class="sit-btn sec" onclick="sitA(\'keepall\')">Оставить все</button><button class="sit-btn" onclick="sitA(\'startvote\')">Начать голосование</button></div>';
      if (ph === 'voting') b += `<div class="sit-note" style="text-align:left">Проголосовало: ${ad.voted_count}</div><button class="sit-btn" onclick="sitA('endvote')">🏁 Завершить голосование</button>`;
      b += '<button class="sit-btn sec" onclick="if(confirm(\'Остановить игру?\'))sitA(\'stop\')">⏹ Остановить игру</button>';
    }
    return `<div class="sit-adm"><div class="sit-lbl" style="cursor:pointer" onclick="sitAdm()">👑 Панель ведущего ${adminOpen ? '▾' : '▸'}</div>${adminOpen ? b : ''}</div>`;
  }
  window.sitAdm = () => { adminOpen = !adminOpen; lastSig = ''; render(); };
  window.sitOwn = () => { const t = prompt('Текст ситуации:'); if (t && t.trim()) sitA('own', { text: t.trim() }); };

  /* ── черновик ответа и «печатает…» ── */
  const dKey = () => S && S.team ? `sitdraft_${S.round}_${S.team.id}_${S.uid}` : null;
  const dGet = () => { try { const k = dKey(); return k ? localStorage.getItem(k) || '' : ''; } catch (e) { return ''; } };
  const dSet = v => { try { const k = dKey(); if (!k) return; v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) { /* нет хранилища */ } };
  let lastTyping = 0;
  function bindInput() {
    const el = root(); if (!el || el._sitBound) return; el._sitBound = true;
    el.addEventListener('input', e => {
      if (e.target.id === 'sit-ans') dSet(e.target.value);
      if (e.target.id === 'sit-cin' && Date.now() - lastTyping > 2500) { lastTyping = Date.now(); call('typing', {}, true); }
    });
  }

  /* ── отрисовка с сохранением ввода и прокрутки ── */
  function render() {
    const el = root(); if (!el || !S) return;
    head();
    const keep = {};
    ['sit-cin', 'sit-ans', 'sit-sg'].forEach(id => { const x = $id(id); if (x) keep[id] = { v: x.value, f: document.activeElement === x, s: x.selectionStart }; });
    const chat = $id('sit-chat'); const atBottom = !chat || chat.scrollHeight - chat.scrollTop - chat.clientHeight < 40;
    let h = ({ none: vNone, lobby: vLobby, picking: vPicking, ready: vReady, work: vWork, moderation: vModeration, voting: vVoting, finished: vFinished }[S.phase] || vNone)();
    h += adminPanel();
    el.innerHTML = h;
    if (!keep['sit-ans'] || !keep['sit-ans'].v) { const ta = $id('sit-ans'); const d = dGet(); if (ta && d) ta.value = d; }
    bindInput();
    for (const id in keep) { const x = $id(id); if (x) { if (keep[id].v) x.value = keep[id].v; if (keep[id].f) { x.focus(); try { x.setSelectionRange(keep[id].s, keep[id].s); } catch (e) {} } } }
    const c2 = $id('sit-chat'); if (c2 && atBottom) c2.scrollTop = c2.scrollHeight;
    const cin = $id('sit-cin'); if (cin) cin.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sitChat(); } });
    tick();
  }
})();
