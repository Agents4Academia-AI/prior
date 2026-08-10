/**
 * Prior — gold-set labelling app (Google Apps Script, bound to the labelling Sheet).
 *
 * ONE tab: `sites` — 809 rows sorted by queue_rank, header in row 1.
 *
 * MULTI-LABELLER. Each labeller writes into their OWN prefixed columns, so nobody can
 * overwrite anyone else. Who you are comes from the `?who=` URL parameter:
 *
 *     .../exec?who=callum   ->  gold_intent, gold_support, gold_priority, gold_notes   (all 809)
 *     .../exec?who=h        ->  H_gold_intent, H_gold_support, …                       (random_eval only)
 *     .../exec?who=k        ->  K_gold_intent, K_gold_support, …                       (random_eval only)
 *
 * Columns are found BY HEADER NAME, so you can reorder/insert columns in the sheet freely.
 * Add a labeller = add a row to LABELLERS below + the four columns to the sheet.
 *
 * The browser NEVER receives judge_*, edge_*, sj_* or sample_type — the payload is built
 * field by field in payloadAt_(), so labelling stays blind. That is also why the
 * deployment must stay "Execute as: ME": labellers then never need access to the
 * spreadsheet itself, where the judge columns are in plain sight.
 *
 * Deploy: Deploy > New deployment > Web app
 *         Execute as: ME  ·  Who has access: ANYONE WITH A GOOGLE ACCOUNT
 */

var TAB = 'sites';
var SKIP = 'SKIP';                // gold_intent value meaning "passed on this one"

var LABELLERS = {
  callum: { prefix: '',   name: 'Callum',     scope: 'all' },
  h:      { prefix: 'H_', name: 'Labeller H', scope: 'random_eval' },
  k:      { prefix: 'K_', name: 'Labeller K', scope: 'random_eval' }
};

var FIELDS = ['intent', 'support', 'priority', 'notes'];

// ── plumbing ──────────────────────────────────────────────────────────────

function doGet(e) {
  var raw = (e && e.parameter && e.parameter.who) ? String(e.parameter.who).toLowerCase() : '';
  var t = HtmlService.createTemplateFromFile('Index');
  t.who = raw.replace(/[^a-z0-9_]/g, '');   // sanitise before it reaches the page
  return t.evaluate()
    .setTitle('Prior — gold labelling')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1');
}

/** For the "who are you?" chooser when no ?who= was supplied. */
function getLabellers() {
  return Object.keys(LABELLERS).map(function (k) {
    return { id: k, name: LABELLERS[k].name, scope: LABELLERS[k].scope };
  });
}

function cfg_(who) {
  var c = LABELLERS[String(who || '').toLowerCase()];
  if (!c) throw new Error('Unknown labeller "' + who + '". Use the link you were sent, ' +
                          'which ends in ?who=' + Object.keys(LABELLERS).join(' / ?who='));
  return c;
}

function sh_() {
  var s = SpreadsheetApp.getActive().getSheetByName(TAB);
  if (!s) throw new Error('Missing tab: ' + TAB);
  return s;
}

/** header name -> 1-based column index */
function cols_(sheet) {
  var head = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0], m = {};
  for (var i = 0; i < head.length; i++) m[String(head[i]).trim()] = i + 1;
  return m;
}

function colValues_(sheet, colIdx) {
  var n = sheet.getLastRow() - 1;
  return n < 1 ? [] : sheet.getRange(2, colIdx, n, 1).getValues().map(function (r) { return r[0]; });
}

function need_(c, name) {
  if (!c[name]) throw new Error('Missing column "' + name + '" — add it to row 1 of the `' +
                                TAB + '` tab (the header spelling must match exactly).');
  return c[name];
}

/**
 * The rows this labeller works through, in queue order.
 * Returns [{row, v}] where v is their current label. 3 column reads, no abstracts.
 */
function index_(sheet, c, cfg) {
  var types = colValues_(sheet, need_(c, 'sample_type'));
  var mine = colValues_(sheet, need_(c, cfg.prefix + 'gold_intent'));
  var out = [];
  for (var i = 0; i < types.length; i++) {
    if (cfg.scope !== 'all' && String(types[i]).trim() !== cfg.scope) continue;
    out.push({ row: i + 2, v: String(mine[i]).trim() });
  }
  return out;
}

// ── read API ──────────────────────────────────────────────────────────────

