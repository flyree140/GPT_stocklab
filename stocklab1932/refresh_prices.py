"""Bounded complete-day OHLC refresh; independent of news/Qwen.

19.3.3: as_of is the requested date, NOT proof that its daily bar exists.
Only the actual last valid bar determines freshness. Never publishes private
browser batches, synthetic substitutes, or partially formed daily candles.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os, json, time, re
from stocklab16.market import history
from stocklab17.hygiene import clean_bars
from stocklab17.calendar import expected_close, covered, SEED
from .developer import read
from .collection import write

TZ = ZoneInfo('Asia/Taipei')
SYMBOL = re.compile(r'^[0-9A-Za-z^-]{1,16}\.(?:TW|TWO)$')


def calendar_for(root):
    for rel in ('config/market-calendar.json', 'data/calendar/latest.json', 'assets/paper-calendar.json'):
        c = read(Path(root) / rel, {}) or {}
        if all(k in c for k in ('start', 'end', 'closed')):
            return c
    return SEED


def last_valid(payload, now, cal):
    rows = [b for b in payload.get('candles', []) if b.get('is_final') is not False and not b.get('provisional')]
    clean, _ = clean_bars(rows, cutoff=now.isoformat(), calendar=cal)
    return clean[-1]['date'] if clean else None


def run(root, fetcher=history, *, current=None, sleep_fn=time.sleep, monotonic=time.monotonic):
    root = Path(root)
    now = current or datetime.now(TZ)
    if now.tzinfo is None:
        raise ValueError('refresh current must include a timezone')
    now = now.astimezone(TZ)
    cal = calendar_for(root)
    day = now.date().isoformat()
    if not covered(day, cal):
        report = {'version': '19.3.3', 'at': now.isoformat(), 'timezone': 'Asia/Taipei',
                  'state': 'calendar_missing', 'message': '交易日曆未涵蓋 ' + day,
                  'required_close_date': None, 'updated': [], 'failed': [], 'by_symbol': {},
                  'no_model_calls': True}
        write(root / 'data/developer1932/price_refresh.json', report)
        return report
    required = expected_close(now.isoformat(), cal)
    wanted = {'0050.TW'}
    for p in (root / 'data/developer1932/signals').glob('*.json'):
        r = read(p, {}) or {}
        if not r.get('demo'):
            wanted.update(x.get('symbol') for x in r.get('rows', []))
    latest = read(root / 'data/latest.json', {}) or {}
    if not latest.get('demo'):
        wanted.update(s.get('symbol') for s in latest.get('stocks', []))
    # Older trial holdings may not be in the newest rotating research pool.
    for p in (root / 'data/market').glob('*.json'):
        old = read(p, {}) or {}
        if not old.get('demo'):
            wanted.add(old.get('symbol'))
    wanted = sorted(s for s in wanted if isinstance(s, str) and SYMBOL.fullmatch(s))
    existing, needed, status = {}, [], {}
    for symbol in wanted:
        old = read(root / 'data/market' / f"{symbol.replace('.', '_')}.json", {}) or {}
        existing[symbol] = old
        last = last_valid(old, now, cal)
        fresh = bool(last and last >= required)
        status[symbol] = {'state': 'fresh' if fresh else 'queued', 'latest_complete_date': last,
                          'required_close_date': required, 'fetch_requested_as_of': old.get('as_of'),
                          'message': '完整日K已到需要日期' if fresh else '待補完整日K，as_of不作為已更新證明'}
        if not fresh:
            needed.append((last or '', symbol))
    cap = max(0, min(80, int(os.getenv('PRICE_REFRESH_LIMIT', '40'))))
    seconds = max(30, min(1200, int(os.getenv('PRICE_REFRESH_SECONDS', '900'))))
    started = monotonic()
    selected = sorted(needed)[:cap]
    updated, failed, attempted, quarantined = [], [], [], 0
    for _, symbol in selected:
        if monotonic() - started >= seconds:
            break
        attempted.append(symbol)
        try:
            rows = fetcher(symbol, day, 180)
            if not rows:
                raise ValueError('來源沒有傳回可用日K；保留原檔，不製造成交')
            clean_new, bad = clean_bars(rows, cutoff=now.isoformat(), calendar=cal)
            # Be conservative if a provider explicitly marks a provisional candle.
            provisional = [x for x in clean_new if x.get('is_final') is False or x.get('provisional')]
            clean_new = [x for x in clean_new if not (x.get('is_final') is False or x.get('provisional'))]
            bad.extend({'date': x['date'], 'reason': 'provisional_bar', 'bar': x} for x in provisional)
            if bad:
                quarantined += len(bad)
                write(root / 'data/quarantine' / f"{symbol.replace('.', '_')}.json", bad)
            merged = {b['date']: b for b in existing[symbol].get('candles', [])
                      if b.get('is_final') is not False and not b.get('provisional')}
            merged.update({b['date']: b for b in clean_new})
            clean, old_bad = clean_bars(list(merged.values()), cutoff=now.isoformat(), calendar=cal)
            if not clean_new or not clean:
                raise ValueError('此次沒有完整有效的新日K；原檔保留')
            last = clean[-1]['date']
            # Preserve metadata. No headline or frozen forecast is rewritten here.
            payload = {**existing[symbol], 'symbol': symbol, 'as_of': day, 'candles': clean,
                       'latest_complete_date': last, 'refreshed_at': now.isoformat(),
                       'price_only_no_llm': True, 'intraday_execution_supported': False}
            write(root / 'data/market' / f"{symbol.replace('.', '_')}.json", payload)
            state = 'updated' if last >= required else 'source_lag'
            status[symbol].update(state=state, latest_complete_date=last, refreshed_at=now.isoformat(),
                                  message='取得所需完整日K' if state == 'updated' else '來源仍未公布所需日期；不是沒試單')
            if state == 'updated':
                updated.append(symbol)
            else:
                failed.append({'symbol': symbol, 'reason': status[symbol]['message'], 'latest_complete_date': last})
        except Exception as exc:
            msg = f'{type(exc).__name__}: {str(exc)[:280]}'
            status[symbol].update(state='source_error', message=msg)
            failed.append({'symbol': symbol, 'reason': msg})
        sleep_fn(.2)
    pending = sum(s['state'] == 'queued' for s in status.values())
    report = {'version': '19.3.3', 'at': now.isoformat(), 'timezone': 'Asia/Taipei',
              'state': 'complete' if not failed and not pending else 'partial',
              'required_close_date': required, 'research_generated_at': latest.get('generated_at'),
              'tracked_symbols': len(wanted), 'limit': cap, 'attempted': len(attempted),
              'updated': updated, 'already_fresh': sum(s['state'] == 'fresh' for s in status.values()),
              'failed': failed, 'queued': pending, 'quarantined': quarantined,
              'by_symbol': status, 'no_fake_forward_fill': True, 'no_model_calls': True,
              'intraday_execution_supported': False,
              'note': '盤中檢查只修補已收盤資料；不宣稱即時報價或即時成交。'}
    write(root / 'data/developer1932/price_refresh.json', report)
    return report


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    a = p.parse_args()
    print(json.dumps(run(a.root), ensure_ascii=False))
