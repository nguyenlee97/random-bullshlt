'use strict';

const fs = require('fs');
const path = require('path');

const dir = __dirname;
const data = fs.readFileSync(path.join(dir, 'report-data.json'), 'utf8');
const template = fs.readFileSync(path.join(dir, 'template.html'), 'utf8');
const safeJson = data.replace(/</g, '\\u003c');
const html = template.replace('__REPORT_DATA__', safeJson);

if (html === template) {
  throw new Error('Missing __REPORT_DATA__ placeholder in template.html');
}

fs.writeFileSync(path.join(dir, 'index.html'), html, 'utf8');
console.log(`Built ${path.join(dir, 'index.html')}`);
