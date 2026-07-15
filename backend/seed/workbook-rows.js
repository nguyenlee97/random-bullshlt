const ExcelJS = require('exceljs');

function cellValue(cell) {
  const value = cell.value;
  if (value && typeof value === 'object') {
    if (Object.prototype.hasOwnProperty.call(value, 'result')) return value.result;
    if (Object.prototype.hasOwnProperty.call(value, 'text')) return value.text;
    if (Array.isArray(value.richText)) return value.richText.map((part) => part.text).join('');
  }
  return value ?? null;
}

async function readWorksheetRows(filename, worksheetName) {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filename);
  const worksheet = workbook.getWorksheet(worksheetName);
  if (!worksheet) throw new Error(`Worksheet not found: ${worksheetName}`);

  const headers = [];
  worksheet.getRow(1).eachCell({ includeEmpty: true }, (cell, column) => {
    headers[column] = String(cellValue(cell) ?? '').trim();
  });

  const rows = [];
  worksheet.eachRow((row, rowNumber) => {
    if (rowNumber === 1) return;
    const record = {};
    let populated = false;
    headers.forEach((header, column) => {
      if (!header) return;
      const value = cellValue(row.getCell(column));
      record[header] = value;
      if (value !== null && value !== '') populated = true;
    });
    if (populated) rows.push(record);
  });
  return rows;
}

module.exports = { readWorksheetRows };
