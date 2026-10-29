"""Cheap CPU multi-factor return baseline, separate from language fine-tuning.
No portfolio advice or automatic strategy promotion. Real labels are required.
"""
from __future__ import annotations
import json,math,argparse
from pathlib import Path
from .schema import timestamp,digest

FEATURES=['news_verified_count','news_positive_events','news_negative_events',
 'social_attention_z','social_sentiment_balance','social_unique_authors',
 'revenue_yoy_pct','roe_pct','ocf_to_net_income','pe_peer_percentile',
 'rsi14','close_to_ma20','atr_pct','volume_ratio_previous20','return20_pct',
 'foreign_net_to_volume','trust_net_to_volume','usd_twd_change20_pct','market_return20_pct']

def partition(rows,train_end,validation_end,test_end):
    a,b,c=map(timestamp,(train_end,validation_end,test_end))
    if not a<b<c:raise ValueError('train < validation < test')
    out={k:[] for k in ('train','validation','test')};rejected=[]
    for r in rows:
        try:
            d=timestamp(r['decision_at']);entry=timestamp(r['entry_at']);end=timestamp(r['label_end_at']);avail=timestamp(r['features_available_at'])
            if not avail<=d<entry<=end:raise ValueError('unavailable features / entry must be after decision')
            if not isinstance(r['net_return_pct'],(int,float)) or not math.isfinite(r['net_return_pct']):raise ValueError('missing valid realized cost-adjusted target')
            if set(r['features'])-set(FEATURES):raise ValueError('feature not allowlisted')
            if any(v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)) for v in r['features'].values()):raise ValueError('invalid feature')
            name='train' if d<=a and end<=a else 'validation' if a<d<=b and end<=b else 'test' if b<d<=c and end<=c else None
            if not name:raise ValueError('purged overlapping/not-mature label window')
            out[name].append(r)
        except (KeyError,ValueError,TypeError) as e:rejected.append({'id':r.get('id'),'reason':str(e)})
    owners={}
    for key,rs in out.items():
        for r in rs:owners.setdefault(r['event_cluster'],set()).add(key)
    bad={g for g,parts in owners.items() if len(parts)>1}
    for key in out:
        out[key]=sorted([r for r in out[key] if r['event_cluster'] not in bad],key=lambda r:r['decision_at'])
    return out,{'rejected':rejected,'purged_shared_events':sorted(bad)}

def fit_evaluate(rows,train_end,validation_end,test_end):
    import numpy as np
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    sets,report=partition(rows,train_end,validation_end,test_end)
    if any(len(sets[k])<30 for k in sets) or len(sets['train'])<100:raise ValueError('至少100筆訓練、30筆驗證、30筆測試；不足只做資料報告，不宣稱預測')
    keys=[k for k in FEATURES if any(r['features'].get(k) is not None for r in sets['train'])]
    if not keys:raise ValueError('all factors missing')
    def xy(name):
        return np.array([[np.nan if r['features'].get(k) is None else r['features'][k] for k in keys] for r in sets[name]]),np.array([r['net_return_pct'] for r in sets[name]])
    trainx,trainy=xy('train');vx,vy=xy('validation');tx,ty=xy('test')
    model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),Ridge(alpha=10.0))
    model.fit(trainx,trainy);residual=vy-model.predict(vx);pred=model.predict(tx)
    low,med,high=np.quantile(residual,[.1,.5,.9]);lower=pred+low;upper=pred+high
    report.update({'counts':{k:len(v) for k,v in sets.items()},'features':keys,'model':'CPU Ridge alpha=10 (fixed; no test tuning)',
      'test_mae_pct_points':float(np.mean(np.abs(pred-ty))),'zero_return_baseline_mae':float(np.mean(np.abs(ty))),
      'test_direction_accuracy':float(np.mean((pred>0)==(ty>0))),
      'validation_residual_band':[float(low),float(med),float(high)],
      'test_band_coverage':float(np.mean((ty>=lower)&(ty<=upper))),
      'predictions':[{'id':r['id'],'mean_estimate_pct':float(p),'scenario_low_pct':float(l),'scenario_high_pct':float(u),'observed_pct':float(y)} for r,p,l,u,y in zip(sets['test'],pred,lower,upper,ty)],
      'dataset_sha256':digest(rows),'portfolio_performance_not_tested':True,'automatic_promotion':False,
      'limits':['重疊交易、同日股票及市場共同因子不是獨立樣本。','殘差區間不是保證信賴區間；需檢查時變及前瞻覆蓋。','沒有合格標籤時不捏造報酬。']})
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--train-end',required=True);p.add_argument('--validation-end',required=True);p.add_argument('--test-end',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    rows=[json.loads(x) for x in Path(a.input).read_text().splitlines() if x.strip()]
    result=fit_evaluate(rows,a.train_end,a.validation_end,a.test_end)
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2))
