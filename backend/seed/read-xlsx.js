/** Dump only zones (all 26) */
const xlsx = require('xlsx');
const wb = xlsx.readFile('C:\\Users\\LENOVO\\Downloads\\Ads Zone.xlsx');
const rows = xlsx.utils.sheet_to_json(wb.Sheets['Ad Zones'], { defval: null });
console.log('TOTAL ZONES:', rows.length);
rows.forEach((r) => console.log(JSON.stringify(r)));
