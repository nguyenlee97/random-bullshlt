const NP6_CATALOG_VERSION = 'np6-2026-03';
const NP6_TAXONOMY_VERSION = 'placement-topics-v2';

const BASE_TOPICS = [
  {
    id: 'business_finance',
    code: 'BusinessFinance',
    slug: 'business-finance',
    label: 'Business & Finance',
    labelVi: 'Kinh doanh & Tài chính',
    znewsChannel: 'znews-kinh-doanh',
    keywordsVi: ['kinh doanh', 'tài chính', 'ngân hàng', 'đầu tư', 'doanh nghiệp', 'việc làm'],
    keywordsEn: ['business', 'finance', 'banking', 'investment', 'enterprise', 'careers'],
    dmpCategories: ['Business and industry'],
    secondaryTopics: ['education_careers', 'home_property_architecture'],
  },
  {
    id: 'health_wellness',
    code: 'HealthWellness',
    slug: 'health-wellness',
    label: 'Health & Wellness',
    labelVi: 'Sức khỏe & Đời sống lành mạnh',
    znewsChannel: 'znews-suc-khoe',
    keywordsVi: ['sức khỏe', 'chăm sóc', 'dinh dưỡng', 'thể chất', 'bảo hiểm sức khỏe'],
    keywordsEn: ['health', 'wellness', 'care', 'nutrition', 'fitness', 'health insurance'],
    dmpCategories: ['Fitness and wellness (fitness)', 'Food and drink (consumables)'],
    secondaryTopics: ['family_parenting', 'sports_outdoors'],
  },
  {
    id: 'sports_outdoors',
    code: 'SportsOutdoors',
    slug: 'sports-outdoors',
    label: 'Sports & Outdoors',
    labelVi: 'Thể thao & Ngoài trời',
    znewsChannel: 'znews-the-thao',
    keywordsVi: ['thể thao', 'bóng đá', 'tập luyện', 'ngoài trời', 'người hâm mộ'],
    keywordsEn: ['sports', 'football', 'soccer', 'fitness', 'outdoors', 'fans'],
    dmpCategories: ['Sports and outdoors', 'Soccer', 'Fitness and wellness (fitness)'],
    secondaryTopics: ['health_wellness', 'travel_hospitality'],
  },
  {
    id: 'technology_science',
    code: 'TechnologyScience',
    slug: 'technology-science',
    label: 'Technology & Science',
    labelVi: 'Công nghệ & Khoa học',
    znewsChannel: 'znews-cong-nghe',
    keywordsVi: ['công nghệ', 'thiết bị', 'phần mềm', 'AI', 'viễn thông', 'khoa học'],
    keywordsEn: ['technology', 'devices', 'software', 'AI', 'telecom', 'science'],
    dmpCategories: ['Technology (computers & electronics)', 'Digital Activities'],
    secondaryTopics: ['business_finance', 'education_careers'],
  },
  {
    id: 'entertainment_culture',
    code: 'EntertainmentCulture',
    slug: 'entertainment-culture',
    label: 'Entertainment & Culture',
    labelVi: 'Giải trí & Văn hóa',
    znewsChannel: 'znews-giai-tri',
    keywordsVi: ['giải trí', 'âm nhạc', 'điện ảnh', 'truyền hình', 'nghệ thuật', 'sự kiện'],
    keywordsEn: ['entertainment', 'music', 'film', 'television', 'arts', 'events'],
    dmpCategories: ['Entertainment (leisure)', 'Hobbies and activities'],
    secondaryTopics: ['lifestyle_food_shopping', 'travel_hospitality'],
  },
  {
    id: 'lifestyle_food_shopping',
    code: 'LifestyleFoodShopping',
    slug: 'lifestyle-food-shopping',
    label: 'Lifestyle, Food & Shopping',
    labelVi: 'Đời sống, Ẩm thực & Mua sắm',
    znewsChannel: 'znews-doi-song',
    keywordsVi: ['đời sống', 'ẩm thực', 'đồ uống', 'thời trang', 'làm đẹp', 'mua sắm'],
    keywordsEn: ['lifestyle', 'food', 'drink', 'fashion', 'beauty', 'shopping'],
    dmpCategories: ['Food and drink (consumables)', 'Shopping and fashion', 'Hobbies and activities'],
    secondaryTopics: ['family_parenting', 'entertainment_culture'],
  },
  {
    id: 'family_parenting',
    code: 'FamilyParenting',
    slug: 'family-parenting',
    label: 'Family & Parenting',
    labelVi: 'Gia đình & Nuôi dạy con',
    znewsChannel: 'znews-family-parenting',
    keywordsVi: ['gia đình', 'cha mẹ', 'trẻ em', 'mẹ và bé', 'chăm sóc gia đình'],
    keywordsEn: ['family', 'parenting', 'children', 'mother and baby', 'household care'],
    dmpCategories: ['Family and relationships'],
    secondaryTopics: ['health_wellness', 'education_careers'],
    exclusions: ['infer_personal_parental_status'],
  },
  {
    id: 'education_careers',
    code: 'EducationCareers',
    slug: 'education-careers',
    label: 'Education & Careers',
    labelVi: 'Giáo dục & Nghề nghiệp',
    znewsChannel: 'znews-education-careers',
    keywordsVi: ['giáo dục', 'học tập', 'trường học', 'khóa học', 'du học', 'tuyển dụng'],
    keywordsEn: ['education', 'learning', 'schools', 'courses', 'study abroad', 'recruitment', 'skills', 'career development'],
    dmpCategories: ['Business and industry'],
    secondaryTopics: ['business_finance', 'family_parenting'],
  },
  {
    id: 'travel_hospitality',
    code: 'TravelHospitality',
    slug: 'travel-hospitality',
    label: 'Travel & Hospitality',
    labelVi: 'Du lịch & Dịch vụ lưu trú',
    znewsChannel: 'znews-travel-hospitality',
    keywordsVi: ['du lịch', 'điểm đến', 'hàng không', 'khách sạn', 'nghỉ dưỡng'],
    keywordsEn: ['travel', 'destinations', 'airlines', 'hotels', 'hospitality'],
    dmpCategories: ['Travel', 'Hobbies and activities'],
    secondaryTopics: ['lifestyle_food_shopping', 'entertainment_culture'],
  },
  {
    id: 'automotive_mobility',
    code: 'AutomotiveMobility',
    slug: 'automotive-mobility',
    label: 'Automotive & Mobility',
    labelVi: 'Ô tô, Xe máy & Di chuyển',
    znewsChannel: 'znews-automotive-mobility',
    keywordsVi: ['ô tô', 'xe máy', 'xe điện', 'di chuyển', 'phụ kiện xe', 'vay mua xe'],
    keywordsEn: ['automotive', 'cars', 'motorcycles', 'EVs', 'mobility', 'vehicle finance'],
    dmpCategories: ['Hobbies and activities', 'Purchase behavior (Purchase behavior)'],
    secondaryTopics: ['technology_science', 'business_finance'],
  },
  {
    id: 'home_property_architecture',
    code: 'HomePropertyArchitecture',
    slug: 'home-property-architecture',
    label: 'Home, Property & Architecture',
    labelVi: 'Nhà ở, Bất động sản & Kiến trúc',
    znewsChannel: 'znews-home-property-architecture',
    keywordsVi: ['nhà ở', 'bất động sản', 'xây dựng', 'nội thất', 'kiến trúc'],
    keywordsEn: ['home', 'property', 'real estate', 'construction', 'interiors', 'architecture'],
    dmpCategories: ['Business and industry', 'Hobbies and activities'],
    secondaryTopics: ['business_finance', 'lifestyle_food_shopping'],
  },
  {
    id: 'society_news_law',
    code: 'SocietyNewsLaw',
    slug: 'society-news-law',
    label: 'Society, News & Law',
    labelVi: 'Xã hội, Thời sự & Pháp luật',
    znewsChannel: 'znews-society-news-law',
    keywordsVi: ['xã hội', 'thời sự', 'pháp luật', 'an toàn', 'giao thông', 'môi trường'],
    keywordsEn: ['society', 'news', 'law', 'safety', 'transport policy', 'environment'],
    dmpCategories: ['Business and industry', 'Expats'],
    secondaryTopics: ['business_finance', 'automotive_mobility'],
  },
];

