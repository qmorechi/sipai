#!/usr/bin/env python3
"""
SIPAI Site Builder
讀取 Notion 資料 → 下載圖片 → 注入 timeline.html
每天由 GitHub Action 自動執行
"""

import os, re, base64, json, urllib.request
from PIL import Image
import io

NOTION_TOKEN = os.environ.get('NOTION_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {NOTION_TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json',
}

# ── Notion 頁面 ID ──
PAGE_IDS = {
    'sipai_2d':    '3426af6a916d809fba3ef4cc00e06e2c',  # SIPAI 2D設定（六角色）
    'city':        '3566af6a916d8058a005f522421f7b40',  # City Monsters 世界觀
    'myao':        '34c6af6a916d803b962ad041d25c7efd',  # 全知療癒貓
}


def notion_get(path):
    req = urllib.request.Request(
        f'https://api.notion.com/v1/{path}',
        headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def get_all_image_urls(page_id, depth=0):
    """遞迴讀取頁面內所有圖片 URL"""
    if depth > 3:
        return []
    urls = []
    try:
        data = notion_get(f'blocks/{page_id}/children?page_size=100')
    except Exception as e:
        print(f'  {"  "*depth}blocks 讀取失敗: {e}')
        return urls
    for block in data.get('results', []):
        btype = block.get('type', '')
        if btype == 'image':
            img = block['image']
            url = (img.get('file') or {}).get('url') or (img.get('external') or {}).get('url')
            if url:
                urls.append(url)
        if block.get('has_children'):
            urls.extend(get_all_image_urls(block['id'], depth+1))
    return urls


def compress_url(url, max_w=600, quality=72):
    """下載並壓縮圖片，回傳 base64 data URI"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    img = Image.open(io.BytesIO(data)).convert('RGB')
    w, h = img.size
    if w > max_w:
        img = img.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=quality, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def fetch_images():
    """抓取所有需要的圖片，回傳 {key: base64_data_uri}"""
    result = {}

    # ── SIPAI 主圖（第一張群組圖）──
    print('讀取 SIPAI 2D 設定...')
    sipai_urls = get_all_image_urls(PAGE_IDS['sipai_2d'])
    print(f'  找到 {len(sipai_urls)} 張圖片')
    if sipai_urls:
        try:
            result['sipai_main'] = compress_url(sipai_urls[0])
            print(f'  ✓ sipai_main')
        except Exception as e:
            print(f'  ✗ sipai_main: {e}')

    # ── City Monsters 主圖 ──
    print('讀取 City Monsters...')
    city_urls = get_all_image_urls(PAGE_IDS['city'])
    print(f'  找到 {len(city_urls)} 張圖片')
    if city_urls:
        try:
            result['city_main'] = compress_url(city_urls[0])
            print(f'  ✓ city_main')
        except Exception as e:
            print(f'  ✗ city_main: {e}')

    return result


def inject_images(html, imgs):
    """把圖片注入 HTML 的對應佔位符"""

    # SIPAI 卡片：🚀 佔位符
    if 'sipai_main' in imgs:
        old = '<div class="ip-image"><div class="ip-image-placeholder">🚀</div><div class="ip-image-hint">SIPAI 生意興龍</div></div>'
        new = f'<div class="ip-image"><img src="{imgs["sipai_main"]}" alt="SIPAI 生意興龍"></div>'
        if old in html:
            html = html.replace(old, new)
            print('  ✓ SIPAI 圖片注入')
        else:
            print('  ✗ SIPAI 佔位符找不到')

    # City Monsters 卡片：🏙️ 佔位符
    if 'city_main' in imgs:
        old = '<div class="ip-image"><div class="ip-image-placeholder">🏙️</div><div class="ip-image-hint">City Monsters 阿灰</div></div>'
        new = f'<div class="ip-image"><img src="{imgs["city_main"]}" alt="City Monsters 阿灰"></div>'
        if old in html:
            html = html.replace(old, new)
            print('  ✓ City Monsters 圖片注入')
        else:
            print('  ✗ City Monsters 佔位符找不到')

    return html


def build():
    print('=' * 50)
    print('SIPAI Site Builder 啟動')
    print('=' * 50)

    # 讀取現有 HTML
    if not os.path.exists('timeline.html'):
        print('⚠️  timeline.html 不存在')
        return
    with open('timeline.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 抓圖片
    if not NOTION_TOKEN:
        print('⚠️  NOTION_TOKEN 未設定，跳過圖片更新')
    else:
        imgs = fetch_images()
        print(f'\n共取得 {len(imgs)} 張圖片')
        if imgs:
            print('注入圖片...')
            html = inject_images(html, imgs)

    # 更新時間戳記
    from datetime import datetime, timezone, timedelta
    tw_time = datetime.now(timezone(timedelta(hours=8))).strftime('%Y/%m/%d %H:%M')
    html = re.sub(
        r'<!-- BUILD_TIME -->.*?<!-- /BUILD_TIME -->',
        f'<!-- BUILD_TIME --><span style="font-size:11px;color:#5a6270">自動更新：{tw_time} TW</span><!-- /BUILD_TIME -->',
        html
    )

    with open('timeline.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n✓ 完成！timeline.html 已更新')


if __name__ == '__main__':
    build()
