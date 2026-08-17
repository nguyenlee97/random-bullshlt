const TOPICS = [
  ['business-finance','BusinessFinance','Kinh doanh & Tài chính','Thông tin thị trường, doanh nghiệp, đầu tư và tài chính cá nhân.'],
  ['health-wellness','HealthWellness','Sức khỏe & Wellness','Kiến thức chăm sóc sức khỏe, dinh dưỡng và lối sống cân bằng.'],
  ['sports-outdoors','SportsOutdoors','Thể thao & Ngoài trời','Tin tức thể thao, vận động ngoài trời và cộng đồng người hâm mộ.'],
  ['technology-science','TechnologyScience','Công nghệ & Khoa học','Xu hướng công nghệ, sản phẩm số và những khám phá khoa học mới.'],
  ['family-parenting','FamilyParenting','Gia đình & Nuôi dạy con','Gợi ý thiết thực để cha mẹ đồng hành cùng con và vun đắp gia đình.'],
  ['education-careers','EducationCareers','Giáo dục & Nghề nghiệp','Cơ hội học tập, phát triển kỹ năng và định hướng nghề nghiệp.'],
  ['travel-hospitality','TravelHospitality','Du lịch & Lưu trú','Điểm đến, trải nghiệm nghỉ dưỡng và xu hướng du lịch mới.'],
  ['automotive-mobility','AutomotiveMobility','Ô tô, Xe máy & Di chuyển','Thị trường xe, công nghệ an toàn và giải pháp di chuyển hiện đại.'],
  ['home-property-architecture','HomePropertyArchitecture','Nhà ở, BĐS & Kiến trúc','Không gian sống, kiến trúc, quy hoạch và thị trường bất động sản.'],
  ['society-news-law','SocietyNewsLaw','Xã hội, Thời sự & Pháp luật','Những câu chuyện xã hội, chính sách và pháp luật gần với đời sống.'],
  ['marketing-digital-business','MarketingDigitalBusiness','Marketing & Kinh doanh số','Thương mại điện tử, quảng cáo, khởi nghiệp và chuyển đổi số.'],
  ['fitness-active-living','FitnessActiveLiving','Fitness & Sống khỏe','Tập luyện, phục hồi vận động và xây dựng lối sống năng động.'],
  ['soccer-fandom','SoccerFandom','Bóng đá & Người hâm mộ','Bóng đá Việt Nam, giải đấu quốc tế và cộng đồng người hâm mộ.'],
  ['gaming-esports','GamingEsports','Game & Esports','Game mobile, esports, thiết bị và những giải đấu điện tử đáng chú ý.'],
  ['movies-tv-streaming','MoviesTvStreaming','Phim, Truyền hình & Streaming','Phim mới, nền tảng trực tuyến và câu chuyện phía sau màn ảnh.'],
  ['music-live-events','MusicLiveEvents','Âm nhạc & Sự kiện','Concert, lễ hội âm nhạc, nghệ sĩ trẻ và sân khấu trực tiếp.'],
  ['books-reading','BooksReading','Sách & Văn hóa đọc','Sách mới, văn học, xuất bản số và cảm hứng đọc mỗi ngày.'],
  ['arts-crafts-photography','ArtsCraftsPhotography','Nghệ thuật, Sáng tạo & Nhiếp ảnh','Nghệ thuật đương đại, thiết kế, nhiếp ảnh và thủ công sáng tạo.'],
  ['food-dining','FoodDining','Ẩm thực, Nấu ăn & Nhà hàng','Hương vị Việt, địa chỉ ăn uống và những xu hướng ẩm thực mới.'],
  ['fashion-beauty','FashionBeauty','Thời trang & Làm đẹp','Phong cách cá nhân, mỹ phẩm và câu chuyện của thời trang Việt.'],
  ['shopping-ecommerce','ShoppingEcommerce','Mua sắm & Thương mại điện tử','Mua sắm thông minh, bán lẻ và những thay đổi của thị trường số.'],
  ['home-garden-diy','HomeGardenDiy','Nhà, Vườn & DIY','Cải tạo nhà, làm vườn, nội thất và ý tưởng tự làm hữu ích.'],
  ['pets-animals','PetsAnimals','Thú cưng & Động vật','Chăm sóc, dinh dưỡng và đời sống cộng đồng yêu động vật.'],
];

