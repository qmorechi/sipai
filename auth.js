// ╔══════════════════════════════════════════════════════════════╗
// ║  auth.js — 方案 C / P1 共用登入層（草稿，尚未部署）            ║
// ╚══════════════════════════════════════════════════════════════╝
//
// 對應 docs/HANDOFF.md「方案 C」P1。roles.html / console.html / ray-upload.html
// 三頁共用：Google 登入（限 MX 公司 Workspace，比對主要網域 @minimax.com.tw）、
// session 管理、把寫入請求帶上使用者 JWT。
//
// 載入順序（頁面 <head> 或 inline script 之前）：
//   <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
//   <script src="auth.js"></script>
// 然後頁面 inline script 把 sbFetch 的 headers 換成 MXIPAuth.authHeaders()。
//
// ⚠️ 生效前提（缺一不可，否則登入會失敗 / 寫入會 401）：
//   1. Supabase Dashboard 已開 Google provider 並限網域 mx.design
//   2. drafts/DRAFT_20260529_auth_rls.sql 的 member_identities 已填真 email 並套用
//   3. 各表已 ENABLE RLS（在那之前 anon 仍可寫，登入只是「備好」不影響運作）
//
// 設計：讀（SELECT）一律可走 anon（公開唯讀）；寫（POST/PATCH/PUT/DELETE）要登入，
// 帶使用者 access_token 當 Bearer，RLS 再依角色判斷能不能寫。

