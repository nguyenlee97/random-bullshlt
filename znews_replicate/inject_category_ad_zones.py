"""
inject_category_ad_zones.py
Injects AdsPilot-compatible ad zone containers into all 6 ZNews category HTML pages.
Run once from the znews_replicate/ directory: python inject_category_ad_zones.py
"""
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

# slug → zone name prefix
CATEGORIES = {
    'the-thao':   'TheThao',
    'kinh-doanh': 'KinhDoanh',
    'cong-nghe':  'CongNghe',
    'giai-tri':   'GiaiTri',
    'doi-song':   'DoiSong',
    'suc-khoe':   'SucKhoe',
}

def make_injection(prefix: str) -> str:
    """
    Returns an HTML snippet to inject just before </body>.

    Zones created:
      • Znews_{prefix}_Background  – 0px overlay added to _BACKGROUND_ZONE_IDS
                                     on the backend; shown via top-of-page crop.
      • Znews_{prefix}_SidebarBox  – 300×250px div injected into .sidebar
      • Znews_{prefix}_SideLeft    – 160×600 fixed panel on the left gutter
      • Znews_{prefix}_SideRight   – 160×600 fixed panel on the right gutter
    """
    return f"""
<!-- ═══ AdsPilot Zone Containers ({prefix}) ═══════════════════════════════ -->
<!-- Background skin: 0-height placeholder (backend uses top-of-page fallback) -->
<div id="Znews_{prefix}_Background"
     style="position:absolute;top:0;left:0;width:100%;height:0;pointer-events:none;z-index:-999;">
</div>

<!-- Sticky side panels: fixed-position, always visible after DOMContentLoaded -->
<div id="Znews_{prefix}_SideLeft"
     style="position:fixed;left:0;top:200px;width:160px;height:600px;
            z-index:9000;pointer-events:none;background:transparent;">
</div>
<div id="Znews_{prefix}_SideRight"
     style="position:fixed;right:0;top:200px;width:160px;height:600px;
            z-index:9000;pointer-events:none;background:transparent;">
</div>

<script>
/* AdsPilot: inject sidebar box zone into the existing .sidebar element */
(function () {{
    var sidebar = (
        document.querySelector('section.sidebar') ||
        document.querySelector('.section-sidebar') ||
        document.querySelector('.sidebar')
    );
    var box = document.createElement('div');
    box.id    = 'Znews_{prefix}_SidebarBox';
    box.style.cssText = 'width:300px;height:250px;display:block;';
    if (sidebar) {{
        sidebar.insertBefore(box, sidebar.firstChild);
    }} else {{
        /* Fallback: absolute position at 300px from top-right */
        box.style.cssText += 'position:absolute;top:300px;right:0;';
        document.body.appendChild(box);
    }}
}})();
</script>
<!-- ════════════════════════════════════════════════════════════════════════ -->
"""

def inject(slug: str, prefix: str):
    path = os.path.join(BASE, f'{slug}.html')
    if not os.path.exists(path):
        print(f'  SKIP (not found): {slug}.html')
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    marker = f'Znews_{prefix}_SidebarBox'
    if marker in content:
        print(f'  SKIP (already injected): {slug}.html')
        return

    if '</body>' not in content:
        print(f'  SKIP (no </body>): {slug}.html')
        return

    new_content = content.replace('</body>', make_injection(prefix) + '</body>', 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f'  OK: {slug}.html  →  Znews_{prefix}_{{Background,SidebarBox,SideLeft,SideRight}}')

if __name__ == '__main__':
    print('Injecting ad zones into ZNews category pages...')
    for slug, prefix in CATEGORIES.items():
        inject(slug, prefix)
    print('Done.')
