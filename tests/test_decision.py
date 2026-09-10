from stocklab16.decision import decide

def test_missing_data_does_not_become_buy():
    stock={'kind':'stock','candles':[],'news':[],'facts':{},'market_score':None}
    d=decide(stock,'2026-09-10')
    assert d['code']=='insufficient'
