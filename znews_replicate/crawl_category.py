import requests
from bs4 import BeautifulSoup
import re
import os

# Categories to replicate
categories = {
    'kinh-doanh': 'https://znews.vn/kinh-doanh-tai-chinh.html',
    'suc-khoe': 'https://znews.vn/suc-khoe.html',
    'the-thao': 'https://znews.vn/the-thao.html',
    'doi-song': 'https://znews.vn/doi-song.html',
    'cong-nghe': 'https://znews.vn/cong-nghe.html',
    'giai-tri': 'https://znews.vn/giai-tri.html'
}

def generate_category_pages():
    with open('index.html', 'r', encoding='utf-8') as f:
        index_html = f.read()

    # Split index.html into header and footer
    header_end = index_html.find('</header>')
    page_wrapper_start = index_html.find('<div class="page-wrapper">', header_end)
    footer_start = index_html.find('<footer id="footer">')

    header_html = index_html[:page_wrapper_start]
    footer_html = index_html[footer_start:]

    for cat_name, cat_url in categories.items():
        print(f"Crawling {cat_name} from {cat_url}...")
        try:
            response = requests.get(cat_url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find articles in the real category page
            articles = soup.find_all('article', class_='article-item')
            print(f"Found {len(articles)} articles.")
            
            # Extract HTML for articles
            articles_html = ""
            for article in articles:
                # Fix relative image src
                for img in article.find_all('img'):
                    if img.get('src') and img['src'].startswith('//'):
                        img['src'] = 'https:' + img['src']
                    elif img.get('data-src') and img['data-src'].startswith('//'):
                        img['src'] = 'https:' + img['data-src']
                # Fix relative links
                for a in article.find_all('a'):
                    if a.get('href') and a['href'].startswith('/'):
                        a['href'] = 'https://znews.vn' + a['href']

            # 1. Lead Block (1+4)
            featured_html = "<div class='category-full-width lead-block' style='display: flex; gap: 30px; margin-bottom: 40px;'>"
            if len(articles) > 0:
                featured_html += f"<div class='featured-lead' style='flex: 0 0 65%;'>{articles[0]}</div>"
            if len(articles) > 1:
                featured_html += "<div class='featured-sub-list' style='flex: 0 0 calc(35% - 30px); display: flex; flex-direction: column; gap: 20px;'>"
                for i in range(1, min(5, len(articles))):
                    featured_html += str(articles[i])
                featured_html += "</div>"
            featured_html += "</div>"
            
            # 2. Noi Bat Block (4 cols)
            noi_bat_html = ""
            if len(articles) > 5:
                noi_bat_html += "<div class='category-full-width noi-bat-block' style='margin-bottom: 40px; border-top: 2px solid #e2e8f0; padding-top: 20px;'>"
                noi_bat_html += "<h2 class='block-title' style='font-size: 14px; font-weight: bold; text-transform: uppercase; margin-bottom: 20px;'>Nổi bật</h2>"
                noi_bat_html += "<div class='grid-4-col' style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 25px;'>"
                for i in range(5, min(9, len(articles))):
                    noi_bat_html += f"<div class='grid-item'>{articles[i]}</div>"
                noi_bat_html += "</div></div>"

            # 3. Category Blocks (4 cols)
            cat_block_html = ""
            if len(articles) > 9:
                cat_headers_1 = ["Doanh nhân", "Bất động sản", "Tài chính - Chứng khoán", "Thị trường"]
                cat_block_html += "<div class='category-full-width sub-cat-block' style='margin-bottom: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px;'>"
                cat_block_html += "<div class='grid-4-col' style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 25px;'>"
                for i in range(4):
                    idx = 9 + i
                    if idx < len(articles):
                        cat_block_html += f"<div class='grid-item cat-col'><h3 class='cat-col-title' style='font-size: 14px; color: #007bff; border-bottom: 1px solid #007bff; padding-bottom: 5px; margin-bottom: 15px;'>{cat_headers_1[i]}</h3>{articles[idx]}</div>"
                cat_block_html += "</div></div>"

            if len(articles) > 13:
                cat_headers_2 = ["Kinh tế số", "Tiền của tôi", "Hàng không", "TTDN"]
                cat_block_html += "<div class='category-full-width sub-cat-block' style='margin-bottom: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px;'>"
                cat_block_html += "<div class='grid-4-col' style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 25px;'>"
                for i in range(4):
                    idx = 13 + i
                    if idx < len(articles):
                        cat_block_html += f"<div class='grid-item cat-col'><h3 class='cat-col-title' style='font-size: 14px; color: #007bff; border-bottom: 1px solid #007bff; padding-bottom: 5px; margin-bottom: 15px;'>{cat_headers_2[i]}</h3>{articles[idx]}</div>"
                cat_block_html += "</div></div>"
            
            # 4. Vertical list for remaining articles
            articles_html = ""
            for article in articles[17:35]: 
                articles_html += str(article) + "\n"

            # Capitalize Zone names properly
            zone_category = cat_name.replace('-', ' ').title().replace(' ', '')
            
            # Proper Vietnamese titles with diacritics
            category_titles = {
                'kinh-doanh': 'Kinh Doanh',
                'suc-khoe': 'Sức Khỏe',
                'the-thao': 'Thể Thao',
                'doi-song': 'Đời Sống',
                'cong-nghe': 'Công Nghệ',
                'giai-tri': 'Giải Trí'
            }
            display_title = category_titles.get(cat_name, cat_name.replace('-', ' ').title())
            
            # Dynamic Sub-navigation based on category
            sub_navs = {
                'kinh-doanh': ['Doanh nhân', 'Bất động sản', 'Tài chính - Chứng khoán', 'Thị trường', 'Kinh tế số', 'Tiền Của Tôi', 'Hàng không', 'Nông nghiệp'],
                'suc-khoe': ['Khỏe đẹp', 'Dinh dưỡng', 'Mẹ và Bé', 'Bệnh thường gặp', 'Thuốc mới', 'Nha khoa'],
                'the-thao': ['Bóng đá Việt Nam', 'Bóng đá Anh', 'Thể thao Thế giới', 'Võ thuật', 'Hậu trường', 'Tennis'],
                'doi-song': ['Giới trẻ', 'Xu hướng', 'Sống khỏe', 'Nhà đẹp', 'Gia đình', 'Du lịch'],
                'cong-nghe': ['Mobile', 'Gadget', 'Internet', 'Esports', 'AI', 'Chuyển đổi số'],
                'giai-tri': ['Sao Việt', 'Châu Á', 'Hollywood', 'Phim ảnh', 'Âm nhạc', 'Thời trang']
            }
            sub_categories = sub_navs.get(cat_name, [])
            sub_cat_html = " &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; ".join(sub_categories)
            
            financial_ticker_html = ""
            if cat_name == 'kinh-doanh':
                financial_ticker_html = """
        <div class="financial-ticker" style="display: flex; justify-content: space-between; padding-bottom: 20px; border-bottom: 1px solid #000; margin-bottom: 30px; font-size: 13px; text-align: left;">
            <div><span style="color: #007bff; font-weight: bold; font-size: 10px;">GIÁ VÀNG SJC</span><br><b>Mua</b><br> 146,200,000 &nbsp;&nbsp; <b>Bán</b><br> 150,200,000</div>
            <div><span style="color: #007bff; font-weight: bold; font-size: 10px;">TỶ GIÁ</span><br><b>USD Mua</b> 26,150 &nbsp;&nbsp; <b>Bán</b> 26,404<br><b>EUR Mua</b> 30,275 &nbsp;&nbsp; <b>Bán</b> 31,184</div>
            <div style="text-align: center; color: #999; font-size: 11px; padding-top: 10px;">Tài trợ bởi <br><b>HDBank</b></div>
            <div><span style="color: #007bff; font-weight: bold; font-size: 10px;">CHỨNG KHOÁN</span><br><b>VNINDEX <span style="color: green;">▲</span></b><br> 1,838.9 <span style="color: green;">+0.4%</span></div>
            <div><br><b>HNX <span style="color: red;">▼</span></b><br> 293.79 <span style="color: red;">-3.63%</span></div>
            <div><br><b>Upcom <span style="color: red;">▼</span></b><br> 125.09 <span style="color: red;">-0.61%</span></div>
        </div>"""
        
            # Build the new page-wrapper content
            # We add a skin ad container and side ad containers
            category_content = f"""
<!-- SKIN AD CONTAINER -->
<div id="znews-skin-ad" class="ad-container ad-skin" data-zone="Znews_{zone_category}_Background"></div>

<!-- SIDE ADS (Absolute positioned fixed relative to body) -->
<div class="ad-container ad-side-left sticky-ad" data-zone="Znews_{zone_category}_SideLeft"></div>
<div class="ad-container ad-side-right sticky-ad" data-zone="Znews_{zone_category}_SideRight"></div>

<div class="center-wrapper">
<div class="page-wrapper category-page">
    <div class="category-header-mock" style="width: 100%; margin-bottom: 30px;">
        <h1 style="font-size: 48px; font-weight: 800; text-transform: uppercase; margin: 30px 0; letter-spacing: 1px; text-align: center;">{display_title}</h1>
        
        <div style="border-top: 1px solid #000; border-bottom: 1px solid #e2e8f0; padding: 15px 0; margin-bottom: 15px; font-weight: 500; font-size: 14px; color: #333; text-align: left;">
            {sub_cat_html}
        </div>
        {financial_ticker_html}
        </div>

    <!-- MAIN GRIDS -->
    {featured_html}
    {noi_bat_html}
    {cat_block_html}

    <div class="container layout-two-col">
        <main class="main-content">
            <h2 class='block-title' style='font-size: 14px; font-weight: bold; text-transform: uppercase; margin-bottom: 20px;'>Vĩ mô</h2>
            <div class="article-list">
                {articles_html}
            </div>
        </main>
        
        <aside class="sidebar">
            <!-- IN-CONTENT SIDEBAR AD -->
            <div class="sidebar-ad-wrapper">
                <div class="ad-container ad-sidebar-box" data-zone="Znews_{zone_category}_SidebarBox"></div>
            </div>
        </aside>
    </div>
</div>
</div>
"""
            # Combine everything
            cat_header = header_html.replace('</head>', '<link rel="stylesheet" type="text/css" href="category-style.css" />\n</head>')
            full_html = cat_header + category_content + footer_html
            
            with open(f"{cat_name}.html", 'w', encoding='utf-8') as out_file:
                out_file.write(full_html)
            print(f"Generated {cat_name}.html successfully.")
            
        except Exception as e:
            print(f"Error processing {cat_name}: {e}")

if __name__ == "__main__":
    generate_category_pages()
