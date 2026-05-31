// MX-IP-Studio 六大 IP 計畫
// IP 清單真相＝Supabase `ip_projects`（codename=id）。下面這份是 fallback：
// 離線/未登入/讀取失敗時用，確保舊行為不變。loadIPs() 會在登入後用線上資料覆蓋。
//
// status（ip_projects）：
//   active   — 上線中（進會議開會包、可工作）
//   paused   — 暫停（不進會議，但仍可在 Skill Runner 充實內容）
//   archived — 結案（隱藏，不列）
//   （舊靜態值 temp 視同 paused：列出可工作、不進會議）
let IPS = [
  { id:'SIPAI',        name:'SIPAI 生意興龍',           status:'active', order_no:1 },
  { id:'CityMonsters', name:'City Monsters / 類格世代', status:'active', order_no:2 },
  { id:'HealingCat',   name:'全知療癒貓 / 不倒翁',      status:'paused', order_no:3 },
  { id:'PeekingX',     name:'偷瞄的X',                  status:'paused', order_no:4 },
  { id:'CtrlZ',        name:'早知道 Ctrl+Z',            status:'paused', order_no:5 },
  { id:'AHu',          name:'閣樓小精靈 A-Hu',          status:'paused', order_no:6 },
];

let ipById = new Map(IPS.map(ip => [ip.id, ip]));

// 上線中（進會議）= status==='active'。其餘（paused）仍列出、仍可工作。
function activeIPs(){ return IPS.filter(ip => ip.status === 'active'); }

// 從 Supabase ip_projects 動態載入 IP 清單（codename→id）。需登入（RLS：authenticated 可讀）。
// 任何失敗都靜默退回上面的靜態 IPS，確保頁面不會因此壞掉。回傳最終 IPS 陣列。
async function loadIPs(){
  try{
    const SB = (window.MXIPAuth && MXIPAuth.SB_URL) || '';
    const headers = (window.MXIPAuth && MXIPAuth.authHeaders) ? MXIPAuth.authHeaders() : null;
    if(!SB || !headers) return IPS;
    const r = await fetch(SB + '/rest/v1/ip_projects?select=codename,name,status,tier,created_at&order=created_at.asc', { headers });
    if(!r.ok) return IPS;
    const rows = await r.json();
    if(!Array.isArray(rows) || !rows.length) return IPS;
    const mapped = rows
      .filter(x => x && x.codename && x.status !== 'archived')
      .map((x,i) => ({ id:x.codename, name:x.name||x.codename, status:(x.status||'active'), tier:x.tier||'', order_no:i+1 }));
    if(mapped.length){ IPS = mapped; ipById = new Map(IPS.map(ip => [ip.id, ip])); }
  }catch(e){ /* 靜默退靜態 */ }
  return IPS;
}
