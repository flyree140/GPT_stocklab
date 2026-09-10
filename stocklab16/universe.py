from __future__ import annotations
import json, urllib.request
from .common import ROOT,now,read_json,write_json

def _get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'StockLab16'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode('utf-8'))

def refresh():
    rows=[]
    try:
        for r in _get('https://openapi.twse.com.tw/v1/opendata/t187ap03_L'):
            code=str(r.get('公司代號') or '').strip(); name=str(r.get('公司簡稱') or r.get('公司名稱') or '').strip()
            if code and name:rows.append({'symbol':code+'.TW','code':code,'name':name,'market':'上市','sector':str(r.get('產業別') or '')})
    except Exception as exc:print('TWSE universe unavailable',exc)
    for url in ['https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O','https://www.tpex.org.tw/openapi/v1/tpex_mainboard_company_basic']:
        try:
            data=_get(url)
            for r in data:
                code=str(r.get('公司代號') or r.get('SecuritiesCompanyCode') or '').strip(); name=str(r.get('公司簡稱') or r.get('公司名稱') or r.get('CompanyAbbreviation') or r.get('CompanyName') or '').strip()
                if code and name:rows.append({'symbol':code+'.TWO','code':code,'name':name,'market':'上櫃','sector':str(r.get('產業別') or r.get('IndustryCategory') or '')})
            if data:break
        except Exception as exc:print('TPEX universe endpoint unavailable',exc)
    core=read_json(ROOT/'config'/'stocks.json',{}).get('stocks',[]); rows.extend({'symbol':r['symbol'],'code':r['symbol'].split('.')[0],'name':r['name'],'market':'核心','sector':r.get('sector','')} for r in core)
    ded={r['symbol']:r for r in rows}; payload={'version':'16.0','generated_at':now().isoformat(timespec='seconds'),'count':len(ded),'instruments':sorted(ded.values(),key=lambda x:x['symbol'])}
    if ded:write_json(ROOT/'data'/'universe.json',payload)
    return payload

if __name__=='__main__':print('universe',refresh()['count'])
