"""Map provider-observed current facts without pretending to know historical release time."""
from stocklab192.schema import timestamp

def observed_facts(stock,cutoff):
 f=stock.get('facts',{});at=f.get('available_at');out=[]
 try:
  if not at or timestamp(at)>timestamp(cutoff):return []
 except (ValueError,TypeError):return []
 for old,new in [('eps','eps_ttm'),('pe','pe'),('pb','pb'),('roe','roe_pct'),('revenue_growth_reported','revenue_yoy_pct')]:
  value=f.get(old)
  # Yahoo revenueGrowth is not necessarily the official monthly YoY. Do not mislabel it.
  if old=='revenue_growth_reported':continue
  if isinstance(value,(int,float)) and not isinstance(value,bool):out.append({'factor':'fundamental','name':new,'value':value,'available_at':at,'period':'provider-current-observed; not original filing period','source':f.get('source') or 'provider current snapshot','unit':'percent' if new.endswith('_pct') else 'provider-native'})
 return out
