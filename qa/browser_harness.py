from pathlib import Path
from urllib.parse import urlsplit
import re,json,mimetypes
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]

def mount(page,root=R,tutorial=False,requests=None):
    requests=requests if requests is not None else []
    def read(source,path):
        requests.append(path)
        rel=urlsplit(path).path.lstrip('/')
        target=(root/rel).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():return {'status':404,'body':'not found','type':'text/plain'}
        return {'status':200,'body':target.read_text(encoding='utf-8'),'type':mimetypes.guess_type(rel)[0] or 'application/json'}
    page.expose_binding('__testReadFile',read)
    page.evaluate("""() => {
      window.__testRequests=[];
      const mem=new Map();
      Object.defineProperty(window,'localStorage',{value:{getItem:k=>mem.get(k)??null,setItem:(k,v)=>mem.set(k,String(v)),removeItem:k=>mem.delete(k),clear:()=>mem.clear()},configurable:true});
      window.fetch=async input=>{const p=String(input);window.__testRequests.push(p);const v=await window.__testReadFile(p);return new Response(v.body,{status:v.status,headers:{'Content-Type':v.type}})};
      // Only navigation is unavailable in the managed offline test browser.
      // Route/history behavior is checked separately in the static-site tests.
      history.replaceState=()=>{};
    }""")
    if tutorial:
        html=(root/'tutorial.html').read_text()
        # No real network links are followed in a visual fixture.
        page.set_content(html,wait_until='domcontentloaded')
    else:
        html=(root/'index.html').read_text()
        html=re.sub(r'<link[^>]+(?:rel="stylesheet"|rel="icon")[^>]*>','',html)
        html=re.sub(r'<script type="module" src="assets/app.mjs"></script>','',html)
        page.set_content(html,wait_until='domcontentloaded')
        page.add_style_tag(content=(root/'assets/styles.css').read_text())
        page.evaluate("""async ({engine,charts,app})=>{
          const blob=s=>URL.createObjectURL(new Blob([s],{type:'text/javascript'}));
          const engineUrl=blob(engine);
          const chartUrl=blob(charts.replaceAll("'./engine.mjs'",JSON.stringify(engineUrl)));
          const appUrl=blob(app.replaceAll("'./engine.mjs'",JSON.stringify(engineUrl)).replaceAll("'./charts.mjs'",JSON.stringify(chartUrl)));
          await import(appUrl);
        }""",{k:(root/f'assets/{k}.mjs').read_text() for k in ['engine','charts','app']})
        page.wait_for_selector('.ranking-row',timeout=10000)
    return requests
