const ApiLog = require('../models/ApiLog');

/**
 * Express middleware that fires AFTER route handlers to log every API call.
 * We capture the response by monkey-patching res.json.
 */
function logRequest(req, res, next) {
  const originalJson = res.json.bind(res);

  res.json = function (body) {
    // Prune log to keep last 1000 entries
    ApiLog.countDocuments()
      .then((count) => {
        if (count > 1000) {
          return ApiLog.find({}, { _id: 1 })
            .sort({ ts: 1 })
            .limit(count - 1000)
            .then((old) => ApiLog.deleteMany({ _id: { $in: old.map((d) => d._id) } }));
        }
      })
      .catch(() => {});

    // Store log entry (non-blocking)
    ApiLog.create({
      method:  req.method,
      path:    req.path,
      query:   Object.keys(req.query).length ? req.query : null,
      body:    req.method !== 'GET' ? (req.body || null) : null,
      status:  res.statusCode,
      resBody: typeof body === 'object' ? body : null,
      ip:      req.ip,
    }).catch(() => {});

    return originalJson(body);
  };

  next();
}

module.exports = { logRequest };
