"""Generate NP-6 ZNews topic fixtures from the existing ZNews category shell.

The source shell is one of the already-captured category pages. Only the
publisher chrome, CSS, scripts, and DOM conventions are reused. Article copy
and imagery are deterministic synthetic fixtures created for NP-6.
"""

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSET_ROOT = "assets/np6-topics"

TOPICS = [
    {
        "slug": "family-parenting",
        "file": "gia-dinh.html",
        "code": "FamilyParenting",
        "title": "Gia Đình & Nuôi Dạy Con",
        "base": "suc-khoe.html",
        "subnav": ["Cha mẹ", "Mẹ và bé", "Dinh dưỡng trẻ em", "Giáo dục gia đình", "Tổ ấm"],
        "subjects": ["nuôi dạy con", "sức khỏe trẻ nhỏ", "kết nối gia đình", "dinh dưỡng cho bé", "kỹ năng làm cha mẹ"],
    },
    {
        "slug": "education-careers",
        "file": "giao-duc-nghe-nghiep.html",
        "code": "EducationCareers",
        "title": "Giáo Dục & Nghề Nghiệp",
        "base": "kinh-doanh.html",
        "subnav": ["Trường học", "Du học", "Kỹ năng", "Tuyển dụng", "Phát triển nghề nghiệp"],
        "subjects": ["kỹ năng nghề nghiệp", "giáo dục hiện đại", "học tập suốt đời", "cơ hội việc làm", "đào tạo số"],
    },
    {
        "slug": "travel-hospitality",
        "file": "du-lich-luu-tru.html",
        "code": "TravelHospitality",
        "title": "Du Lịch & Lưu Trú",
        "base": "doi-song.html",
        "subnav": ["Điểm đến", "Khách sạn", "Hàng không", "Ẩm thực địa phương", "Kinh nghiệm"],
        "subjects": ["du lịch Việt Nam", "trải nghiệm nghỉ dưỡng", "hàng không", "khách sạn xanh", "điểm đến mới"],
    },
    {
        "slug": "automotive-mobility",
        "file": "xe-di-chuyen.html",
        "code": "AutomotiveMobility",
        "title": "Xe & Di Chuyển",
        "base": "cong-nghe.html",
        "subnav": ["Ô tô", "Xe máy", "Xe điện", "Công nghệ xe", "Kinh nghiệm lái"],
        "subjects": ["xe điện", "ô tô gia đình", "công nghệ an toàn", "hạ tầng sạc", "thị trường xe"],
    },
    {
        "slug": "home-property-architecture",
        "file": "nha-o-bat-dong-san.html",
        "code": "HomePropertyArchitecture",
        "title": "Nhà Ở, Bất Động Sản & Kiến Trúc",
        "base": "kinh-doanh.html",
        "subnav": ["Thị trường", "Kiến trúc", "Nội thất", "Nhà ở", "Quy hoạch"],
        "subjects": ["nhà ở đô thị", "kiến trúc bền vững", "thị trường bất động sản", "không gian sống", "quy hoạch"],
    },
    {
        "slug": "society-news-law",
        "file": "xa-hoi-phap-luat.html",
        "code": "SocietyNewsLaw",
        "title": "Xã Hội, Thời Sự & Pháp Luật",
        "base": "doi-song.html",
        "subnav": ["Đời sống", "Pháp luật", "Giao thông", "Cộng đồng", "Môi trường"],
        "subjects": ["chính sách gần cuộc sống", "an toàn cộng đồng", "pháp luật dân sinh", "giao thông đô thị", "hoạt động xã hội"],
    },
    {
        "slug": "marketing-digital-business",
        "file": "marketing-kinh-doanh-so.html",
        "code": "MarketingDigitalBusiness",
        "title": "Marketing & Kinh Doanh Số",
        "base": "kinh-doanh.html",
        "subnav": ["Quảng cáo", "Thương mại số", "Khởi nghiệp", "Mạng xã hội", "Doanh nghiệp nhỏ"],
        "subjects": ["marketing số", "thương mại điện tử", "khởi nghiệp", "quảng cáo trực tuyến", "doanh nghiệp nhỏ"],
    },
    {
        "slug": "fitness-active-living",
        "file": "fitness-song-khoe.html",
        "code": "FitnessActiveLiving",
        "title": "Fitness & Sống Năng Động",
        "base": "suc-khoe.html",
        "subnav": ["Tập luyện", "Chạy bộ", "Yoga", "Dinh dưỡng thể thao", "Phục hồi"],
        "subjects": ["tập luyện thể chất", "chạy bộ", "yoga", "rèn luyện sức bền", "phục hồi vận động"],
    },
    {
        "slug": "soccer-fandom",
        "file": "bong-da.html",
        "code": "SoccerFandom",
        "title": "Bóng Đá",
        "base": "the-thao.html",
        "subnav": ["Bóng đá Việt Nam", "Bóng đá Anh", "Quốc tế", "Hậu trường", "Người hâm mộ"],
        "subjects": ["bóng đá Việt Nam", "giải đấu quốc tế", "cộng đồng người hâm mộ", "chiến thuật bóng đá", "cầu thủ trẻ"],
    },
    {
        "slug": "gaming-esports",
        "file": "game-esports.html",
        "code": "GamingEsports",
        "title": "Game & Esports",
        "base": "cong-nghe.html",
        "subnav": ["Esports", "Game mobile", "Game PC", "Cộng đồng", "Thiết bị chơi game"],
        "subjects": ["esports", "game mobile", "cộng đồng game thủ", "thiết bị chơi game", "giải đấu điện tử"],
    },
    {
        "slug": "movies-tv-streaming",
        "file": "phim-truyen-hinh.html",
        "code": "MoviesTvStreaming",
        "title": "Phim, Truyền Hình & Streaming",
        "base": "giai-tri.html",
        "subnav": ["Phim Việt", "Phim quốc tế", "Truyền hình", "Streaming", "Hậu trường"],
        "subjects": ["điện ảnh Việt", "nền tảng streaming", "sản xuất truyền hình", "phim tài liệu", "hậu trường phim"],
    },
    {
        "slug": "music-live-events",
        "file": "am-nhac-su-kien.html",
        "code": "MusicLiveEvents",
        "title": "Âm Nhạc & Sự Kiện",
        "base": "giai-tri.html",
        "subnav": ["Nhạc Việt", "Quốc tế", "Concert", "Lễ hội", "Nghệ sĩ"],
        "subjects": ["âm nhạc Việt", "concert", "lễ hội âm nhạc", "nghệ sĩ trẻ", "sân khấu trực tiếp"],
    },
    {
        "slug": "books-reading",
        "file": "sach-va-doc.html",
        "code": "BooksReading",
        "title": "Sách & Văn Hóa Đọc",
        "base": "giai-tri.html",
        "subnav": ["Sách mới", "Văn học", "Truyện tranh", "E-book", "Cộng đồng đọc"],
        "subjects": ["văn hóa đọc", "sách mới", "văn học Việt", "thư viện cộng đồng", "xuất bản số"],
    },
    {
        "slug": "arts-crafts-photography",
        "file": "nghe-thuat-sang-tao.html",
        "code": "ArtsCraftsPhotography",
        "title": "Nghệ Thuật & Sáng Tạo",
        "base": "giai-tri.html",
        "subnav": ["Mỹ thuật", "Nhiếp ảnh", "Thủ công", "Thiết kế", "Biểu diễn"],
        "subjects": ["nghệ thuật đương đại", "nhiếp ảnh", "thủ công sáng tạo", "thiết kế", "nghệ thuật biểu diễn"],
    },
    {
        "slug": "food-dining",
        "file": "am-thuc-nha-hang.html",
        "code": "FoodDining",
        "title": "Ẩm Thực & Nhà Hàng",
        "base": "doi-song.html",
        "subnav": ["Món Việt", "Nhà hàng", "Cà phê", "Nấu ăn", "Ẩm thực quốc tế"],
        "subjects": ["ẩm thực Việt", "nhà hàng", "cà phê", "công thức nấu ăn", "xu hướng ăn uống"],
    },
    {
        "slug": "fashion-beauty",
        "file": "thoi-trang-lam-dep.html",
        "code": "FashionBeauty",
        "title": "Thời Trang & Làm Đẹp",
        "base": "doi-song.html",
        "subnav": ["Thời trang", "Mỹ phẩm", "Chăm sóc tóc", "Phụ kiện", "Phong cách"],
        "subjects": ["thời trang Việt", "chăm sóc sắc đẹp", "mỹ phẩm", "phụ kiện", "phong cách cá nhân"],
    },
    {
        "slug": "shopping-ecommerce",
        "file": "mua-sam-thuong-mai-dien-tu.html",
        "code": "ShoppingEcommerce",
        "title": "Mua Sắm & Thương Mại Điện Tử",
        "base": "doi-song.html",
        "subnav": ["Mua sắm online", "Khuyến mại", "Đồ gia dụng", "Đồ chơi", "Tiêu dùng thông minh"],
        "subjects": ["mua sắm trực tuyến", "thương mại điện tử", "khuyến mại", "tiêu dùng thông minh", "bán lẻ"],
    },
    {
        "slug": "home-garden-diy",
        "file": "nha-vuon-diy.html",
        "code": "HomeGardenDiy",
        "title": "Nhà Vườn & DIY",
        "base": "doi-song.html",
        "subnav": ["Làm vườn", "DIY", "Nội thất", "Gia dụng", "Cải tạo nhà"],
        "subjects": ["làm vườn tại nhà", "đồ thủ công DIY", "cải tạo nhà", "nội thất", "thiết bị gia dụng"],
    },
    {
        "slug": "pets-animals",
        "file": "thu-cung-dong-vat.html",
        "code": "PetsAnimals",
        "title": "Thú Cưng & Động Vật",
        "base": "doi-song.html",
        "subnav": ["Chó mèo", "Chăm sóc", "Dinh dưỡng", "Thú y", "Động vật"],
        "subjects": ["chăm sóc thú cưng", "dinh dưỡng vật nuôi", "thú y", "cộng đồng yêu động vật", "đời sống thú cưng"],
    },
]

