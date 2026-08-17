const crypto = require('crypto');
const path = require('path');

function deterministicUploadFilename(idempotencyKey, originalname) {
  const key = String(idempotencyKey || '').trim();
  if (!key) return '';
  const ext = path.extname(originalname || '').toLowerCase() || '.jpg';
  const digest = crypto.createHash('sha256').update(key).digest('hex').slice(0, 24);
  return `creative_upload_${digest}${ext}`;
}

module.exports = {
  deterministicUploadFilename,
};