const ZNEWS_PATHS = {
  business_finance: '/kinh-doanh.html',
  health_wellness: '/suc-khoe.html',
  sports_outdoors: '/the-thao.html',
  technology_science: '/cong-nghe.html',
  entertainment_culture: '/giai-tri.html',
  lifestyle_food_shopping: '/doi-song.html',
  family_parenting: '/gia-dinh.html',
  education_careers: '/giao-duc-nghe-nghiep.html',
  travel_hospitality: '/du-lich-luu-tru.html',
  automotive_mobility: '/xe-di-chuyen.html',
  home_property_architecture: '/nha-o-bat-dong-san.html',
  society_news_law: '/xa-hoi-phap-luat.html',
  marketing_digital_business: '/marketing-kinh-doanh-so.html',
  fitness_active_living: '/fitness-song-khoe.html',
  soccer_fandom: '/bong-da.html',
  gaming_esports: '/game-esports.html',
  movies_tv_streaming: '/phim-truyen-hinh.html',
  music_live_events: '/am-nhac-su-kien.html',
  books_reading: '/sach-va-doc.html',
  arts_crafts_photography: '/nghe-thuat-sang-tao.html',
  food_dining: '/am-thuc-nha-hang.html',
  fashion_beauty: '/thoi-trang-lam-dep.html',
  shopping_ecommerce: '/mua-sam-thuong-mai-dien-tu.html',
  home_garden_diy: '/nha-vuon-diy.html',
  pets_animals: '/thu-cung-dong-vat.html',
};

const RETIRED_TOPIC_IDS = new Set([
  'entertainment_culture',
  'lifestyle_food_shopping',
]);

