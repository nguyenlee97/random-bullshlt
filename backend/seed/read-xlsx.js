/** Dump only zones from the portable, repository-owned workbook. */
const path = require('path');
const { readWorksheetRows } = require('./workbook-rows');

(async () => {
  const file = path.join(__dirname, 'data', 'Ads Zone.xlsx');
  const rows = await readWorksheetRows(file, 'Ad Zones');
  console.log('TOTAL ZONES:', rows.length);
  rows.forEach((row) => console.log(JSON.stringify(row)));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