const SUBJECTS = {
  'business-finance': ['thị trường tài chính', 'doanh nghiệp Việt', 'đầu tư bền vững', 'tài chính cá nhân', 'kinh tế số'],
  'health-wellness': ['dinh dưỡng khoa học', 'sức khỏe tinh thần', 'y tế dự phòng', 'chăm sóc gia đình', 'lối sống cân bằng'],
  'sports-outdoors': ['thể thao Việt Nam', 'chạy bộ', 'hoạt động ngoài trời', 'giải đấu phong trào', 'rèn luyện sức bền'],
  'technology-science': ['trí tuệ nhân tạo', 'thiết bị thông minh', 'khoa học ứng dụng', 'an toàn số', 'đổi mới công nghệ'],
  'family-parenting': ['nuôi dạy con', 'sức khỏe trẻ nhỏ', 'kết nối gia đình', 'dinh dưỡng cho bé', 'kỹ năng làm cha mẹ'],
  'education-careers': ['kỹ năng nghề nghiệp', 'giáo dục hiện đại', 'học tập suốt đời', 'cơ hội việc làm', 'đào tạo số'],
  'travel-hospitality': ['du lịch Việt Nam', 'trải nghiệm nghỉ dưỡng', 'hàng không', 'khách sạn xanh', 'điểm đến mới'],
  'automotive-mobility': ['xe điện', 'ô tô gia đình', 'công nghệ an toàn', 'hạ tầng sạc', 'thị trường xe'],
  'home-property-architecture': ['nhà ở đô thị', 'kiến trúc bền vững', 'thị trường bất động sản', 'không gian sống', 'quy hoạch'],
  'society-news-law': ['chính sách gần cuộc sống', 'an toàn cộng đồng', 'pháp luật dân sinh', 'giao thông đô thị', 'hoạt động xã hội'],
  'marketing-digital-business': ['marketing số', 'thương mại điện tử', 'khởi nghiệp', 'quảng cáo trực tuyến', 'doanh nghiệp nhỏ'],
  'fitness-active-living': ['tập luyện thể chất', 'chạy bộ', 'yoga', 'rèn luyện sức bền', 'phục hồi vận động'],
  'soccer-fandom': ['bóng đá Việt Nam', 'giải đấu quốc tế', 'cộng đồng người hâm mộ', 'chiến thuật bóng đá', 'cầu thủ trẻ'],
  'gaming-esports': ['esports', 'game mobile', 'cộng đồng game thủ', 'thiết bị chơi game', 'giải đấu điện tử'],
  'movies-tv-streaming': ['điện ảnh Việt', 'nền tảng streaming', 'sản xuất truyền hình', 'phim tài liệu', 'hậu trường phim'],
  'music-live-events': ['âm nhạc Việt', 'concert', 'lễ hội âm nhạc', 'nghệ sĩ trẻ', 'sân khấu trực tiếp'],
  'books-reading': ['văn hóa đọc', 'sách mới', 'văn học Việt', 'thư viện cộng đồng', 'xuất bản số'],
  'arts-crafts-photography': ['nghệ thuật đương đại', 'nhiếp ảnh', 'thủ công sáng tạo', 'thiết kế', 'nghệ thuật biểu diễn'],
  'food-dining': ['ẩm thực Việt', 'nhà hàng', 'cà phê', 'công thức nấu ăn', 'xu hướng ăn uống'],
  'fashion-beauty': ['thời trang Việt', 'chăm sóc sắc đẹp', 'mỹ phẩm', 'phụ kiện', 'phong cách cá nhân'],
  'shopping-ecommerce': ['mua sắm trực tuyến', 'thương mại điện tử', 'khuyến mại', 'tiêu dùng thông minh', 'bán lẻ'],
  'home-garden-diy': ['làm vườn tại nhà', 'đồ thủ công DIY', 'cải tạo nhà', 'nội thất', 'thiết bị gia dụng'],
  'pets-animals': ['chăm sóc thú cưng', 'dinh dưỡng vật nuôi', 'thú y', 'cộng đồng yêu động vật', 'đời sống thú cưng'],
};

const SOURCES = ['ZNews', 'VietnamNet', 'VTC News', 'Tuổi Trẻ', 'Thanh Niên', 'Tạp chí Tri thức'];
const TITLE_PATTERNS = [
  '{subject} đang tạo ra thay đổi đáng chú ý trong năm nay',
  'Những câu chuyện mới nhất được quan tâm về {subject}',
  'Người Việt thay đổi cách tiếp cận {subject} như thế nào?',
  '5 xu hướng của {subject} không nên bỏ lỡ',
  'Chuyên gia nói gì về bước tiến mới của {subject}?',
  '{subject}: Từ lựa chọn mới đến thói quen hàng ngày',
  'Cộng đồng chia sẻ trải nghiệm thực tế về {subject}',
  'Góc nhìn mới giúp hiểu đúng hơn về {subject}',
  'Các sáng kiến Việt tạo dấu ấn trong lĩnh vực {subject}',
  'Điều gì khiến {subject} được chú ý lúc này?',
];

function topicFromQuery() {
  const slug = new URLSearchParams(location.search).get('topic');
  return TOPICS.find((topic) => topic[0] === slug) || TOPICS[0];
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
  }[character]));
}

function makeStories(topic) {
  const [slug, , title] = topic;
  const subjects = SUBJECTS[slug];
  return TITLE_PATTERNS.map((pattern, index) => {
    const subject = subjects[index % subjects.length];
    return {
      title: pattern.replace('{subject}', subject[0].toUpperCase() + subject.slice(1)),
      description: `${title} ghi nhận nhiều chuyển động mới quanh ${subject}. Những dữ liệu, trải nghiệm và góc nhìn thực tế giúp độc giả hiểu rõ hơn câu chuyện đang diễn ra.`,
      image: `https://znews-stg.pawgrammers.io.vn/assets/np6-topics/${slug}-${String((index % 6) + 1).padStart(2, '0')}.jpg`,
      source: SOURCES[index % SOURCES.length],
      time: index < 2 ? `${index + 18} phút` : `${index} giờ`,
      related: 6 + ((index * 7) % 38),
    };
  });
}

