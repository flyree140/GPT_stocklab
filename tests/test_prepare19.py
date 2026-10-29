from datetime import datetime
from zoneinfo import ZoneInfo
from stocklab18.prepare import parse_twse_dated
from stocklab16.preflight import already_completed

def test_dated_official_missing_date_is_rejected():
    assert parse_twse_dated({'fields':['證券代號','收盤價'],'data':[['2881','100']]},'2026-10-20')=={}

def test_dated_official_mismatch_rejected():
    assert parse_twse_dated({'date':'20261019','fields':['證券代號','收盤價'],'data':[['2881','100']]},'2026-10-20')=={}

def test_dated_nested_tables():
    p={'date':'1151020','tables':[{'fields':['證券代號','證券名稱','收盤價'],'data':[['2881','測試','100.50'],['2330','測試','--']]}]}
    assert parse_twse_dated(p,'2026-10-20')['2881.TW']['close']==100.5

def test_old_numbered_tables():
    p={'date':'20261020','fields9':['證券代號','收盤價'],'data9':[['2881','NaN'],['2330','1,000']]}
    assert list(parse_twse_dated(p,'2026-10-20'))==['2330.TW']

def test_evening_window_not_skipped_after_first_run():
    s={'mode':'live','stocks':[{}],'as_of':'2026-10-20','generated_at':'2026-10-20T18:50:00+08:00'}
    assert not already_completed(s,'17 13 * * *',datetime(2026,10,20,21,17,tzinfo=ZoneInfo('Asia/Taipei')))
    assert already_completed(s,'37 10 * * *',datetime(2026,10,20,19,tzinfo=ZoneInfo('Asia/Taipei')))

def test_completed_night_skips_repeat_same_window():
    s={'mode':'live','stocks':[{}],'as_of':'2026-10-20','generated_at':'2026-10-20T21:50:00+08:00'}
    assert already_completed(s,'17 13 * * *',datetime(2026,10,20,22,tzinfo=ZoneInfo('Asia/Taipei')))
