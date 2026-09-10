from stocklab16.events import analyze,aggregate
META={'symbol':'2412.TW','name':'中華電','aliases':['中華電信']}
def test_promotion_not_profit_signal():
    item={'title':'中華電聯名卡贈500點','excerpt':'活動提供 Hami Point 回饋','published_at':'2026-09-08T10:00:00+08:00','available_at':'2026-09-08T10:00:00+08:00','url':'','publisher':'demo'}
    e=analyze(item,META,'2026-09-08T23:59:00+08:00')
    assert e['category']=='promotion' and e['impact_score']==0
    assert '補貼' in e['risk']
def test_static_profile_excluded():
    item={'title':'中華電(2412) 個股概覽','published_at':'2026-09-08T10:00:00+08:00','available_at':'2026-09-08T10:00:00+08:00','url':'','publisher':'demo'}
    e=analyze(item,META,'2026-09-08T23:59:00+08:00')
    assert not e['included']
    assert aggregate([e])['score'] is None
