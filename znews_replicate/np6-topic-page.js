(() => {
  const menuTopics = [
    ['Kinh doanh', 'kinh-doanh.html'],
    ['Sức khỏe', 'suc-khoe.html'],
    ['Thể thao', 'the-thao.html'],
    ['Công nghệ', 'cong-nghe.html'],
    ['Gia đình', 'gia-dinh.html'],
    ['Giáo dục & Nghề nghiệp', 'giao-duc-nghe-nghiep.html'],
    ['Du lịch & Lưu trú', 'du-lich-luu-tru.html'],
    ['Xe & Di chuyển', 'xe-di-chuyen.html'],
    ['Nhà ở & Bất động sản', 'nha-o-bat-dong-san.html'],
    ['Xã hội & Pháp luật', 'xa-hoi-phap-luat.html'],
    ['Marketing & Kinh doanh số', 'marketing-kinh-doanh-so.html'],
    ['Fitness & Sống khỏe', 'fitness-song-khoe.html'],
    ['Bóng đá', 'bong-da.html'],
    ['Game & Esports', 'game-esports.html'],
    ['Phim & Truyền hình', 'phim-truyen-hinh.html'],
    ['Âm nhạc & Sự kiện', 'am-nhac-su-kien.html'],
    ['Sách & Đọc', 'sach-va-doc.html'],
    ['Nghệ thuật & Sáng tạo', 'nghe-thuat-sang-tao.html'],
    ['Ẩm thực & Nhà hàng', 'am-thuc-nha-hang.html'],
    ['Thời trang & Làm đẹp', 'thoi-trang-lam-dep.html'],
    ['Mua sắm & Thương mại điện tử', 'mua-sam-thuong-mai-dien-tu.html'],
    ['Nhà vườn & DIY', 'nha-vuon-diy.html'],
    ['Thú cưng & Động vật', 'thu-cung-dong-vat.html'],
  ];

  const setupCategoryMenu = () => {
    const header = document.getElementById('zing-header');
    const trigger = header?.querySelector(':scope > .page-wrapper .category-menu .more');
    const popup = header?.querySelector(':scope > .category-popup');
    if (!header || !trigger || !popup) return;

    popup.id = 'np6-category-popup';
    popup.classList.add('np6-category-popup');
    popup.setAttribute('aria-hidden', 'true');
    popup.innerHTML = `
      <div class="np6-mega-inner">
        <div class="np6-mega-grid" role="menu" aria-label="Chuyên mục ZNews">
          ${menuTopics.map(([label, href]) => `
            <a role="menuitem" href="${href}"><span aria-hidden="true">/</span>${label}</a>
          `).join('')}
        </div>
      </div>
      <div class="np6-channel-bar" aria-label="Kênh nội dung">
        <a href="#" data-channel="podcast">Podcast</a>
        <a href="#" data-channel="longform">Longform</a>
        <a href="#" data-channel="story">Story</a>
        <a href="#" data-channel="lens">Lens</a>
      </div>
    `;

    trigger.setAttribute('role', 'button');
    trigger.setAttribute('tabindex', '0');
    trigger.setAttribute('aria-label', 'Mở danh sách chuyên mục');
    trigger.setAttribute('aria-controls', popup.id);
    trigger.setAttribute('aria-expanded', 'false');

    let closeTimer = null;
    const setOpen = (open) => {
      window.clearTimeout(closeTimer);
      trigger.classList.toggle('active', open);
      popup.classList.toggle('active', open);
      trigger.setAttribute('aria-expanded', String(open));
      trigger.setAttribute('aria-label', open ? 'Đóng danh sách chuyên mục' : 'Mở danh sách chuyên mục');
      popup.setAttribute('aria-hidden', String(!open));
    };
    const open = () => setOpen(true);
    const close = (delay = 0) => {
      window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(() => {
        if (!header.matches(':hover') && !header.contains(document.activeElement)) setOpen(false);
      }, delay);
    };
    const toggle = () => setOpen(trigger.getAttribute('aria-expanded') !== 'true');

    trigger.addEventListener('mouseenter', open);
    header.addEventListener('mouseleave', () => close(120));
    trigger.addEventListener('click', (event) => {
      event.preventDefault();
      toggle();
    });
    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggle();
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        open();
        popup.querySelector('[role="menuitem"]')?.focus();
      }
    });
    popup.addEventListener('focusin', open);
    header.addEventListener('focusout', () => close());
    popup.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
        trigger.focus();
      }
    });
    popup.querySelectorAll('[data-channel]').forEach((link) => {
      link.addEventListener('click', (event) => event.preventDefault());
    });
    document.addEventListener('pointerdown', (event) => {
      if (!header.contains(event.target)) setOpen(false);
    });
  };

  setupCategoryMenu();

  const params = new URLSearchParams(location.search);
  const evidence = params.get('evidence') === '1';
  const adMode = params.get('admode') === 'masthead' ? 'masthead' : 'skin';

  document.body.dataset.admode = adMode;
  if (!evidence) return;
  document.body.classList.add('np6-evidence-mode');

  const background = document.querySelector('[data-zone$="_Background"]');
  if (background) {
    const badge = document.createElement('span');
    badge.className = 'np6-background-evidence';
    badge.textContent = background.dataset.zone;
    document.body.appendChild(badge);
  }
})();
