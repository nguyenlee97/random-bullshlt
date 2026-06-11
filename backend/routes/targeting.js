const express = require('express');
const router = express.Router();

// Static targeting options — same as mock TARGETING constant
// Stored in-memory (no need to hit DB for static config)
const TARGETING = {
  geo: {
    'Miền Bắc':   ['Hà Nội','Cao Bằng','Hải Phòng','Quảng Ninh','Sơn La','Thái Bình','Bắc Ninh','Vĩnh Phúc'],
    'Miền Trung': ['Đà Nẵng','Huế','Nghệ An','Thanh Hóa','Khánh Hòa','Bình Định'],
    'Miền Nam':   ['TP.HCM','Cần Thơ','Đồng Nai','Bình Dương','Vũng Tàu','Long An'],
  },
  age:         ['Under 18','18-24','25-34','35-44','45-54','55-64','Over 64'],
  gender:      ['Male','Female'],
  deviceOS:    ['Android','iOS','Windows Phone','PC and other'],
  deviceBrand: ['Samsung','Apple','Xiaomi','Oppo','Vivo','Realme','Huawei','ZTE','Vertex','Lava','iBRIT','Blu'],
  marital:     ['Single','Married'],
  parental:    ['Have children under age 6','Have children','No children'],
  education:   ['Entry Level','College & Bachelor','Master','Doctor'],
  income:      ['Top 5%','Top 5-10%','Top 10-25%','Top 25-50%','Top 50-75%','Top 75-100%'],
  career:      ['Student','Office Worker','Labour Worker','Housewife','Shop owner','Arts/Design/Entertainment','Sales','Healthcare','Engineering','Farming/Fishing/Forestry','Installation/Maintenance'],
  interest:    ['Real Estate','Entertainment > Movie','Entertainment > Celebrities','Entertainment > Reading','Travel','Air travel','Hotel','Credit cards','Fintech','Fashion','F&B','Sports','Automotive','Education','Healthcare'],
  weather:     ['Sunny','Rain','Cloudy','Other'],
};

// GET /api/targeting/options
router.get('/options', (_req, res) => {
  res.json(TARGETING);
});

module.exports = router;
