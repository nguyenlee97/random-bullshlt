require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const morgan = require('morgan');

const app = express();

// ── CORS ─────────────────────────────────────────────────────────────────────
const allowedOrigins = (process.env.ALLOWED_ORIGINS || '')
  .split(',')
  .map((o) => o.trim())
  .filter(Boolean);

app.use(
  cors({
    origin: (origin, cb) => {
      // Allow requests with no origin (curl, Postman, same-origin)
      if (!origin || allowedOrigins.length === 0 || allowedOrigins.includes(origin)) {
        return cb(null, true);
      }
      cb(new Error(`CORS: origin ${origin} not allowed`));
    },
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
  })
);

// ── BODY / LOGGING ────────────────────────────────────────────────────────────
app.use(express.json({ limit: '25mb' }));   // 25mb for base64 AI-generated images
app.use(express.urlencoded({ extended: true, limit: '25mb' }));
app.use(morgan('dev'));

// ── STATIC: uploaded creatives ────────────────────────────────────────────────
// Serves files in backend/uploads/ at /uploads/<filename>
// On VPS, Nginx proxies /uploads/* here so the URL is https://api.pawgrammers.io.vn/uploads/<file>
const path = require('path');
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// ── API LOGGING MIDDLEWARE ────────────────────────────────────────────────────
const { logRequest } = require('./middleware/apiLogger');
app.use(logRequest);

// ── ROUTES ────────────────────────────────────────────────────────────────────
app.use('/api/zones',          require('./routes/zones'));
app.use('/api/targeting',      require('./routes/targeting'));
app.use('/api/dmp',            require('./routes/dmp'));
app.use('/api/orders',         require('./routes/orders'));
app.use('/api/ads',            require('./routes/ads'));
app.use('/api/analytics',      require('./routes/analytics'));
app.use('/api/audience',       require('./routes/audience'));
app.use('/api/admin',          require('./routes/admin'));
app.use('/api/logs',           require('./routes/logs'));
app.use('/api/creative',       require('./routes/creative'));

// ── HEALTH ────────────────────────────────────────────────────────────────────
app.get('/api/health', (_req, res) => {
  res.json({ ok: true, ts: new Date().toISOString(), env: process.env.NODE_ENV });
});

// ── 404 ───────────────────────────────────────────────────────────────────────
app.use((_req, res) => res.status(404).json({ error: 'Not found' }));

// ── ERROR HANDLER ─────────────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(500).json({ error: err.message || 'Internal server error' });
});

// ── DB + LISTEN ───────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';

mongoose
  .connect(MONGODB_URI)
  .then(() => {
    console.log(`✅  MongoDB connected: ${MONGODB_URI}`);
    app.listen(PORT, () => console.log(`🚀  AdsPilot API running on http://localhost:${PORT}`));
  })
  .catch((err) => {
    console.error('❌  MongoDB connection failed:', err.message);
    process.exit(1);
  });