HEADLINE_PATTERNS = [
    "{subject}: Những thay đổi đáng chú ý trong tuần",
    "Người Việt đang quan tâm điều gì về {subject}?",
    "Ba xu hướng mới định hình trải nghiệm {subject}",
    "Góc dữ liệu: Nhu cầu {subject} thay đổi ra sao",
    "Chuyên gia giải thích những điều cần biết về {subject}",
    "Cộng đồng tìm thấy giá trị mới từ {subject}",
    "Công nghệ đang làm mới lĩnh vực {subject}",
    "Hướng dẫn thực tế để lựa chọn giải pháp {subject}",
    "Những sáng kiến Việt tạo dấu ấn trong {subject}",
    "Thị trường {subject} bước vào giai đoạn mới",
    "Câu chuyện phía sau một trải nghiệm {subject}",
    "Năm lưu ý giúp người dùng tiếp cận {subject} hiệu quả",
    "Xu hướng bền vững đang lan rộng trong {subject}",
    "Doanh nghiệp Việt đầu tư nhiều hơn cho {subject}",
    "Thế hệ trẻ định nghĩa lại trải nghiệm {subject}",
    "Những con số đáng chú ý của lĩnh vực {subject}",
    "Khi cộng đồng cùng xây dựng hệ sinh thái {subject}",
    "Điều gì tạo nên một lựa chọn {subject} đáng tin cậy?",
    "Các mô hình mới đang mở rộng cơ hội trong {subject}",
    "Kinh nghiệm hữu ích trước khi bắt đầu với {subject}",
    "Từ ý tưởng đến trải nghiệm thực tế trong {subject}",
    "Người dùng ưu tiên chất lượng khi chọn {subject}",
    "Những câu hỏi thường gặp nhất về {subject}",
    "Bức tranh {subject} qua góc nhìn chuyên gia",
    "Đổi mới sáng tạo thúc đẩy lĩnh vực {subject}",
    "Các thương hiệu thích ứng với nhu cầu {subject}",
    "Một ngày trải nghiệm xu hướng {subject} mới",
    "Giải pháp đơn giản giúp tiếp cận {subject} tốt hơn",
    "Cơ hội phát triển dành cho cộng đồng {subject}",
    "Tương lai của {subject} sẽ thay đổi thế nào?",
    "Những lựa chọn được người dùng đánh giá cao",
    "Câu chuyện địa phương tạo cảm hứng về {subject}",
    "Kết nối trực tuyến mở rộng cộng đồng {subject}",
    "Chất lượng và an toàn trở thành ưu tiên hàng đầu",
    "Toàn cảnh lĩnh vực {subject} trong tháng này",
]


