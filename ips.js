// MX-IP-Studio 六大 IP 計畫
// Phase 1 寫死在 JS,Phase 3 之後再考慮上 Supabase
//
// status:
//   active   — 進行中(列在主控台 IP 選單前面)
//   paused   — 暫停(列出但灰色)
//   archived — 結案(預設不顯示)
//   temp     — 暫存 / 觀察(列在最後,可隨時轉 active)
const IPS = [
  { id:'SIPAI',        name:'SIPAI 生意興龍',           status:'active', order_no:1 },
  { id:'CityMonsters', name:'City Monsters / 類格世代', status:'active', order_no:2 },
  { id:'HealingCat',   name:'全知療癒貓 / 不倒翁',      status:'temp',   order_no:3 },
  { id:'PeekingX',     name:'偷瞄的X',                  status:'temp',   order_no:4 },
  { id:'CtrlZ',        name:'早知道 Ctrl+Z',            status:'temp',   order_no:5 },
  { id:'AHu',          name:'閣樓小精靈 A-Hu',          status:'temp',   order_no:6 },
];

const ipById = new Map(IPS.map(ip => [ip.id, ip]));