/** Full payload for position `pos` (0-based) in this labeller's queue. */
function payloadAt_(who, pos) {
  var cfg = cfg_(who), s = sh_(), c = cols_(s);
  var idx = index_(s, c, cfg);
  if (!idx.length) {
    throw new Error('No rows in scope for ' + cfg.name + ' (looked for sample_type="' +
                    cfg.scope + '")');
  }
  pos = Math.max(0, Math.min(Number(pos) || 0, idx.length - 1));

  var v = s.getRange(idx[pos].row, 1, 1, s.getLastColumn()).getValues()[0];
  var g = function (name) { return c[name] ? String(v[c[name] - 1]) : ''; };

  var done = 0, skipped = 0;
  for (var i = 0; i < idx.length; i++) {
    if (idx[i].v === SKIP) skipped++; else if (idx[i].v) done++;
  }

  var existing = {};
  FIELDS.forEach(function (f) { existing[f] = g(cfg.prefix + 'gold_' + f); });

  return {
    who: who, labeller: cfg.name,
    pos: pos, num: pos + 1, total: idx.length,
    site_key: g('site_key'),
    cite_key: g('cite_key'),
    site_idx: Number(g('site_idx')) + 1,
    n_sites: Number(g('n_sites_on_edge')),
    claim: g('claim'),
    citing: { title: g('citing_title'), year: g('citing_year'),
              authors: g('citing_authors'), abstract: g('citing_abstract') },
    cited: { title: g('cited_title'), year: g('cited_year'),
             authors: g('cited_authors'), abstract: g('cited_abstract') },
    existing: existing,
    state: { labelled: done, skipped: skipped, total: idx.length }
  };
}

function getSite(who, pos) {
  return payloadAt_(who, pos);
}

/** First position after `afterPos` with no label; wraps to the first gap if none follow. */
function nextOpen(who, afterPos) {
  var cfg = cfg_(who), s = sh_(), c = cols_(s);
  var idx = index_(s, c, cfg);
  var from = Number(afterPos);
  for (var i = from + 1; i < idx.length; i++) if (!idx[i].v) return payloadAt_(who, i);
  for (var j = 0; j < idx.length; j++) if (!idx[j].v) return payloadAt_(who, j);
  return payloadAt_(who, Math.min(from + 1, idx.length - 1));
}

/** Where this labeller should resume. */
function getStart(who) {
  var cfg = cfg_(who), s = sh_(), c = cols_(s);
  var idx = index_(s, c, cfg);
  for (var i = 0; i < idx.length; i++) if (!idx[i].v) return payloadAt_(who, i);
  return payloadAt_(who, 0);
}

// ── write API ─────────────────────────────────────────────────────────────

/**
 * p: {who, pos, site_key, intent, support, priority, notes}
 * Writes only this labeller's prefixed columns, then returns the next open site.
 */
function saveLabel(p) {
  var cfg = cfg_(p.who);
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var s = sh_(), c = cols_(s);
    var idx = index_(s, c, cfg);
    var pos = Math.max(0, Math.min(Number(p.pos) || 0, idx.length - 1));
    var row = idx[pos].row;
    if (String(s.getRange(row, need_(c, 'site_key')).getValue()) !== p.site_key) {
      throw new Error('row/site_key mismatch — reload the app');
    }
    FIELDS.forEach(function (f) {
      var col = c[cfg.prefix + 'gold_' + f];
      if (col) s.getRange(row, col).setValue(p[f] || '');
    });
    var rev = c[cfg.prefix + 'revision'];
    if (rev) s.getRange(row, rev).setValue((Number(s.getRange(row, rev).getValue()) || 0) + 1);
    SpreadsheetApp.flush();
  } finally {
    lock.releaseLock();
  }
  return nextOpen(p.who, p.pos);
}

/** Skip never clobbers a real label — skipping an already-labelled site just moves on. */
function skipSite(p) {
  var cfg = cfg_(p.who), s = sh_(), c = cols_(s);
  var idx = index_(s, c, cfg);
  var pos = Math.max(0, Math.min(Number(p.pos) || 0, idx.length - 1));
  if (idx[pos].v && idx[pos].v !== SKIP) return nextOpen(p.who, p.pos);
  return saveLabel({ who: p.who, pos: p.pos, site_key: p.site_key, intent: SKIP,
                     notes: p.notes || '' });
}
