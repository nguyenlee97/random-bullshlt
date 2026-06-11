const express = require('express');
const router  = express.Router();
const multer  = require('multer');
const path    = require('path');
const fs      = require('fs');
const crypto  = require('crypto');

// ── Uploads directory ──────────────────────────────────────────────────────
// Resolve once at startup: <project_root>/uploads/
// On VPS this dir will be under /var/www/backend/uploads/ and served by Nginx
const UPLOADS_DIR = path.join(__dirname, '..', 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) {
    fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

// ── Allowed MIME types ─────────────────────────────────────────────────────
const ALLOWED_TYPES = new Set([
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/gif',
]);

const ALLOWED_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif']);

// ── Unique filename generator ──────────────────────────────────────────────
function uniqueName(originalname) {
    const ext  = path.extname(originalname).toLowerCase() || '.jpg';
    const hash = crypto.randomBytes(8).toString('hex');
    const ts   = Date.now();
    return `creative_${ts}_${hash}${ext}`;
}

// ── Multer: disk storage, 20 MB limit ─────────────────────────────────────
const storage = multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, UPLOADS_DIR),
    filename:    (_req, file, cb)  => cb(null, uniqueName(file.originalname)),
});

const upload = multer({
    storage,
    limits: { fileSize: 20 * 1024 * 1024 }, // 20 MB
    fileFilter: (_req, file, cb) => {
        if (ALLOWED_TYPES.has(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error(`Unsupported file type: ${file.mimetype}. Allowed: JPEG, PNG, WEBP, GIF`));
        }
    },
});

// ── Helper: build the public URL for an uploaded file ─────────────────────
function buildPublicUrl(req, filename) {
    // Prefer explicit PUBLIC_BASE_URL env var (set on VPS to https://api.pawgrammers.io.vn)
    // Falls back to request origin for local dev
    const base = process.env.PUBLIC_BASE_URL
        || `${req.protocol}://${req.get('host')}`;
    return `${base}/uploads/${filename}`;
}

// ── POST /api/creative/upload  (multipart) ─────────────────────────────────
// Field name: "file" (single image)
// Returns: { ok, url, filename, size, mimeType }
router.post('/upload', upload.single('file'), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: 'No file received. Send as multipart field "file".' });
    }

    const url = buildPublicUrl(req, req.file.filename);

    console.log(`[Creative] Uploaded: ${req.file.filename} (${(req.file.size / 1024).toFixed(1)} KB)`);

    res.status(201).json({
        ok:       true,
        url,
        filename: req.file.filename,
        size:     req.file.size,
        mimeType: req.file.mimetype,
    });
});

// ── POST /api/creative/upload-base64  (JSON body) ──────────────────────────
// Body: { base64: "<data>", filename?: "banner.jpg", mimeType?: "image/jpeg" }
// Used by AI agent passing image bytes from image generation API
// Returns: { ok, url, filename, size }
router.post('/upload-base64', (req, res) => {
    const { base64, filename: rawName, mimeType } = req.body || {};

    if (!base64) {
        return res.status(400).json({ error: '"base64" field is required.' });
    }

    // Strip data URI prefix if present: "data:image/png;base64,<data>"
    const cleaned = base64.replace(/^data:[^;]+;base64,/, '');

    // Validate the base64 string is non-empty
    if (!cleaned || cleaned.length < 10) {
        return res.status(400).json({ error: 'base64 field appears empty or invalid.' });
    }

    // Determine file extension from provided mimeType or filename
    let ext = '.jpg';
    if (mimeType && ALLOWED_TYPES.has(mimeType)) {
        ext = { 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif' }[mimeType] || '.jpg';
    } else if (rawName) {
        const candidate = path.extname(rawName).toLowerCase();
        if (ALLOWED_EXTENSIONS.has(candidate)) ext = candidate;
    }

    const filename = uniqueName(`upload${ext}`);
    const filepath = path.join(UPLOADS_DIR, filename);

    let buffer;
    try {
        buffer = Buffer.from(cleaned, 'base64');
    } catch (e) {
        return res.status(400).json({ error: 'Invalid base64 encoding.' });
    }

    // Enforce 20 MB raw size limit
    const MAX_BYTES = 20 * 1024 * 1024;
    if (buffer.length > MAX_BYTES) {
        return res.status(413).json({
            error: `File too large: ${(buffer.length / 1024 / 1024).toFixed(1)} MB. Maximum is 20 MB.`
        });
    }

    fs.writeFile(filepath, buffer, (err) => {
        if (err) {
            console.error('[Creative] Write failed:', err);
            return res.status(500).json({ error: 'Failed to save file to disk.' });
        }

        const url = buildPublicUrl(req, filename);
        console.log(`[Creative] Base64 upload: ${filename} (${(buffer.length / 1024).toFixed(1)} KB)`);

        res.status(201).json({
            ok:       true,
            url,
            filename,
            size:     buffer.length,
            mimeType: mimeType || 'image/jpeg',
        });
    });
});

// ── GET /api/creative/list ─────────────────────────────────────────────────
// Returns all uploaded creatives with their URLs
router.get('/list', (req, res) => {
    fs.readdir(UPLOADS_DIR, (err, files) => {
        if (err) return res.status(500).json({ error: err.message });

        const items = files
            .filter(f => ALLOWED_EXTENSIONS.has(path.extname(f).toLowerCase()))
            .map(f => {
                const stat = fs.statSync(path.join(UPLOADS_DIR, f));
                return {
                    filename:  f,
                    url:       buildPublicUrl(req, f),
                    size:      stat.size,
                    uploadedAt: stat.birthtime,
                };
            })
            .sort((a, b) => b.uploadedAt - a.uploadedAt);

        res.json({ count: items.length, files: items });
    });
});

// ── DELETE /api/creative/:filename ────────────────────────────────────────
// Remove a specific uploaded file
router.delete('/:filename', (req, res) => {
    // Sanitize: strip any path traversal
    const safe = path.basename(req.params.filename);
    const filepath = path.join(UPLOADS_DIR, safe);

    if (!fs.existsSync(filepath)) {
        return res.status(404).json({ error: `File "${safe}" not found.` });
    }

    fs.unlink(filepath, (err) => {
        if (err) return res.status(500).json({ error: err.message });
        console.log(`[Creative] Deleted: ${safe}`);
        res.json({ ok: true, deleted: safe });
    });
});

// ── Multer error handler ───────────────────────────────────────────────────
// Must be defined AFTER the routes that use multer
router.use((err, _req, res, _next) => {
    if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(413).json({
            error: 'File too large. Maximum size is 20 MB.'
        });
    }
    res.status(400).json({ error: err.message });
});

module.exports = router;