const REFINED_TOPICS = [
  {
    id: 'marketing_digital_business',
    code: 'MarketingDigitalBusiness',
    slug: 'marketing-digital-business',
    label: 'Marketing & Digital Business',
    labelVi: 'Marketing & Kinh doanh số',
    znewsChannel: 'znews-marketing-digital-business',
    keywordsVi: ['marketing', 'quảng cáo', 'thương mại điện tử', 'kinh doanh số', 'truyền thông'],
    keywordsEn: ['marketing', 'advertising', 'digital business', 'entrepreneurship', 'ecommerce'],
    dmpCategories: ['Business and industry', 'Digital Activities'],
    dmpSubcategories: ['Advertising', 'Marketing', 'Entrepreneurship'],
    dmpSegments: ['Digital marketing', 'Advertising', 'Small business'],
    secondaryTopics: ['business_finance', 'technology_science', 'shopping_ecommerce'],
  },
  {
    id: 'fitness_active_living',
    code: 'FitnessActiveLiving',
    slug: 'fitness-active-living',
    label: 'Fitness & Active Living',
    labelVi: 'Fitness & Sống khỏe',
    znewsChannel: 'znews-fitness-active-living',
    keywordsVi: ['fitness', 'gym', 'chạy bộ', 'yoga', 'tập luyện', 'sống khỏe'],
    keywordsEn: ['fitness', 'gym', 'running', 'yoga', 'workouts', 'active lifestyle'],
    dmpCategories: ['Fitness and wellness (fitness)', 'Sports and outdoors'],
    dmpSubcategories: ['Physical exercise', 'Running', 'Yoga'],
    dmpSegments: ['Fitness and wellness', 'Gyms', 'Running'],
    secondaryTopics: ['health_wellness', 'sports_outdoors'],
  },
  {
    id: 'soccer_fandom',
    code: 'SoccerFandom',
    slug: 'soccer-fandom',
    label: 'Football & Soccer Fandom',
    labelVi: 'Bóng đá & Người hâm mộ',
    znewsChannel: 'znews-soccer-fandom',
    keywordsVi: ['bóng đá', 'cầu thủ', 'câu lạc bộ', 'giải đấu', 'người hâm mộ'],
    keywordsEn: ['football', 'soccer', 'players', 'clubs', 'leagues', 'fans'],
    dmpCategories: ['Soccer', 'Sports and outdoors'],
    dmpSubcategories: ['Soccer fans', 'Football clubs', 'Football competitions'],
    dmpSegments: ['Association football', 'Premier League', 'Football fans'],
    secondaryTopics: ['sports_outdoors', 'fitness_active_living'],
  },
  {
    id: 'gaming_esports',
    code: 'GamingEsports',
    slug: 'gaming-esports',
    label: 'Gaming & Esports',
    labelVi: 'Game & Esports',
    znewsChannel: 'znews-gaming-esports',
    keywordsVi: ['trò chơi', 'game', 'esports', 'game mobile', 'thi đấu điện tử'],
    keywordsEn: ['gaming', 'video games', 'mobile games', 'esports', 'game streaming'],
    dmpCategories: ['Entertainment (leisure)', 'Digital Activities'],
    dmpSubcategories: ['Games', 'Video games', 'Online games'],
    dmpSegments: ['Video games', 'Mobile games', 'Esports'],
    secondaryTopics: ['technology_science', 'movies_tv_streaming'],
  },
  {
    id: 'movies_tv_streaming',
    code: 'MoviesTvStreaming',
    slug: 'movies-tv-streaming',
    label: 'Movies, TV & Streaming',
    labelVi: 'Phim, Truyền hình & Streaming',
    znewsChannel: 'znews-movies-tv-streaming',
    keywordsVi: ['phim ảnh', 'điện ảnh', 'truyền hình', 'streaming', 'diễn viên'],
    keywordsEn: ['movies', 'cinema', 'television', 'streaming', 'actors'],
    dmpCategories: ['Entertainment (leisure)'],
    dmpSubcategories: ['Movies', 'Television', 'Streaming media'],
    dmpSegments: ['Movies', 'Television programs', 'Streaming television'],
    secondaryTopics: ['music_live_events', 'arts_crafts_photography'],
  },
  {
    id: 'music_live_events',
    code: 'MusicLiveEvents',
    slug: 'music-live-events',
    label: 'Music & Live Events',
    labelVi: 'Âm nhạc & Sự kiện',
    znewsChannel: 'znews-music-live-events',
    keywordsVi: ['âm nhạc', 'ca sĩ', 'concert', 'lễ hội', 'sự kiện trực tiếp'],
    keywordsEn: ['music', 'artists', 'concerts', 'festivals', 'live events'],
    dmpCategories: ['Entertainment (leisure)', 'Hobbies and activities'],
    dmpSubcategories: ['Music', 'Concerts', 'Music festivals'],
    dmpSegments: ['Music', 'Live events', 'Concerts'],
    secondaryTopics: ['movies_tv_streaming', 'travel_hospitality'],
  },
  {
    id: 'books_reading',
    code: 'BooksReading',
    slug: 'books-reading',
    label: 'Books & Reading',
    labelVi: 'Sách & Văn hóa đọc',
    znewsChannel: 'znews-books-reading',
    keywordsVi: ['sách', 'đọc sách', 'tác giả', 'xuất bản', 'văn học'],
    keywordsEn: ['books', 'reading', 'authors', 'publishing', 'literature'],
    dmpCategories: ['Entertainment (leisure)', 'Hobbies and activities'],
    dmpSubcategories: ['Books', 'Reading', 'Literature'],
    dmpSegments: ['Books', 'Reading', 'E-books'],
    secondaryTopics: ['education_careers', 'arts_crafts_photography'],
  },
  {
    id: 'arts_crafts_photography',
    code: 'ArtsCraftsPhotography',
    slug: 'arts-crafts-photography',
    label: 'Arts, Crafts & Photography',
    labelVi: 'Nghệ thuật, Sáng tạo & Nhiếp ảnh',
    znewsChannel: 'znews-arts-crafts-photography',
    keywordsVi: ['nghệ thuật', 'thủ công', 'nhiếp ảnh', 'thiết kế', 'sáng tạo'],
    keywordsEn: ['arts', 'crafts', 'photography', 'design', 'creative hobbies'],
    dmpCategories: ['Hobbies and activities', 'Entertainment (leisure)'],
    dmpSubcategories: ['Arts and crafts', 'Photography', 'Design'],
    dmpSegments: ['Photography', 'Arts and crafts', 'Visual arts'],
    secondaryTopics: ['books_reading', 'fashion_beauty'],
  },
  {
    id: 'food_dining',
    code: 'FoodDining',
    slug: 'food-dining',
    label: 'Food, Cooking & Dining',
    labelVi: 'Ẩm thực, Nấu ăn & Nhà hàng',
    znewsChannel: 'znews-food-dining',
    keywordsVi: ['ẩm thực', 'nấu ăn', 'nhà hàng', 'đồ uống', 'món ngon'],
    keywordsEn: ['food', 'cooking', 'restaurants', 'beverages', 'dining'],
    dmpCategories: ['Food and drink (consumables)'],
    dmpSubcategories: ['Cooking', 'Restaurants', 'Cuisine'],
    dmpSegments: ['Food', 'Restaurants', 'Cooking'],
    secondaryTopics: ['travel_hospitality', 'health_wellness'],
  },
  {
    id: 'fashion_beauty',
    code: 'FashionBeauty',
    slug: 'fashion-beauty',
    label: 'Fashion & Beauty',
    labelVi: 'Thời trang & Làm đẹp',
    znewsChannel: 'znews-fashion-beauty',
    keywordsVi: ['thời trang', 'làm đẹp', 'mỹ phẩm', 'chăm sóc da', 'phụ kiện'],
    keywordsEn: ['fashion', 'beauty', 'cosmetics', 'skincare', 'accessories'],
    dmpCategories: ['Shopping and fashion'],
    dmpSubcategories: ['Beauty', 'Clothing', 'Fashion accessories'],
    dmpSegments: ['Beauty', 'Cosmetics', 'Fashion'],
    secondaryTopics: ['shopping_ecommerce', 'arts_crafts_photography'],
  },
  {
    id: 'shopping_ecommerce',
    code: 'ShoppingEcommerce',
    slug: 'shopping-ecommerce',
    label: 'Shopping & Ecommerce',
    labelVi: 'Mua sắm & Thương mại điện tử',
    znewsChannel: 'znews-shopping-ecommerce',
    keywordsVi: ['mua sắm', 'thương mại điện tử', 'khuyến mãi', 'bán lẻ', 'người tiêu dùng'],
    keywordsEn: ['shopping', 'ecommerce', 'promotions', 'retail', 'consumers'],
    dmpCategories: ['Shopping and fashion', 'Purchase behavior (Purchase behavior)', 'Digital Activities'],
    dmpSubcategories: ['Shopping', 'Online shopping', 'Consumer behavior'],
    dmpSegments: ['Online shopping', 'Shopping', 'Engaged shoppers'],
    secondaryTopics: ['fashion_beauty', 'marketing_digital_business'],
  },
  {
    id: 'home_garden_diy',
    code: 'HomeGardenDiy',
    slug: 'home-garden-diy',
    label: 'Home, Garden & DIY',
    labelVi: 'Nhà, Vườn & DIY',
    znewsChannel: 'znews-home-garden-diy',
    keywordsVi: ['nhà cửa', 'làm vườn', 'DIY', 'nội thất', 'trang trí'],
    keywordsEn: ['home', 'gardening', 'DIY', 'interiors', 'home improvement'],
    dmpCategories: ['Hobbies and activities'],
    dmpSubcategories: ['Home improvement', 'Gardening', 'Do it yourself'],
    dmpSegments: ['Home improvement', 'Gardening', 'DIY'],
    secondaryTopics: ['home_property_architecture', 'family_parenting'],
  },
  {
    id: 'pets_animals',
    code: 'PetsAnimals',
    slug: 'pets-animals',
    label: 'Pets & Animals',
    labelVi: 'Thú cưng & Động vật',
    znewsChannel: 'znews-pets-animals',
    keywordsVi: ['thú cưng', 'chó', 'mèo', 'chăm sóc vật nuôi', 'động vật'],
    keywordsEn: ['pets', 'dogs', 'cats', 'pet care', 'animals'],
    dmpCategories: ['Hobbies and activities'],
    dmpSubcategories: ['Pets', 'Dogs', 'Cats'],
    dmpSegments: ['Pets', 'Dogs', 'Cats'],
    secondaryTopics: ['family_parenting', 'home_garden_diy'],
  },
];

