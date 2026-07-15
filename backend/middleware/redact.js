const SENSITIVE_KEYS = /^(authorization|api[-_]?key|token|secret|password|cookie|dataUrl|base64|imageData|fileContent)$/i;
const EMAIL = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const PHONE = /(?<!\d)(?:\+?84|0)(?:\d[ .-]?){8,10}(?!\d)/g;
const CCCD = /(?<!\d)\d{12}(?!\d)/g;
const BEARER = /\bBearer\s+[A-Za-z0-9._-]{12,}/gi;
const MONGO_CREDENTIALS = /(mongodb(?:\+srv)?:\/\/)[^\s:/@]+:[^\s/@]+@/gi;

function redactText(value) {
  return String(value)
    .replace(MONGO_CREDENTIALS, '$1[REDACTED]@')
    .replace(BEARER, 'Bearer [REDACTED]')
    .replace(EMAIL, '[REDACTED_EMAIL]')
    .replace(PHONE, '[REDACTED_PHONE]')
    .replace(CCCD, '[REDACTED_CCCD]');
}

function redact(value, depth = 0) {
  if (depth > 8) return '[TRUNCATED]';
  if (typeof value === 'string') return redactText(value).slice(0, 4000);
  if (Array.isArray(value)) return value.slice(0, 100).map((item) => redact(item, depth + 1));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
      key,
      SENSITIVE_KEYS.test(key) ? '[REDACTED]' : redact(item, depth + 1),
    ]));
  }
  return value;
}

module.exports = { redact, redactText };