(function (global) {
  'use strict';

  const SB_URL = 'https://cpzbwxgokmvayhzrvkqm.supabase.co';
  // anon key 與三頁相同（公開可見、設計上即如此；真正防護靠 RLS）
  const SB_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNwemJ3eGdva212YXloenJ2a3FtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkzNTY1NTYsImV4cCI6MjA5NDkzMjU1Nn0.7d_pasAywneqOxOHFGlc1dpMJcUv1BDCvhV2jYLaAGE';
  // mx.design 是 minimax.com.tw 的網域別名 → Google OIDC 回傳的 email 一律是主要地址
  // @minimax.com.tw（不是別名 @mx.design）。故允許網域 = minimax.com.tw。
  const ALLOWED_DOMAIN = 'minimax.com.tw';
  const WRITE_VERBS = ['POST', 'PATCH', 'PUT', 'DELETE'];

  if (!global.supabase || !global.supabase.createClient) {
    console.error('[auth] supabase-js 未載入 —— 請先放 @supabase/supabase-js CDN script');
  }

  const sb = global.supabase.createClient(SB_URL, SB_ANON, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });

  let _session = null;

  async function refreshSession() {
    const { data } = await sb.auth.getSession();
    _session = data.session || null;
    return _session;
  }

  function currentUser() { return _session && _session.user ? _session.user : null; }
  function accessToken() { return _session ? _session.access_token : null; }
  function currentEmail() {
    const u = currentUser();
    return u && u.email ? u.email.toLowerCase() : null;
  }
  function isAllowed() {
    const e = currentEmail();
    return !!e && e.endsWith('@' + ALLOWED_DOMAIN);
  }

  // REST 用 headers：登入且網域對 → 帶使用者 JWT；否則退回 anon（讀公開）。
  // apikey 永遠帶 anon key（Supabase 要求，登入後也要）。
  function authHeaders(extra) {
    const tok = (isAllowed() && accessToken()) ? accessToken() : SB_ANON;
    return Object.assign(
      { apikey: SB_ANON, Authorization: 'Bearer ' + tok, 'Content-Type': 'application/json' },
      extra || {}
    );
  }

  function isWrite(opts) {
    const m = (opts && opts.method ? opts.method : 'GET').toUpperCase();
    return WRITE_VERBS.indexOf(m) !== -1;
  }

  async function signIn() {
    await sb.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: location.href.split('#')[0],
        queryParams: { hd: ALLOWED_DOMAIN, prompt: 'select_account' },
      },
    });
  }

  async function signOut() {
    await sb.auth.signOut();
    _session = null;
    if (_idleTimer) { clearTimeout(_idleTimer); _idleTimer = null; }
    renderBar();
  }

  // ── 閒置自動登出（座位/共用裝置防護）──
  // 成員在公司外用個人/共用裝置登入後若離開，閒置超過 IDLE_MS 自動 signOut，
  // 避免登入態被留著讓非相關的人接手寫入。核心安全仍是 RLS，此為額外一層。
  const IDLE_MS = 30 * 60 * 1000; // 30 分鐘
  let _idleTimer = null;
  function resetIdle() {
    if (_idleTimer) clearTimeout(_idleTimer);
    if (!currentUser()) return;          // 沒登入不用計時
    _idleTimer = setTimeout(async function () {
      if (!currentUser()) return;
      await signOut();
      alert('因閒置過久已自動登出，請重新登入');
    }, IDLE_MS);
  }
  function startIdleWatch() {
    ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart'].forEach(function (ev) {
      window.addEventListener(ev, resetIdle, { passive: true });
    });
  }

  // 寫入前呼叫：未登入 → 觸發登入並回 false（呼叫端應中止本次寫入）。
  // 登入了但非允許網域 → 登出 + 提示。允許網域 → true。
  async function requireLogin() {
    if (!_session) await refreshSession();
    if (currentUser() && isAllowed()) return true;
    if (currentUser() && !isAllowed()) {
      alert('請改用 MX 公司的 Google 帳號登入');
      await signOut();
      return false;
    }
    await signIn(); // 會跳轉 OAuth，回來後 session 就緒
    return false;
  }

  // 給 sbFetch 包一層：寫入且未登入 → 擋下並引導登入；其餘照常。
  // 用法：sbFetch 內 `if (await MXIPAuth.guardWrite(opts)) return;` 後再發 request。
  async function guardWrite(opts) {
    if (!isWrite(opts)) return false;       // 讀：放行
    if (!_session) await refreshSession();
    if (currentUser() && isAllowed()) return false; // 已登入：放行
    await requireLogin();
    return true; // 已攔截（觸發登入或提示），呼叫端中止
  }

  // ── 登入列 UI（右上角浮動）──
  function renderBar() {
    let bar = document.getElementById('mxip-authbar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'mxip-authbar';
      bar.style.cssText = 'position:fixed;top:8px;right:12px;z-index:9999;font:13px/1.4 system-ui,sans-serif;display:flex;gap:8px;align-items:center;background:rgba(20,24,30,.82);color:#e7edf3;padding:6px 10px;border-radius:8px;backdrop-filter:blur(6px)';
      document.body.appendChild(bar);
    }
    const u = currentUser();
    if (u && isAllowed()) {
      const md = u.user_metadata || {};
      const nm = md.full_name || md.name || (u.email ? u.email.split('@')[0] : '已登入');
      bar.innerHTML = '<span>✅ ' + nm + '</span><button id="mxip-signout" style="cursor:pointer;border:0;border-radius:6px;padding:3px 8px;background:#33405a;color:#cfe">登出</button>';
      bar.querySelector('#mxip-signout').onclick = signOut;
    } else if (u && !isAllowed()) {
      bar.innerHTML = '<span>⚠️ 非公司帳號</span><button id="mxip-signout" style="cursor:pointer;border:0;border-radius:6px;padding:3px 8px;background:#5a3340;color:#fcc">換帳號</button>';
      bar.querySelector('#mxip-signout').onclick = signOut;
    } else {
      bar.innerHTML = '<button id="mxip-signin" style="cursor:pointer;border:0;border-radius:6px;padding:4px 10px;background:#2d6cdf;color:#fff">用 MX 公司帳號登入</button>';
      bar.querySelector('#mxip-signin').onclick = signIn;
    }
  }

  // 頁面載入呼叫一次。回傳 session（可能為 null）。
  async function init() {
    await refreshSession();
    sb.auth.onAuthStateChange(function (_evt, session) {
      _session = session || null;
      renderBar();
      resetIdle();              // 登入後開始計時、登出後清掉
    });
    startIdleWatch();
    resetIdle();                // 若一進來就是登入態，立即起算
    if (document.body) renderBar();
    else document.addEventListener('DOMContentLoaded', renderBar);
    return _session;
  }

  global.MXIPAuth = {
    init, signIn, signOut, requireLogin, guardWrite, authHeaders,
    currentUser, currentEmail, accessToken, isAllowed, refreshSession,
    SB_URL, SB_ANON,
  };
})(window);
