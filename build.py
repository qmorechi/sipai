#!/usr/bin/env python3
"""
SIPAI Site Builder
讀取 Notion 資料 → 下載圖片 → 生成 timeline.html
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
    'timeline': '3226af6a916d80d3904dd6583d619056',   # SIPAI_開發日誌
    'sipai_2d': '3426af6a916d809fba3ef4cc00e06e2c',   # SIPAI 2D設定
    'myao':     '34c6af6a916d803b962ad041d25c7efd',   # 全知療癒貓（不倒翁頁）
}

# ── 角色對應：placeholder emoji → 從 Notion 抓到的 key ──
CHARACTER_KEYS = {
    'sipai_jian':      '阿見(JIAN)',
    'sipai_lei':       '雷仔(LEI)',
    'sipai_bao':       '阿抱(BAO)',
    'sipai_stevensen': '史蒂芬(STEVENSEN)',
    'sipai_debby':     '黛比(Debby)',
    'sipai_yaya':      '牙牙(YAYA)',
}


def notion_get(path):
    req = urllib.request.Request(
        f'https://api.notion.com/v1/{path}',
        headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def get_image_urls_from_page(page_id):
    """遞迴讀取頁面內所有圖片 URL（含 toggle 內）"""
    urls = []
    try:
        data = notion_get(f'blocks/{page_id}/children?page_size=100')
    except Exception as e:
        print(f'  blocks 讀取失敗 {page_id[:8]}: {e}')
        return urls

    for block in data.get('results', []):
        btype = block.get('type', '')
        if btype == 'image':
            img = block['image']
            url = (img.get('file') or {}).get('url') or (img.get('external') or {}).get('url')
            if url:
                urls.append(url)
        if block.get('has_children'):
            urls.extend(get_image_urls_from_page(block['id']))
    return urls


def get_toggle_images(page_id):
    """讀取 toggle block 內的圖片，key = toggle 標題"""
    result = {}
    try:
        data = notion_get(f'blocks/{page_id}/children?page_size=100')
    except:
        return result

    for block in data.get('results', []):
        btype = block.get('type', '')
        if btype in ('toggle', 'details') and block.get('has_children'):
            title_parts = block.get(btype, {}).get('rich_text', [])
            title = ''.join(p.get('plain_text', '') for p in title_parts)
            child_urls = get_image_urls_from_page(block['id'])
            if child_urls:
                result[title] = child_urls[0]  # 取每個角色第一張
    return result


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


def fetch_sipai_images():
    """抓 SIPAI 六角色圖片"""
    print('讀取 SIPAI 2D 設定頁面...')
    toggle_imgs = get_toggle_images(PAGE_IDS['sipai_2d'])
    print(f'  找到 toggle 群組: {list(toggle_imgs.keys())}')

    result = {}
    # 主圖（頁面最上面的圖，非 toggle 內）
    main_urls = []
    try:
        data = notion_get(f'blocks/{PAGE_IDS["sipai_2d"]}/children?page_size=100')
        for block in data.get('results', []):
            if block.get('type') == 'image':
                img = block['image']
                url = (img.get('file') or {}).get('url') or (img.get('external') or {}).get('url')
                if url:
                    main_urls.append(url)
    except Exception as e:
        print(f'  主圖讀取失敗: {e}')

    if main_urls:
        print(f'  主圖: {len(main_urls)} 張，下載第 1 張...')
        try:
            result['sipai_group'] = compress_url(main_urls[0])
            print('  ✓ sipai_group')
        except Exception as e:
            print(f'  ✗ sipai_group: {e}')

    # 六角色
    for key, toggle_title in CHARACTER_KEYS.items():
        url = toggle_imgs.get(toggle_title)
        if url:
            try:
                result[key] = compress_url(url)
                print(f'  ✓ {key}')
            except Exception as e:
                print(f'  ✗ {key}: {e}')
        else:
            print(f'  - {key} ({toggle_title}) 未找到圖片')

    return result


def read_existing_html(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


def inject_sipai_images(html, imgs):
    """把 SIPAI 角色圖片注入 HTML"""

    # SIPAI 群組圖（#003 的 ip-card 偷瞄的X 佔位符）
    # 在 ip-card 裡找偷瞄的X 那張，如果有 sipai_group 就換掉
    if 'sipai_group' in imgs:
        # 在 偷瞄的X 那個 ip-card 的 ip-image 裡插入圖
        html = html.replace(
            '<div class="ip-image"><div class="ip-image-placeholder">👁</div><div class="ip-image-hint">偷瞄的X</div></div>',
            f'<div class="ip-image"><img src="{imgs["sipai_group"]}" alt="SIPAI 偷瞄的X"></div>'
        )

    # SIPAI 在 session 4 的六角色卡片（City Monsters 區塊不動，只動 SIPAI 相關的）
    # 這裡為 session 4 加入 SIPAI 角色展示區塊，目前先做 placeholder 對應
    char_map = {
        'sipai_jian':      ('阿見 JIAN', '👁'),
        'sipai_lei':       ('雷仔 LEI', '⚡'),
        'sipai_bao':       ('阿抱 BAO', '🤗'),
        'sipai_stevensen': ('史蒂芬 STEVENSEN', '🎩'),
        'sipai_debby':     ('黛比 Debby', '🌸'),
        'sipai_yaya':      ('牙牙 YAYA', '🦷'),
    }

    for key, (name, emoji) in char_map.items():
        if key in imgs:
            # 找到對應的佔位符並替換
            old = f'<div class="ip-image-placeholder">{emoji}</div><div class="ip-image-hint">{name}</div>'
            new = f'<img src="{imgs[key]}" alt="{name}">'
            if old in html:
                html = html.replace(
                    f'<div class="ip-image">{old}</div>',
                    f'<div class="ip-image">{new}</div>'
                )

    return html


def build():
    print('=' * 50)
    print('SIPAI Site Builder 啟動')
    print('=' * 50)

    # 1. 讀取現有 HTML
    timeline_html = read_existing_html('timeline.html')
    if not timeline_html:
        print('⚠️  timeline.html 不存在，跳過圖片注入')
        return

    # 2. 抓 SIPAI 角色圖片
    sipai_imgs = {}
    if NOTION_TOKEN:
        try:
            sipai_imgs = fetch_sipai_images()
            print(f'\n共取得 {len(sipai_imgs)} 張圖片')
        except Exception as e:
            print(f'圖片抓取失敗: {e}')
    else:
        print('⚠️  NOTION_TOKEN 未設定，跳過圖片更新')

    # 3. 注入圖片到 HTML
    if sipai_imgs:
        timeline_html = inject_sipai_images(timeline_html, sipai_imgs)
        print('✓ 圖片注入完成')

    # 4. 更新 build 時間戳記
    from datetime import datetime, timezone, timedelta
    tw_time = datetime.now(timezone(timedelta(hours=8))).strftime('%Y/%m/%d %H:%M')
    timeline_html = re.sub(
        r'<!-- BUILD_TIME -->.*?<!-- /BUILD_TIME -->',
        f'<!-- BUILD_TIME --><span style="font-size:11px;color:#5a6270">自動更新：{tw_time} TW</span><!-- /BUILD_TIME -->',
        timeline_html
    )

    # 5. 寫出
    with open('timeline.html', 'w', encoding='utf-8') as f:
        f.write(timeline_html)
    print(f'✓ timeline.html 已更新')

    print('\n完成！')


if __name__ == '__main__':
    build()
