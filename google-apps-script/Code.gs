/**
 * StockLab Favorites — free Google Sheets backend.
 * Bind this script to a Google Sheet, run setup(), set a sync password, then deploy as a Web App.
 *
 * This is designed for personal bookmarks, not sensitive or regulated data.
 */
const STOCKLAB_SHEET_NAME = 'Favorites';
const STOCKLAB_HEADERS = ['user_key', 'symbol', 'name', 'note', 'created_at', 'updated_at', 'deleted'];
const STOCKLAB_PASSWORD_PROPERTY = 'STOCKLAB_SYNC_PASSWORD_SHA256';
const STOCKLAB_MAX_ITEMS = 100;

function setup() {
  const sheet = getSheet_();
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, STOCKLAB_HEADERS.length).setFontWeight('bold');
  sheet.autoResizeColumns(1, STOCKLAB_HEADERS.length);
  return 'StockLab Favorites is ready.';
}

/** Run this manually in Apps Script, e.g. setSyncPassword('a-long-random-token'). */
function setSyncPassword(value) {
  if (!value || String(value).length < 10) {
    throw new Error('同步密碼至少 10 個字元；請勿使用你的 Google 帳號密碼。');
  }
  PropertiesService.getScriptProperties().setProperty(
    STOCKLAB_PASSWORD_PROPERTY,
    sha256_(String(value))
  );
  return 'Sync password updated.';
}

function doGet(e) {
  return handleRequest_(e && e.parameter ? e.parameter : {});
}

function doPost(e) {
  let params = e && e.parameter ? Object.assign({}, e.parameter) : {};
  try {
    if (e && e.postData && e.postData.contents) {
      params = Object.assign(params, JSON.parse(e.postData.contents));
    }
  } catch (error) {
    return respond_({ ok: false, error: 'Invalid JSON body.' }, params.callback);
  }
  return handleRequest_(params);
}

function handleRequest_(params) {
  const callback = sanitizeCallback_(params.callback);
  try {
    authenticate_(params.password);
    const action = String(params.action || 'ping').toLowerCase();
    const userKey = sanitizeText_(params.user_key || '', 80);
    if (!userKey && action !== 'ping') {
      throw new Error('Missing user_key.');
    }

    if (action === 'ping') {
      return respond_({ ok: true, message: 'StockLab Google Sheets backend is ready.' }, callback);
    }
    if (action === 'list') {
      const includeDeleted = String(params.include_deleted || '').toLowerCase() === '1' || String(params.include_deleted || '').toLowerCase() === 'true';
      return respond_({ ok: true, items: listFavorites_(userKey, includeDeleted) }, callback);
    }
    if (action === 'add') {
      const item = upsertFavorite_(userKey, params);
      return respond_({ ok: true, item: item }, callback);
    }
    if (action === 'remove') {
      const symbol = sanitizeSymbol_(params.symbol);
      removeFavorite_(userKey, symbol);
      return respond_({ ok: true, symbol: symbol }, callback);
    }
    throw new Error('Unsupported action: ' + action);
  } catch (error) {
    return respond_({ ok: false, error: String(error && error.message ? error.message : error) }, callback);
  }
}

function getSheet_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) throw new Error('This Apps Script must be bound to a Google Sheet.');
  let sheet = spreadsheet.getSheetByName(STOCKLAB_SHEET_NAME);
  if (!sheet) sheet = spreadsheet.insertSheet(STOCKLAB_SHEET_NAME);
  const firstRow = sheet.getRange(1, 1, 1, STOCKLAB_HEADERS.length).getValues()[0];
  if (firstRow.join('|') !== STOCKLAB_HEADERS.join('|')) {
    sheet.getRange(1, 1, 1, STOCKLAB_HEADERS.length).setValues([STOCKLAB_HEADERS]);
  }
  return sheet;
}

function authenticate_(password) {
  const expected = PropertiesService.getScriptProperties().getProperty(STOCKLAB_PASSWORD_PROPERTY);
  if (!expected) throw new Error('Run setSyncPassword(...) before deploying.');
  const actual = sha256_(String(password || ''));
  if (actual !== expected) throw new Error('Invalid sync password.');
}