const TOPICS = [
  ...BASE_TOPICS.map((topic) => ({
    ...topic,
    znewsPath: ZNEWS_PATHS[topic.id],
    lifecycleStatus: RETIRED_TOPIC_IDS.has(topic.id) ? 'retired' : 'active',
  })),
  ...REFINED_TOPICS.map((topic) => ({
    ...topic,
    znewsPath: ZNEWS_PATHS[topic.id],
    lifecycleStatus: 'active',
  })),
];

const CREATIVE_CONTRACTS = [
  {
    id: 'znews-category-masthead-v1',
    formatId: 'znews-top-banner',
    mediaType: 'image',
    assetWidth: 2224,
    assetHeight: 480,
    displayWidth: 1160,
    displayHeight: 250,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'baomoi-category-masthead-v1',
    formatId: 'zuma-baomoi-masthead',
    mediaType: 'image',
    assetWidth: 1160,
    assetHeight: 280,
    displayWidth: 1160,
    displayHeight: 280,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'category-background-v1',
    formatId: 'znews-Background',
    mediaType: 'image',
    assetWidth: 1504,
    assetHeight: 704,
    displayWidth: 1504,
    displayHeight: 704,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'znews-category-side-left-v1',
    formatId: 'znews-side-banner',
    mediaType: 'image',
    assetWidth: 736,
    assetHeight: 1456,
    displayWidth: 368,
    displayHeight: 728,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'znews-category-side-right-v1',
    formatId: 'znews-side-banner',
    mediaType: 'image',
    assetWidth: 736,
    assetHeight: 1456,
    displayWidth: 368,
    displayHeight: 728,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'baomoi-category-side-left-v1',
    formatId: 'zuma-Left',
    mediaType: 'image',
    assetWidth: 465,
    assetHeight: 1200,
    displayWidth: 232,
    displayHeight: 600,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'baomoi-category-side-right-v1',
    formatId: 'zuma-Right',
    mediaType: 'image',
    assetWidth: 465,
    assetHeight: 1200,
    displayWidth: 232,
    displayHeight: 600,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'display-box-300x250-v1',
    formatId: 'zuma-box',
    mediaType: 'image',
    assetWidth: 300,
    assetHeight: 250,
    displayWidth: 300,
    displayHeight: 250,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'display-halfpage-300x600-v1',
    formatId: 'display-halfpage-300x600',
    mediaType: 'image',
    assetWidth: 300,
    assetHeight: 600,
    displayWidth: 300,
    displayHeight: 600,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'znews-home-inline-v1',
    formatId: 'znews-middle-banner',
    mediaType: 'image',
    assetWidth: 2048,
    assetHeight: 512,
    displayWidth: 1160,
    displayHeight: 250,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'zingmp3-masthead-v1',
    formatId: 'zmp3-top-banner',
    mediaType: 'image',
    assetWidth: 2032,
    assetHeight: 528,
    displayWidth: 2032,
    displayHeight: 528,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'smoney-top-desktop-v1',
    formatId: 'smoney-top-desktop',
    mediaType: 'image',
    assetWidth: 1440,
    assetHeight: 108,
    displayWidth: 1440,
    displayHeight: 108,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'smoney-top-mobile-v1',
    formatId: 'smoney-top-mobile',
    mediaType: 'image',
    assetWidth: 390,
    assetHeight: 96,
    displayWidth: 390,
    displayHeight: 96,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'smoney-screener-desktop-v1',
    formatId: 'smoney-screener-desktop',
    mediaType: 'image',
    assetWidth: 1090,
    assetHeight: 280,
    displayWidth: 1090,
    displayHeight: 280,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'smoney-screener-mobile-v1',
    formatId: 'smoney-screener-mobile',
    mediaType: 'image',
    assetWidth: 387,
    assetHeight: 387,
    displayWidth: 387,
    displayHeight: 387,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'dicungcon-bridge-desktop-v1',
    formatId: 'dicungcon-bridge-desktop',
    mediaType: 'image',
    assetWidth: 966,
    assetHeight: 249,
    displayWidth: 966,
    displayHeight: 249,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'dicungcon-bridge-mobile-v1',
    formatId: 'dicungcon-bridge-mobile',
    mediaType: 'image',
    assetWidth: 343,
    assetHeight: 88,
    displayWidth: 343,
    displayHeight: 88,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'zagoo-interstitial-desktop-v1',
    formatId: 'zagoo-interstitial-desktop',
    mediaType: 'image',
    assetWidth: 512,
    assetHeight: 512,
    displayWidth: 512,
    displayHeight: 512,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
  {
    id: 'zagoo-interstitial-mobile-v1',
    formatId: 'zagoo-interstitial-mobile',
    mediaType: 'image',
    assetWidth: 350,
    assetHeight: 470,
    displayWidth: 350,
    displayHeight: 470,
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp'],
  },
];

const EXISTING_TOPIC_IDS = new Set([
  'business_finance',
  'health_wellness',
  'sports_outdoors',
  'technology_science',
  'entertainment_culture',
  'lifestyle_food_shopping',
]);

const EXISTING_TOPIC_BY_CHANNEL = Object.fromEntries(
  TOPICS
    .filter((topic) => EXISTING_TOPIC_IDS.has(topic.id))
    .map((topic) => [topic.znewsChannel, topic]),
);

const FAMILY_PROFILES = {
  category_masthead: { reachRatio: 0.72, cpm: 62000, vi: 82, ctr: 0.58, obj: 'consideration' },
  category_background: { reachRatio: 0.64, cpm: 50000, vi: 78, ctr: 0.38, obj: 'awareness' },
  category_side_left: { reachRatio: 0.46, cpm: 33000, vi: 64, ctr: 0.34, obj: 'awareness' },
  category_side_right: { reachRatio: 0.42, cpm: 30000, vi: 61, ctr: 0.31, obj: 'awareness' },
  category_sidebar: { reachRatio: 0.32, cpm: 25000, vi: 62, ctr: 0.45, obj: 'conversion' },
};

const PROPERTY_CHANNELS = {
  'smoney-site': {
    name: 'S-Money Finance & Investment',
    reach: 180000,
    topicId: 'business_finance',
  },
  'dicungcon-site': {
    name: 'Đi Cùng Con Family & Parenting',
    reach: 140000,
    topicId: 'family_parenting',
  },
  'zagoo-site': {
    name: 'Zagoo Games & Entertainment',
    reach: 220000,
    topicId: 'gaming_esports',
  },
};

const PROPERTY_PLACEMENTS = [
  {
    id: 'SMoney_TopPromo_Desktop',
    publisher: 'S-Money',
    siteId: 'smoney',
    channel: 'smoney-site',
    pageTemplate: 'finance-home',
    topicId: 'business_finance',
    placementFamily: 'top_promo',
    device: ['desktop'],
    format: 'banner',
    size: '1440x108',
    subFormat: 'top-promo',
    creativeContractId: 'smoney-top-desktop-v1',
    rendererTemplateId: 'smoney-finance-v1',
    evidenceIds: ['np6-smoney-home-desktop-house-banner'],
    provenanceClassification: 'observed_house',
    commercialStatus: 'unconfirmed_house',
    metrics: { reachRatio: 0.45, cpm: 42000, vi: 72, ctr: 0.30, obj: 'awareness' },
    keywords: ['macroeconomics', 'banking', 'investment', 'professional finance'],
  },
  {
    id: 'SMoney_TopPromo_Mobile',
    publisher: 'S-Money',
    siteId: 'smoney',
    channel: 'smoney-site',
    pageTemplate: 'finance-home',
    topicId: 'business_finance',
    placementFamily: 'top_promo',
    device: ['mobile'],
    format: 'banner',
    size: '390x96',
    subFormat: 'top-promo-mobile',
    creativeContractId: 'smoney-top-mobile-v1',
    rendererTemplateId: 'smoney-finance-v1',
    evidenceIds: ['np6-smoney-home-mobile-house-banner'],
    provenanceClassification: 'observed_house',
    commercialStatus: 'unconfirmed_house',
    metrics: { reachRatio: 0.38, cpm: 38000, vi: 76, ctr: 0.34, obj: 'awareness' },
    keywords: ['mobile finance', 'banking', 'investment', 'market news'],
  },
  {
    id: 'SMoney_StockScreener_InContent_Desktop',
    publisher: 'S-Money',
    siteId: 'smoney',
    channel: 'smoney-site',
    pageTemplate: 'stock-screener',
    topicId: 'business_finance',
    placementFamily: 'in_content',
    device: ['desktop'],
    format: 'banner',
    size: '1090x280',
    subFormat: 'screener-in-content',
    creativeContractId: 'smoney-screener-desktop-v1',
    rendererTemplateId: 'smoney-finance-v1',
    evidenceIds: ['np6-smoney-stock-screener-desktop-ad'],
    provenanceClassification: 'observed_filled',
    commercialStatus: 'observed_provider_delivery',
    metrics: { reachRatio: 0.34, cpm: 52000, vi: 81, ctr: 0.62, obj: 'conversion' },
    keywords: ['stock screener', 'active investors', 'portfolio research', 'trading tools'],
  },
  {
    id: 'SMoney_StockScreener_InContent_Mobile',
    publisher: 'S-Money',
    siteId: 'smoney',
    channel: 'smoney-site',
    pageTemplate: 'stock-screener',
    topicId: 'business_finance',
    placementFamily: 'in_content',
    device: ['mobile'],
    format: 'banner',
    size: '387x387',
    subFormat: 'screener-in-content-mobile',
    creativeContractId: 'smoney-screener-mobile-v1',
    rendererTemplateId: 'smoney-finance-v1',
    evidenceIds: ['np6-smoney-stock-screener-mobile-ad'],
    provenanceClassification: 'observed_filled',
    commercialStatus: 'observed_provider_delivery',
    metrics: { reachRatio: 0.29, cpm: 48000, vi: 84, ctr: 0.68, obj: 'conversion' },
    keywords: ['mobile stock research', 'active investors', 'portfolio decision', 'trading tools'],
  },
  {
    id: 'DiCungCon_ContentBridge_Desktop',
    publisher: 'Đi Cùng Con',
    siteId: 'dicungcon',
    channel: 'dicungcon-site',
    pageTemplate: 'parenting-home',
    topicId: 'family_parenting',
    placementFamily: 'content_bridge',
    device: ['desktop'],
    format: 'banner',
    size: '966x249',
    subFormat: 'content-bridge',
    creativeContractId: 'dicungcon-bridge-desktop-v1',
    rendererTemplateId: 'dicungcon-parenting-v1',
    evidenceIds: ['np6-dicungcon-home-desktop-house-banner'],
    provenanceClassification: 'observed_house',
    commercialStatus: 'unconfirmed_house',
    metrics: { reachRatio: 0.42, cpm: 39000, vi: 77, ctr: 0.48, obj: 'consideration' },
    keywords: ['pregnancy content', 'parenting', 'child health', 'family services'],
  },
  {
    id: 'DiCungCon_ContentBridge_Mobile',
    publisher: 'Đi Cùng Con',
    siteId: 'dicungcon',
    channel: 'dicungcon-site',
    pageTemplate: 'parenting-home',
    topicId: 'family_parenting',
    placementFamily: 'content_bridge',
    device: ['mobile'],
    format: 'banner',
    size: '343x88',
    subFormat: 'content-bridge-mobile',
    creativeContractId: 'dicungcon-bridge-mobile-v1',
    rendererTemplateId: 'dicungcon-parenting-v1',
    evidenceIds: ['np6-dicungcon-home-mobile-house-banner'],
    provenanceClassification: 'observed_house',
    commercialStatus: 'unconfirmed_house',
    metrics: { reachRatio: 0.36, cpm: 35000, vi: 80, ctr: 0.52, obj: 'consideration' },
    keywords: ['mobile parenting', 'pregnancy content', 'child education', 'family services'],
  },
  {
    id: 'DiCungCon_SidebarRail_Desktop',
    publisher: 'Đi Cùng Con',
    siteId: 'dicungcon',
    channel: 'dicungcon-site',
    pageTemplate: 'parenting-home',
    topicId: 'family_parenting',
    placementFamily: 'sidebar_rail',
    device: ['desktop'],
    format: 'banner',
    size: '300x600',
    subFormat: 'sidebar-rail',
    creativeContractId: 'display-halfpage-300x600-v1',
    rendererTemplateId: 'dicungcon-parenting-v1',
    evidenceIds: ['np6-dicungcon-reserved-desktop-column'],
    provenanceClassification: 'reserved_layout',
    commercialStatus: 'proposed_mock_only',
    metrics: { reachRatio: 0.24, cpm: 28000, vi: 65, ctr: 0.40, obj: 'conversion' },
    keywords: ['parenting products', 'education', 'toys', 'family care'],
  },
  {
    id: 'Zagoo_Interstitial_Desktop',
    publisher: 'Zagoo',
    siteId: 'zagoo',
    channel: 'zagoo-site',
    pageTemplate: 'game-discovery',
    topicId: 'gaming_esports',
    placementFamily: 'interstitial',
    device: ['desktop'],
    format: 'interstitial',
    size: '512x512',
    subFormat: 'game-interstitial',
    creativeContractId: 'zagoo-interstitial-desktop-v1',
    rendererTemplateId: 'zagoo-games-v1',
    evidenceIds: ['np6-zagoo-home-desktop-house-interstitial'],
    provenanceClassification: 'observed_house',
    commercialStatus: 'unconfirmed_house',
    metrics: { reachRatio: 0.40, cpm: 56000, vi: 88, ctr: 0.72, obj: 'awareness' },
    keywords: ['mobile games', 'casual games', 'role-playing games', 'game discovery'],
  },
  {
    id: 'Zagoo_Interstitial_Mobile',
    publisher: 'Zagoo',
    siteId: 'zagoo',
    channel: 'zagoo-site',
    pageTemplate: 'game-discovery',
    topicId: 'gaming_esports',
    placementFamily: 'interstitial',
    device: ['mobile'],
    format: 'interstitial',
    size: '350x470',
    subFormat: 'game-interstitial-mobile',
    creativeContractId: 'zagoo-interstitial-mobile-v1',
    rendererTemplateId: 'zagoo-games-v1',
    evidenceIds: ['np6-zagoo-home-mobile-house-interstitial'],
    provenanceClassification: 'observed_house',
    commercialStatus: 'unconfirmed_house',
    metrics: { reachRatio: 0.44, cpm: 60000, vi: 91, ctr: 0.78, obj: 'awareness' },
    keywords: ['mobile games', 'casual games', 'game offers', 'game discovery'],
  },
];

function topicAudienceContext(topic) {
  return {
    taxonomyVersion: NP6_TAXONOMY_VERSION,
    primaryTopics: [topic.id],
    secondaryTopics: topic.secondaryTopics || [],
    keywordsVi: topic.keywordsVi,
    keywordsEn: topic.keywordsEn,
    dmpCategoryAffinities: topic.dmpCategories,
    dmpSubcategoryAffinities: topic.dmpSubcategories || [],
    dmpSegmentAffinities: topic.dmpSegments || [],
    intentSignals: [],
    exclusions: topic.exclusions || [],
    confidence: 0.9,
  };
}

function propertyAudienceContext(topicId, keywords = []) {
  const topic = TOPICS.find((item) => item.id === topicId);
  if (!topic) throw new Error(`Unknown NP-6 property topic: ${topicId}`);
  const context = topicAudienceContext(topic);
  return {
    ...context,
    keywordsEn: [...new Set([...context.keywordsEn, ...keywords])],
    confidence: 0.92,
  };
}

function deriveNp6Metrics(publisher, family, channelReach) {
  const profile = FAMILY_PROFILES[family];
  const publisherMultiplier = publisher === 'BaoMoi' ? 0.95 : 1.05;
  return {
    reach: Math.round((channelReach * profile.reachRatio) / 5000) * 5000,
    vi: profile.vi,
    ctr: profile.ctr,
    cpm: Math.round((profile.cpm * publisherMultiplier) / 1000) * 1000,
    obj: profile.obj,
    metricSource: 'synthetic_inventory_v3',
    inventoryTier: family.replaceAll('_', '-'),
  };
}

function contractFor(publisher, family) {
  if (family === 'category_masthead') {
    return publisher === 'ZNews'
      ? 'znews-category-masthead-v1'
      : 'baomoi-category-masthead-v1';
  }
  if (family === 'category_background') return 'category-background-v1';
  if (family === 'category_sidebar') return 'display-box-300x250-v1';
  if (publisher === 'ZNews') {
    return family === 'category_side_left'
      ? 'znews-category-side-left-v1'
      : 'znews-category-side-right-v1';
  }
  return family === 'category_side_left'
    ? 'baomoi-category-side-left-v1'
    : 'baomoi-category-side-right-v1';
}

function familySpec(family) {
  if (family === 'category_masthead') return { format: 'banner', size: null, subFormat: 'masthead' };
  if (family === 'category_sidebar') return { format: 'banner', size: '300x250', subFormat: 'sidebar' };
  return {
    format: 'skin',
    size: 'skin',
    subFormat: family.replace('category_', '').replaceAll('_', '-'),
  };
}

function makePlacement({ publisher, topic, family, channel, channelReach, siteUrl }) {
  const prefix = publisher === 'ZNews' ? 'Znews' : 'BaoMoi';
  const suffix = {
    category_masthead: 'Masthead',
    category_background: 'Background',
    category_side_left: 'SideLeft',
    category_side_right: 'SideRight',
    category_sidebar: 'SidebarBox',
  }[family];
  const id = `${prefix}_${topic.code}_${suffix}`;
  const spec = familySpec(family);
  const size = family === 'category_masthead'
    ? (publisher === 'ZNews' ? '1160x250' : '1160x280')
    : spec.size;
  return {
    id,
    channel,
    publisher,
    siteId: publisher === 'ZNews' ? 'znews' : 'baomoi',
    format: spec.format,
    size,
    subFormat: spec.subFormat,
    flexible: false,
    pageTemplate: 'category',
    topicId: topic.id,
    placementFamily: family,
    comparisonGroupId: `${topic.id}:${family}`,
    device: ['desktop'],
    creativeContractId: contractFor(publisher, family),
    catalogVersion: NP6_CATALOG_VERSION,
    recordRevision: 1,
    lifecycleStatus: 'active',
    testSiteZone: id,
    siteUrl,
    renderer: {
      templateId: publisher === 'ZNews' ? 'znews-static-category-v3' : 'baomoi-category-v2',
      renderZoneId: id,
      previewSupported: true,
      siteUrl,
    },
    audienceContext: topicAudienceContext(topic),
    provenance: {
      classification: 'demo_fixture',
      sourceType: 'live_layout_observation_plus_synthetic_fixture',
      evidenceIds: ['np6-category-census-2026-07-25'],
      verifiedAt: '2026-07-25',
    },
    ...deriveNp6Metrics(publisher, family, channelReach),
  };
}

function buildNp6Channels(existingChannels = {}) {
  const channels = { ...existingChannels };
  for (const topic of TOPICS) {
    if (!channels[topic.znewsChannel]) {
      channels[topic.znewsChannel] = {
        name: `ZNews ${topic.label}`,
        reach: 320000,
        topicId: topic.id,
      };
    } else {
      channels[topic.znewsChannel] = {
        ...channels[topic.znewsChannel],
        topicId: topic.id,
      };
    }
    const baomoiChannel = `baomoi-${topic.slug}`;
    channels[baomoiChannel] = {
      name: `BaoMoi ${topic.label}`,
      reach: 360000,
      topicId: topic.id,
    };
  }
  for (const [channelId, channel] of Object.entries(PROPERTY_CHANNELS)) {
    channels[channelId] = { ...channel };
  }
  return channels;
}

function siteUrl(base, topic, publisher) {
  const root = base.replace(/\/$/, '');
  if (publisher === 'ZNews') return `${root}${topic.znewsPath}`;
  return `${root}/category.html?topic=${encodeURIComponent(topic.slug)}`;
}

function buildNp6Placements(channels, {
  znewsBase = 'https://znews-stg.pawgrammers.io.vn',
  baomoiBase = 'https://baomoi-stg.pawgrammers.io.vn',
} = {}) {
  const placements = [];
  const families = Object.keys(FAMILY_PROFILES);
  for (const topic of TOPICS.filter((item) => item.lifecycleStatus === 'active')) {
    const znewsFamilies = EXISTING_TOPIC_IDS.has(topic.id)
      ? ['category_masthead']
      : families;
    for (const family of znewsFamilies) {
      placements.push(makePlacement({
        publisher: 'ZNews',
        topic,
        family,
        channel: topic.znewsChannel,
        channelReach: channels[topic.znewsChannel].reach,
        siteUrl: siteUrl(znewsBase, topic, 'ZNews'),
      }));
    }
    const baomoiChannel = `baomoi-${topic.slug}`;
    for (const family of families) {
      placements.push(makePlacement({
        publisher: 'BaoMoi',
        topic,
        family,
        channel: baomoiChannel,
        channelReach: channels[baomoiChannel].reach,
        siteUrl: siteUrl(baomoiBase, topic, 'BaoMoi'),
      }));
    }
  }
  return placements;
}

function buildPropertyPlacements(channels, {
  smoneyBase = 'https://smoney-stg.pawgrammers.io.vn',
  dicungconBase = 'https://dicungcon-stg.pawgrammers.io.vn',
  zagooBase = 'https://zagoo-stg.pawgrammers.io.vn',
} = {}) {
  const siteBases = {
    smoney: smoneyBase,
    dicungcon: dicungconBase,
    zagoo: zagooBase,
  };
  return PROPERTY_PLACEMENTS.map((spec) => {
    const channelReach = channels[spec.channel]?.reach || 0;
    const siteUrl = `${siteBases[spec.siteId].replace(/\/$/, '')}/`;
    const metrics = spec.metrics;
    return {
      id: spec.id,
      channel: spec.channel,
      publisher: spec.publisher,
      siteId: spec.siteId,
      format: spec.format,
      size: spec.size,
      subFormat: spec.subFormat,
      flexible: false,
      pageTemplate: spec.pageTemplate,
      topicId: spec.topicId,
      placementFamily: spec.placementFamily,
      comparisonGroupId: null,
      device: spec.device,
      creativeContractId: spec.creativeContractId,
      catalogVersion: NP6_CATALOG_VERSION,
      recordRevision: 1,
      lifecycleStatus: 'active',
      testSiteZone: spec.id,
      siteUrl,
      renderer: {
        templateId: spec.rendererTemplateId,
        renderZoneId: spec.id,
        previewSupported: true,
        siteUrl,
      },
      audienceContext: propertyAudienceContext(spec.topicId, spec.keywords),
      provenance: {
        classification: spec.provenanceClassification,
        sourceType: 'live_layout_observation_plus_synthetic_fixture',
        commercialStatus: spec.commercialStatus,
        evidenceIds: spec.evidenceIds,
        verifiedAt: '2026-07-25',
      },
      reach: Math.round((channelReach * metrics.reachRatio) / 1000) * 1000,
      vi: metrics.vi,
      ctr: metrics.ctr,
      cpm: metrics.cpm,
      obj: metrics.obj,
      metricSource: 'synthetic_inventory_v3',
      inventoryTier: `${spec.siteId}-${spec.placementFamily}-${spec.device[0]}`,
    };
  });
}

function legacyFamily(placement) {
  const id = placement.id || '';
  if (id.includes('Masthead_Inline')) return 'homepage_inline';
  if (id === 'ZingNews_Masthead' || id === 'BaoMoi_Masthead' || id === 'ZingMP3_Masthead') {
    return 'homepage_masthead';
  }
  if (id.includes('Background')) {
    return placement.siteId === 'znews' ? 'category_background' : 'homepage_background';
  }
  if (id.includes('SideLeft')) return 'category_side_left';
  if (id.includes('SideRight')) return 'category_side_right';
  if (id.includes('StickyLeft')) return 'homepage_side_left';
  if (id.includes('StickyRight')) return 'homepage_side_right';
  if (id.includes('SidebarBox')) return 'category_sidebar';
  if (id.includes('PrBox')) return 'content_pr_box';
  if (id.includes('Halfpage') || id.includes('Box2')) return 'large_middle_unit';
  if (id.includes('Box1')) return 'standard_box';
  return 'legacy';
}

function legacyContract(placement, family) {
  if (placement.id === 'ZingMP3_Masthead') return 'zingmp3-masthead-v1';
  if (placement.id === 'ZingNews_Masthead') return 'znews-category-masthead-v1';
  if (placement.id === 'BaoMoi_Masthead') return 'baomoi-category-masthead-v1';
  if (family === 'homepage_inline' || placement.id === 'ZingNews_Halfpage') return 'znews-home-inline-v1';
  if (placement.size === '300x600') return 'display-halfpage-300x600-v1';
  if (placement.size === '300x250') return 'display-box-300x250-v1';
  if (family.includes('background')) return 'category-background-v1';
  if (family.endsWith('side_left')) {
    return placement.siteId === 'znews'
      ? 'znews-category-side-left-v1'
      : 'baomoi-category-side-left-v1';
  }
  if (family.endsWith('side_right')) {
    return placement.siteId === 'znews'
      ? 'znews-category-side-right-v1'
      : 'baomoi-category-side-right-v1';
  }
  return null;
}

function legacyTopic(placement) {
  const channelTopic = EXISTING_TOPIC_BY_CHANNEL[placement.channel];
  if (channelTopic) return { topic: channelTopic, scope: 'category' };
  if (placement.siteId === 'zingmp3') {
    return {
      topic: TOPICS.find((item) => item.id === 'music_live_events'),
      scope: 'publisher_vertical',
    };
  }
  if (placement.siteId === 'znews' || placement.siteId === 'baomoi') {
    return {
      topic: TOPICS.find((item) => item.id === 'society_news_law'),
      scope: 'broad_news_homepage',
    };
  }
  return { topic: null, scope: 'unclassified' };
}

function enrichLegacyPlacements(placements) {
  return placements.map((placement) => {
    const { topic, scope } = legacyTopic(placement);
    const family = legacyFamily(placement);
    const publisher = placement.siteId === 'znews'
      ? 'ZNews'
      : placement.siteId === 'baomoi'
        ? 'BaoMoi'
        : placement.siteId === 'zingmp3'
          ? 'ZingMP3'
          : null;
    const audienceContext = topic ? topicAudienceContext(topic) : null;
    if (audienceContext) {
      audienceContext.contextScope = scope;
      // A broad news homepage is valid fallback inventory, but its inferred
      // topic affinity must stay weaker than an explicit category page.
      if (scope === 'broad_news_homepage') audienceContext.confidence = 0.55;
    }
    return {
      ...placement,
      publisher,
      pageTemplate: scope === 'category' ? 'category' : 'homepage',
      topicId: topic?.id || null,
      placementFamily: family,
      comparisonGroupId: scope === 'category' ? `${topic.id}:${family}` : null,
      device: ['desktop'],
      creativeContractId: legacyContract(placement, family),
      catalogVersion: 'legacy-35',
      recordRevision: scope === 'category' ? 1 : 2,
      lifecycleStatus: topic?.lifecycleStatus === 'retired' ? 'retired' : 'active',
      flexible: Boolean(placement.flexible),
      audienceContext,
      provenance: {
        classification: 'demo_fixture',
        sourceType: scope === 'category'
          ? 'legacy_forced_mapping'
          : 'legacy_contextual_enrichment',
        evidenceIds: scope === 'category'
          ? []
          : ['np6-legacy-metadata-audit-2026-07-26'],
        verifiedAt: scope === 'category' ? null : '2026-07-26',
      },
    };
  });
}

function extendGroups(groups) {
  const znewsChannels = TOPICS.map((topic) => topic.znewsChannel);
  const baomoiChannels = ['baomoi-site', ...TOPICS.map((topic) => `baomoi-${topic.slug}`)];
  const extended = groups.map((group) => {
    if (group.id === 'znews-categories') return { ...group, channels: znewsChannels };
    if (group.id === 'baomoi-site') return { ...group, channels: baomoiChannels };
    return group;
  });
  const additions = [
    {
      id: 'smoney-site',
      name: 'S-Money',
      desc: 'Finance and investment tools — smoney-stg.pawgrammers.io.vn',
      channels: ['smoney-site'],
    },
    {
      id: 'dicungcon-site',
      name: 'Đi Cùng Con',
      desc: 'Family and parenting — dicungcon-stg.pawgrammers.io.vn',
      channels: ['dicungcon-site'],
    },
    {
      id: 'zagoo-site',
      name: 'Zagoo',
      desc: 'Game discovery — zagoo-stg.pawgrammers.io.vn',
      channels: ['zagoo-site'],
    },
  ];
  const known = new Set(extended.map((group) => group.id));
  return [...extended, ...additions.filter((group) => !known.has(group.id))];
}

function applyNp6Catalog(baseCatalog, options = {}) {
  const channels = buildNp6Channels(baseCatalog.channels);
  const legacy = enrichLegacyPlacements(baseCatalog.placements);
  const categoryAdditions = buildNp6Placements(channels, options);
  const propertyAdditions = buildPropertyPlacements(channels, options);
  const additions = [...categoryAdditions, ...propertyAdditions];
  const ids = [...legacy, ...additions].map((placement) => placement.id);
  if (new Set(ids).size !== ids.length) {
    throw new Error('NP-6 catalog contains duplicate placement IDs');
  }
  return {
    ...baseCatalog,
    catalogVersion: NP6_CATALOG_VERSION,
    taxonomyVersion: NP6_TAXONOMY_VERSION,
    revision: 1,
    previousVersion: 'np6-2026-02',
    groups: extendGroups(baseCatalog.groups),
    channels,
    placements: [...legacy, ...additions],
    creativeContracts: CREATIVE_CONTRACTS,
    topicTaxonomy: TOPICS,
  };
}

module.exports = {
  NP6_CATALOG_VERSION,
  NP6_TAXONOMY_VERSION,
  TOPICS,
  CREATIVE_CONTRACTS,
  EXISTING_TOPIC_IDS,
  FAMILY_PROFILES,
  deriveNp6Metrics,
  buildNp6Channels,
  buildNp6Placements,
  buildPropertyPlacements,
  enrichLegacyPlacements,
  applyNp6Catalog,
};
