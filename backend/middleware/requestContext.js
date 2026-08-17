const { randomUUID } = require('crypto');

const SAFE_REQUEST_ID = /^[A-Za-z0-9._:-]{1,64}$/;

function requestContext(req, res, next) {
  const supplied = req.get('X-Request-Id') || '';
  req.requestId = SAFE_REQUEST_ID.test(supplied) ? supplied : randomUUID().replaceAll('-', '').slice(0, 16);
  res.set('X-Request-Id', req.requestId);
  next();
}

module.exports = { requestContext };