function meta(story) {
  return `<div class="story-meta"><strong>${escapeHtml(story.source)}</strong><span>${story.time}</span><span class="related">● ${story.related} liên quan</span></div>`;
}

function renderLead(stories) {
  const lead = stories[0];
  return `
    <article class="lead-main">
      <div class="lead-copy">
        ${meta(lead)}
        <h2>${escapeHtml(lead.title)}</h2>
        <p>${escapeHtml(lead.description)}</p>
      </div>
      <img src="${lead.image}" alt="${escapeHtml(lead.title)}">
    </article>
    <div class="lead-side">
      ${stories.slice(1, 4).map((story) => `
        <article>
          <img src="${story.image}" alt="${escapeHtml(story.title)}">
          <div>${meta(story)}<h3>${escapeHtml(story.title)}</h3></div>
        </article>`).join('')}
    </div>`;
}

function renderArticles(stories) {
  return stories.slice(4).map((story) => `
    <article>
      <img src="${story.image}" alt="${escapeHtml(story.title)}" loading="lazy">
      <div class="article-copy">
        ${meta(story)}
        <h3>${escapeHtml(story.title)}</h3>
        <p>${escapeHtml(story.description)}</p>
      </div>
    </article>`).join('');
}

function render() {
  const topic = topicFromQuery();
  const [slug, code, title, description] = topic;
  const stories = makeStories(topic);
  const prefix = `BaoMoi_${code}`;

  document.title = `${title} - Báo Mới`;
  document.getElementById('topic-title').textContent = title;
  document.getElementById('topic-description').textContent = description;
  document.getElementById('topic-subnav').innerHTML = SUBJECTS[slug]
    .map((subject) => `<a href="#latest"># ${escapeHtml(subject)}</a>`).join('');
  document.getElementById('lead-grid').innerHTML = renderLead(stories);
  document.getElementById('article-list').innerHTML = renderArticles(stories);
  document.getElementById('popular-list').innerHTML = stories.slice(0, 6)
    .map((story) => `<li><a href="#latest">${escapeHtml(story.title)}<small>${story.source} · ${story.time}</small></a></li>`)
    .join('');

  mountCategoryAds(prefix);
}

async function mountCategoryAds(prefix) {
  const backgroundPromise = mountAd(
    `${prefix}_Background`,
    'category-background',
    { deferRender: true },
  );
  const mastheadPromise = mountAd(
    `${prefix}_Masthead`,
    'category-masthead',
    { deferRender: true },
  );

  mountAd(`${prefix}_SideLeft`, 'category-side-left');
  mountAd(`${prefix}_SideRight`, 'category-side-right');
  mountAd(`${prefix}_SidebarBox`, 'category-sidebar');

  const [background, masthead] = await Promise.all([
    backgroundPromise,
    mastheadPromise,
  ]);
  const backgroundElement = document.getElementById('category-background');
  const mastheadElement = document.getElementById('category-masthead');
  const hasBackground = Boolean(background?.hasAd && background.html);
  const hasMasthead = Boolean(masthead?.hasAd && masthead.html);
  const backgroundIsLive = hasBackground && background.isFallback !== true;
  const mastheadIsLive = hasMasthead && masthead.isFallback !== true;
  const showBackground = hasBackground && (backgroundIsLive || !mastheadIsLive);

  if (showBackground) {
    renderAdResult(backgroundElement, background);
    clearAdMount(mastheadElement);
    if (background.imageUrl && document.body?.classList) {
      document.body.classList.add('has-bg-ad');
      document.body.style.backgroundImage = `url("${background.imageUrl}")`;
    }
    return;
  }

  clearAdMount(backgroundElement);
  if (document.body?.classList) {
    document.body.classList.remove('has-bg-ad');
    document.body.style.backgroundImage = '';
  }
  if (hasMasthead) {
    renderAdResult(mastheadElement, masthead);
  } else {
    clearAdMount(mastheadElement);
  }
}

function clearAdMount(element) {
  if (element) element.innerHTML = '';
}

function renderAdResult(element, result) {
  if (!element || !result?.hasAd || !result.html) return;
  element.innerHTML = result.html;
  if (element.classList?.add) element.classList.add('loaded');
  const closeButton = typeof element.querySelector === 'function'
    ? element.querySelector('.ad-close-btn')
    : null;
  if (closeButton?.addEventListener) {
    closeButton.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      clearAdMount(element);
    });
  }
}

async function mountAd(zoneId, elementId, { deferRender = false } = {}) {
  const element = document.getElementById(elementId);
  element.dataset.zone = zoneId;
  if (typeof fetchAdForZone !== 'function') return null;
  const result = await fetchAdForZone(zoneId);
  if (!deferRender) renderAdResult(element, result);
  return result;
}

document.addEventListener('DOMContentLoaded', render);