def article(topic: dict, index: int, *, eager: bool = False) -> str:
    subject = topic["subjects"][index % len(topic["subjects"])]
    title = HEADLINE_PATTERNS[index].format(subject=subject)
    image = f"{ASSET_ROOT}/{topic['slug']}-{index % 6 + 1:02}.jpg"
    summary = (
        f"Bài viết mô phỏng được biên soạn riêng cho chủ đề {topic['title']}. "
        "Nội dung dùng để kiểm thử độ phù hợp của ngữ cảnh, hình ảnh và vị trí quảng cáo."
    )
    loading = "" if eager else ' loading="lazy"'
    return f"""
<article article-id="np6-{topic['slug']}-{index + 1:02}" class="article-item type-text np6-synthetic-story">
  <p class="article-thumbnail"><a href="#np6-{index + 1}">
    <img src="{html.escape(image)}" alt="{html.escape(title)}"{loading}>
  </a></p>
  <header>
    <h3 class="article-title"><a href="#np6-{index + 1}">{html.escape(title)}</a></h3>
    <p class="article-meta"><span class="article-publish"><span class="friendly-time">{index + 1} giờ trước</span></span></p>
    <p class="article-summary">{html.escape(summary)}</p>
  </header>
</article>"""


def build_content(topic: dict) -> str:
    nav = " &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; ".join(html.escape(item) for item in topic["subnav"])
    lead = article(topic, 0, eager=True)
    lead_side = "".join(article(topic, index, eager=True) for index in range(1, 5))
    highlights = "".join(
        f"<div class='grid-item'>{article(topic, index, eager=True)}</div>"
        for index in range(5, 9)
    )
    columns = "".join(
        f"<div class='grid-item cat-col'><h3 class='cat-col-title'>{html.escape(topic['subnav'][i])}</h3>{article(topic, 9 + i)}</div>"
        for i in range(4)
    )
    listing = "".join(article(topic, index) for index in range(13, 35))
    return f"""
<div class="center-wrapper">
<div class="page-wrapper category-page np6-topic-page" data-topic="{html.escape(topic['slug'])}">
  <div class="category-header-mock">
    <h1>{html.escape(topic['title'])}</h1>
    <div class="np6-subnav">{nav}</div>
  </div>

  <div class="category-full-width lead-block">
    <div class="featured-lead">{lead}</div>
    <div class="featured-sub-list">{lead_side}</div>
  </div>

  <div class="category-full-width noi-bat-block">
    <h2 class="block-title">Nổi bật</h2>
    <div class="grid-4-col">{highlights}</div>
  </div>

  <div class="category-full-width np6-category-columns">
    <div class="grid-4-col">{columns}</div>
  </div>

  <div class="container layout-two-col">
    <main class="main-content">
      <h2 class="block-title">Tin mới</h2>
      <div class="article-list">{listing}</div>
    </main>
    <aside class="sidebar">
      <div class="sidebar-ad-wrapper">
        <div id="Znews_{topic['code']}_SidebarBox" class="ad-container ad-sidebar-box"
             data-zone="Znews_{topic['code']}_SidebarBox"></div>
      </div>
    </aside>
  </div>
</div>
</div>
"""


