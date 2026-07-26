/**
 * Ad format catalog for AI image generation.
 * Each entry matches a reference image in test-ad-image/.
 * cropAnchor: tells the canvas crop fallback where the model puts content
 *   'center' — narrow center strip (ultra-wide banners)
 *   'top'    — top-center cluster (background ads)
 *   'right'  — flush right column (zuma-Left slider)
 *   'left'   — flush left column (zuma-Right slider)
 */
export const AD_FORMATS = [
  {
    id: 'zmp3-top-banner',
    label: 'Top Banner Panoramic (2032×528)',
    width: 2032, height: 528,
    cropAnchor: 'center',
    usageHint: 'Banner ngang rộng đầu trang, tỷ lệ 3.8:1 — phù hợp header âm nhạc, tin tức',
  },
  {
    id: 'znews-Background',
    label: 'Desktop Background Skin (1504×704)',
    width: 1504, height: 704,
    cropAnchor: 'top',
    usageHint: 'Skin toàn trang desktop — nội dung tập trung phía trên, viền trái/phải để trống',
  },
  {
    id: 'znews-middle-banner',
    label: 'Mid-page Banner (2048×512)',
    width: 2048, height: 512,
    cropAnchor: 'center',
    usageHint: 'Dải ngang giữa trang — tỷ lệ 4:1, layout 3 cột: text · mascot · offers',
  },
  {
    id: 'znews-side-banner',
    label: 'Side Skyscraper (736×1456)',
    width: 736, height: 1456,
    cropAnchor: 'center',
    usageHint: 'Banner đứng dọc bên cạnh nội dung — tỷ lệ 1:2, sidebar trái hoặc phải',
  },
  {
    id: 'znews-top-banner',
    label: 'Top Banner Ultra-wide (2224×480)',
    width: 2224, height: 480,
    cropAnchor: 'center',
    usageHint: 'Header banner cực rộng — tỷ lệ 4.6:1, layout 4 cột ngang',
  },
  {
    id: 'zuma-baomoi-masthead',
    label: 'Masthead Strip (1160×280)',
    width: 1160, height: 280,
    cropAnchor: 'center',
    usageHint: 'Strip ngang đầu trang — layout sạch gọn: sản phẩm · text · CTA button · tag giá',
  },
  {
    id: 'zuma-box',
    label: 'Display Box 300×250',
    width: 300, height: 250,
    cropAnchor: 'center',
    usageHint: 'Medium Rectangle — kích thước IAB chuẩn, phổ biến nhất trên desktop',
  },
  {
    id: 'display-halfpage-300x600',
    label: 'Display Halfpage 300×600',
    width: 300, height: 600,
    cropAnchor: 'center',
    usageHint: 'Halfpage dọc — kích thước chính xác cho sidebar 300×600',
  },
  {
    id: 'znews-masthead-1160x250',
    label: 'ZingNews Masthead 1160×250',
    width: 1160, height: 250,
    cropAnchor: 'center',
    usageHint: 'Masthead ngang 1160×250 — không kéo giãn từ format 1160×280',
  },
  {
    id: 'zuma-Left',
    label: 'Sticky Side Slider Left (465×1200)',
    width: 465, height: 1200,
    cropAnchor: 'right',
    usageHint: 'Dải dọc dính bên trái màn hình — nội dung căn sát mép phải của canvas',
  },
  {
    id: 'zuma-Right',
    label: 'Sticky Side Slider Right (465×1200)',
    width: 465, height: 1200,
    cropAnchor: 'left',
    usageHint: 'Dải dọc dính bên phải màn hình — nội dung căn sát mép trái của canvas',
  },
  {
    id: 'smoney-top-desktop',
    label: 'S-Money Top Promo Desktop 1440×108',
    width: 1440, height: 108,
    cropAnchor: 'center',
    usageHint: 'Dải quảng bá tài chính rất rộng và thấp trên desktop',
  },
  {
    id: 'smoney-top-mobile',
    label: 'S-Money Top Promo Mobile 390×96',
    width: 390, height: 96,
    cropAnchor: 'center',
    usageHint: 'Dải quảng bá tài chính riêng cho màn hình điện thoại',
  },
  {
    id: 'smoney-screener-desktop',
    label: 'S-Money Screener Desktop 1090×280',
    width: 1090, height: 280,
    cropAnchor: 'center',
    usageHint: 'Quảng cáo trong nội dung tại bộ lọc cổ phiếu desktop',
  },
  {
    id: 'smoney-screener-mobile',
    label: 'S-Money Screener Mobile 387×387',
    width: 387, height: 387,
    cropAnchor: 'center',
    usageHint: 'Quảng cáo vuông trong công cụ tài chính trên mobile',
  },
  {
    id: 'dicungcon-bridge-desktop',
    label: 'Đi Cùng Con Content Bridge Desktop 966×249',
    width: 966, height: 249,
    cropAnchor: 'center',
    usageHint: 'Dải nội dung gia đình giữa các khối bài viết trên desktop',
  },
  {
    id: 'dicungcon-bridge-mobile',
    label: 'Đi Cùng Con Content Bridge Mobile 343×88',
    width: 343, height: 88,
    cropAnchor: 'center',
    usageHint: 'Dải nội dung gia đình nhỏ gọn riêng cho mobile',
  },
  {
    id: 'zagoo-interstitial-desktop',
    label: 'Zagoo Game Interstitial Desktop 512×512',
    width: 512, height: 512,
    cropAnchor: 'center',
    usageHint: 'Interstitial vuông cho ngữ cảnh khám phá game desktop',
  },
  {
    id: 'zagoo-interstitial-mobile',
    label: 'Zagoo Game Interstitial Mobile 350×470',
    width: 350, height: 470,
    cropAnchor: 'center',
    usageHint: 'Interstitial dọc cho ngữ cảnh khám phá game mobile',
  },
]

/** Map from format id → format object */
export const AD_FORMATS_MAP = Object.fromEntries(AD_FORMATS.map(f => [f.id, f]))