function listFavorites_(userKey, includeDeleted) {
  const sheet = getSheet_();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  const values = sheet.getRange(2, 1, lastRow - 1, STOCKLAB_HEADERS.length).getValues();
  return values
    .filter(row => String(row[0]) === userKey)
    .map(row => ({
      symbol: String(row[1]),
      name: String(row[2]),
      note: String(row[3]),
      created_at: dateToIso_(row[4]),
      updated_at: dateToIso_(row[5]),
      deleted: String(row[6]).toLowerCase() === 'true'
    }))
    .filter(item => includeDeleted || !item.deleted)
    .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))
    .slice(0, includeDeleted ? STOCKLAB_MAX_ITEMS * 2 : STOCKLAB_MAX_ITEMS);
}

function upsertFavorite_(userKey, params) {
  const symbol = sanitizeSymbol_(params.symbol);
  const name = safeCell_(sanitizeText_(params.name || '', 100));
  const note = safeCell_(sanitizeText_(params.note || '', 500));
  if (!symbol) throw new Error('Missing symbol.');

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = getSheet_();
    const now = new Date();
    const lastRow = sheet.getLastRow();
    if (lastRow >= 2) {
      const values = sheet.getRange(2, 1, lastRow - 1, STOCKLAB_HEADERS.length).getValues();
      for (let index = 0; index < values.length; index++) {
        if (String(values[index][0]) === userKey && String(values[index][1]) === symbol) {
          const created = values[index][4] || now;
          sheet.getRange(index + 2, 1, 1, STOCKLAB_HEADERS.length).setValues([
            [userKey, symbol, name, note, created, now, false]
          ]);
          return { symbol: symbol, name: name, note: note, created_at: dateToIso_(created), updated_at: now.toISOString() };
        }
      }
    }

    const activeCount = listFavorites_(userKey).length;
    if (activeCount >= STOCKLAB_MAX_ITEMS) throw new Error('Favorites limit reached (' + STOCKLAB_MAX_ITEMS + ').');
    sheet.appendRow([userKey, symbol, name, note, now, now, false]);
    return { symbol: symbol, name: name, note: note, created_at: now.toISOString(), updated_at: now.toISOString() };
  } finally {
    lock.releaseLock();
  }
}

function removeFavorite_(userKey, symbol) {
  if (!symbol) throw new Error('Missing symbol.');
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = getSheet_();
    const lastRow = sheet.getLastRow();
    if (lastRow < 2) return;
    const values = sheet.getRange(2, 1, lastRow - 1, STOCKLAB_HEADERS.length).getValues();
    for (let index = 0; index < values.length; index++) {
      if (String(values[index][0]) === userKey && String(values[index][1]) === symbol) {
        sheet.getRange(index + 2, 6, 1, 2).setValues([[new Date(), true]]);
        return;
      }
    }
  } finally {
    lock.releaseLock();
  }
}

function respond_(payload, callback) {
  const json = JSON.stringify(payload);
  const body = callback ? callback + '(' + json + ');' : json;
  const mime = callback ? ContentService.MimeType.JAVASCRIPT : ContentService.MimeType.JSON;
  return ContentService.createTextOutput(body).setMimeType(mime);
}

function sanitizeCallback_(value) {
  const callback = String(value || '');
  return /^[A-Za-z_$][0-9A-Za-z_$.]{0,100}$/.test(callback) ? callback : '';
}

function sanitizeSymbol_(value) {
  return String(value || '').trim().replace(/[^0-9A-Za-z.^_-]/g, '').slice(0, 24);
}

function sanitizeText_(value, maxLength) {
  return String(value || '').replace(/[\u0000-\u001F\u007F]/g, ' ').trim().slice(0, maxLength);
}

function safeCell_(value) {
  return /^[=+\-@]/.test(value) ? "'" + value : value;
}

function sha256_(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, value, Utilities.Charset.UTF_8);
  return bytes.map(byte => ('0' + ((byte + 256) % 256).toString(16)).slice(-2)).join('');
}

function dateToIso_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) return value.toISOString();
  return String(value || '');
}
