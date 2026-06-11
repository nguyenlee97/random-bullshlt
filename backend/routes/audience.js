const express = require('express');
const router = express.Router();

// Static DMP attributes for audience estimation (same as dmp.js)
const DMP_ATTRS = [
  { k: 'travel_intent_sea',  size: 1850000 },
  { k: 'air_travel',         size: 2200000 },
  { k: 'hotel_booker',       size: 1430000 },
  { k: 'credit_card_user',   size: 3100000 },
  { k: 'fintech_high_value', size:  680000 },
  { k: 'hcm_hn_dn',          size: 5200000 },
  { k: 'age_25_44',          size: 8900000 },
  { k: 'premium_lifestyle',  size:  920000 },
  { k: 'first_jobber',       size: 1780000 },
  { k: 'car_buyer_intent',   size:  420000 },
  { k: 'new_parent',         size:  680000 },
  { k: 'gamer_hardcore',     size: 1120000 },
];

const TARGETING_OPTIONS = {
  geo: {
    'Miền Bắc':   ['Hà Nội','Cao Bằng','Hải Phòng','Quảng Ninh','Sơn La','Thái Bình','Bắc Ninh','Vĩnh Phúc'],
    'Miền Trung': ['Đà Nẵng','Huế','Nghệ An','Thanh Hóa','Khánh Hòa','Bình Định'],
    'Miền Nam':   ['TP.HCM','Cần Thơ','Đồng Nai','Bình Dương','Vũng Tàu','Long An'],
  },
  age:       ['Under 18','18-24','25-34','35-44','45-54','55-64','Over 64'],
  gender:    ['Male','Female'],
  deviceOS:  ['Android','iOS','Windows Phone','PC and other'],
  income:    ['Top 5%','Top 5-10%','Top 10-25%','Top 25-50%','Top 50-75%','Top 75-100%'],
  education: ['Entry Level','College & Bachelor','Master','Doctor'],
  interest:  ['Real Estate','Entertainment > Movie','Entertainment > Celebrities','Entertainment > Reading','Travel','Air travel','Hotel','Credit cards','Fintech','Fashion','F&B','Sports','Automotive','Education','Healthcare'],
};

// Mirrors mock AdsPilotAPI.estimateAudience() logic exactly
function estimateAudience(targeting) {
  const t = targeting || {};
  let pop = 60_000_000;

  const allProvinces = Object.values(TARGETING_OPTIONS.geo).flat();
  if (t.geo && t.geo.length)       pop = pop * (t.geo.length / allProvinces.length);
  if (t.age && t.age.length)       pop *= (t.age.length / TARGETING_OPTIONS.age.length);
  if (t.gender && t.gender.length) pop *= (t.gender.length / TARGETING_OPTIONS.gender.length);
  if (t.deviceOS && t.deviceOS.length) pop *= (t.deviceOS.length / TARGETING_OPTIONS.deviceOS.length);
  if (t.income && t.income.length) pop *= (t.income.length / TARGETING_OPTIONS.income.length);
  if (t.education && t.education.length) pop *= (t.education.length / TARGETING_OPTIONS.education.length);
  if (t.interest && t.interest.length)   pop *= Math.min(1, t.interest.length * 0.15);

  if (t.dmpInclude && t.dmpInclude.length) {
    const sizes = t.dmpInclude.map((k) => {
      const a = DMP_ATTRS.find((x) => x.k === k);
      return a ? a.size : 0;
    });
    const minSize = Math.min(...sizes);
    pop = Math.min(pop, minSize * Math.pow(0.82, t.dmpInclude.length - 1));
  }

  const size = Math.round(pop);
  return { size, low: Math.round(size * 0.85), high: Math.round(size * 1.15) };
}

// POST /api/audience/estimate
// Body: { geo, age, gender, deviceOS, income, education, interest, dmpInclude }
router.post('/estimate', (req, res) => {
  try {
    const targeting = req.body || {};
    const result = estimateAudience(targeting);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