def build_page(topic: dict) -> str:
    base = (ROOT / topic["base"]).read_text(encoding="utf-8")
    prefix, remainder = base.split('<div class="center-wrapper">', 1)
    _, footer_tail = remainder.split('<footer id="footer">', 1)
    footer = '<footer id="footer">' + footer_tail

    match = re.search(r'Znews_([A-Za-z]+)_Background', prefix)
    if not match:
        raise RuntimeError(f"Cannot find source zone prefix in {topic['base']}")
    source_code = match.group(1)
    prefix = prefix.replace(f"Znews_{source_code}_", f"Znews_{topic['code']}_")
    prefix = re.sub(
        r'<script[^>]+src="[^"]*zplayer-autoplay-countdown-plugin[^"]*"[^>]*>\s*</script>',
        "",
        prefix,
    )
    prefix = re.sub(
        r'<link[^>]+href="[^"]*zplayer-autoplay-countdown-plugin[^"]*"[^>]*>',
        "",
        prefix,
    )
    prefix = re.sub(
        r'<script type="text/javascript"\s*>\s*var disableVideoAds.*?</script>',
        "",
        prefix,
        flags=re.S,
    )
    prefix = re.sub(
        r'<div[^>]+class="ad-container np6-topic-masthead"[^>]*>\s*</div>\s*',
        "",
        prefix,
        count=1,
    )
    prefix = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(topic['title'])} | ZNews NP-6</title>",
        prefix,
        count=1,
        flags=re.S,
    )
    prefix = re.sub(
        r'href="category-style\.css(?:\?[^"]*)?"',
        'href="category-style.css?v=np6-2026-02-menu-1"',
        prefix,
    )
    masthead = f"""
<div id="Znews_{topic['code']}_Masthead" class="ad-container np6-topic-masthead"
     data-zone="Znews_{topic['code']}_Masthead" aria-label="Top banner ad"></div>
"""
    prefix = prefix.replace("<!-- SKIN AD CONTAINER -->", masthead + "\n<!-- SKIN AD CONTAINER -->", 1)
    footer = re.sub(
        r'<script src="np6-topic-page\.js[^"]*"></script>\s*',
        "",
        footer,
    )
    footer = re.sub(
        r'<script>\s*!function\(t\).*?window\.on\("DOMContentLoaded".*?</script>',
        "",
        footer,
        flags=re.S,
    )
    footer = re.sub(
        r'src="api\.js(?:\?[^"]*)?"',
        'src="api.js?v=np6-2026-02-4"',
        footer,
    )
    footer = re.sub(
        r'src="app\.js(?:\?[^"]*)?"',
        'src="app.js?v=np6-2026-02-4"',
        footer,
    )
    footer = footer.replace(
        "</body>",
        '<script src="np6-topic-page.js?v=np6-2026-02-menu-2"></script>\n</body>',
        1,
    )
    return prefix + build_content(topic) + footer


def main() -> None:
    for topic in TOPICS:
        output = ROOT / topic["file"]
        output.write_text(build_page(topic), encoding="utf-8", newline="\n")
        print(f"{output.name}: {topic['code']} (35 synthetic stories)")


if __name__ == "__main__":
    main()
