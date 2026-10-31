"""Optional independent CPU classifier; NO Qwen base, no returns or trade decisions.
Trains reviewed chronological splits; exports JSON weights, not executable pickle.
User must still verify class errors. Raw logits are not calibrated probabilities.
"""
import json
from pathlib import Path
from stocklab192.schema import load_jsonl,digest
from stocklab192.train import validate_parts

def text(r):return '\n'.join(d['text'] for d in r['documents'])
def fit(data_dir,out,allow_synthetic=False):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score,classification_report
    p=Path(data_dir);parts={k:load_jsonl(p/(k+'.jsonl')) for k in ('train','validation','test')}
    validate_parts(parts,allow_synthetic=allow_synthetic)
    classes={r['gold']['category'] for r in parts['train']}
    if len(classes)<2:raise ValueError('至少需要兩種事件標籤；不自動造資料')
    vec=TfidfVectorizer(analyzer='char',ngram_range=(2,4),max_features=12000,sublinear_tf=True)
    x=vec.fit_transform([text(r) for r in parts['train']]);y=[r['gold']['category'] for r in parts['train']]
    clf=LogisticRegression(max_iter=300,random_state=42,class_weight='balanced').fit(x,y)
    truth=[r['gold']['category'] for r in parts['validation']];pred=clf.predict(vec.transform([text(r) for r in parts['validation']]))
    result={'version':'19.3-cpu-text-1','model':'char-tfidf-logistic','task':'event_category_only',
        'synthetic_smoke_only':allow_synthetic,'Qwen_required':False,'profitability_validated':False,
        'vocabulary':{k:int(v) for k,v in vec.vocabulary_.items()},'idf':vec.idf_.tolist(),'coef':clf.coef_.tolist(),'intercept':clf.intercept_.tolist(),
        'classes':clf.classes_.tolist(),'data_hashes':{k:digest(v) for k,v in parts.items()},
        'validation':{'n':len(truth),'macro_f1':f1_score(truth,pred,average='macro',zero_division=0),
          'class_report':classification_report(truth,pred,output_dict=True,zero_division=0)},
        'note':'不產生分析文章、價格、股數；未校準分數不是上漲機率。未接入正式評分。'}
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

def predict(model_file,texts):
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    m=json.loads(Path(model_file).read_text());v=TfidfVectorizer(analyzer='char',ngram_range=(2,4),sublinear_tf=True,vocabulary=m['vocabulary'])
    v.idf_=np.array(m['idf']);scores=v.transform(texts)@np.array(m['coef']).T+np.array(m['intercept'])
    if len(m['classes'])==2:labels=np.where(scores[:,0]>0,1,0)
    else:labels=np.argmax(scores,axis=1)
    return [{'category':m['classes'][int(i)],'raw_scores':s.tolist(),'not_calibrated_probability':True} for i,s in zip(labels,scores)]
