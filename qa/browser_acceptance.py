"""Offline Chromium visual + interaction QA of actual release assets.
This environment forbids browser URL navigation. This harness uses about:blank,
file-backed fetch, blob module URLs and in-memory Storage/history adapters.
These are TEST ONLY; production assets are unmodified. No online services tested.
"""
from pathlib import Path
import argparse,json,time,sys
from playwright.sync_api import sync_playwright,expect
from browser_harness import mount

P=argparse.ArgumentParser();P.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);P.add_argument('--output',type=Path,required=True);a=P.parse_args();R=a.root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
report={'mode':'offline_dom_actual_release_files','browser':'Chromium','test_adapters':['file-backed fetch (on demand)','blob module URLs','in-memory localStorage','history.replaceState no-op'],
        'not_tested':['normal browser URL navigation (blocked by environment policy)','GitHub Actions live runner','live Qwen weights/inference','live news providers','live Google Sheets authorization'],
        'checks':[],'page_errors':[],'screenshots':[],'layouts':[],'requests':[]}
def check(name,fn):
    fn();report['checks'].append({'name':name,'passed':True});print('PASS '+name,flush=True)
def screenshot(page,name,selector=None,full=True):
    path=out/name
    page.wait_for_timeout(400)  # Let native focus/scroll settle before capture.
    if selector:page.locator(selector).screenshot(path=str(path))
    else:page.screenshot(path=str(path),full_page=full)
    report['screenshots'].append(name)
def layout(page,label):
    info=page.evaluate("""()=>({viewport:innerWidth,body:document.documentElement.scrollWidth,overflows:[...document.querySelectorAll('main,.page.active,.news-card,dialog[open]')].filter(x=>x.getBoundingClientRect().right>innerWidth+1).map(x=>x.className)})""")
    report['layouts'].append({'page':label,'expected_width':page.viewport_size['width'],**info});assert info['viewport']<=page.viewport_size['width']+1,(label,info);assert info['body']<=info['viewport']+1,(label,info);assert not info['overflows'],(label,info)
def page_errors(page):page.set_default_timeout(7000);page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);report['browser_version']=browser.version
    pg=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1);page_errors(pg);requests=[];mount(pg,R,requests=requests)
    check('dashboard loads real packaged JSON',lambda:expect(pg.locator('#ranking .ranking-row')).to_have_count(6));layout(pg,'desktop-dashboard');screenshot(pg,'01-overview.png')
    pg.locator('[data-page="news"]').click()
    check('revenue 377 extraction visible',lambda:expect(pg.locator('#newsCards')).to_contain_text('377'))
    check('29.6 not blanket 19',lambda:expect(pg.locator('.news-card').filter(has_text='群聯8月營收')).to_contain_text('+29.6'))
    pg.locator('#newsQuery').fill('群聯');check('news search filters',lambda:expect(pg.locator('.news-card')).to_have_count(1));screenshot(pg,'02-revenue-analysis.png');layout(pg,'desktop-revenue')
    pg.locator('#newsQuery').fill('');pg.locator('#newsCategory').select_option('analyst_forecast');check('analyst subcategory filter',lambda:expect(pg.locator('.news-card')).to_have_count(3));screenshot(pg,'03-eps-comparison.png')
    eps=pg.locator('.news-card').filter(has_text='信驊');eps.locator('summary').click();check('115.4 paired arithmetic visible',lambda:expect(eps).to_contain_text('115.4'));check('EPS baseline caveat shown',lambda:expect(eps).to_contain_text('舊預估'));eps.screenshot(path=str(out/'04-evidence-expanded.png'));report['screenshots'].append('04-evidence-expanded.png')
    check('financial-specific credit KPIs',lambda:expect(pg.locator('.news-card').filter(has_text='中信金')).to_contain_text('信用成本'))
    pg.locator('[data-page="stocks"]').click();pg.locator('[data-filter="trend"]').click();check('trend filter active',lambda:expect(pg.locator('[data-filter="trend"]')).to_have_class('active'))
    pg.locator('[data-filter=""]').click();pg.locator('#stockFilter').fill('2330');check('stock search',lambda:expect(pg.locator('#stockTable tr')).to_have_count(1));pg.locator('#stockTable [data-open]').click();check('chart exists',lambda:expect(pg.locator('#chart svg')).to_be_visible());screenshot(pg,'05-stock-research.png',full=False)
    for indicator in ['macd','kd','rsi']:
        pg.locator(f'[data-indicator="{indicator}"]').click();check(f'{indicator} chart switch',lambda:expect(pg.locator('#chart svg')).to_be_visible())
    pg.locator('#chartRange').select_option('120');pg.locator('#chartPan').fill('130');pg.locator('#chartPan').dispatch_event('input');pg.locator('#chart #hit-area').hover();check('OHLC hover has actual date',lambda:expect(pg.locator('#hover')).to_contain_text('2026'))
    pg.locator('#chartColor').check();check('chart color switch',lambda:expect(pg.locator('#chartColor')).to_be_checked());pg.locator('#chartColor').uncheck()
    # Gate cards are a separate screenshot within the scrolled dialog.
    pg.locator('.gate-grid').scroll_into_view_if_needed();screenshot(pg,'06-entry-gates.png',selector='.gate-grid');check('six independent entry gates',lambda:expect(pg.locator('.gate')).to_have_count(6))
    pg.locator('#favBtn').click();check('new favorite toggles on',lambda:expect(pg.locator('#favBtn')).to_contain_text('已收藏'))
    pg.keyboard.press('Escape');check('native modal escape',lambda:expect(pg.locator('#stockDialog')).not_to_be_visible())
    pg.locator('[data-page="favorites"]').click();pg.locator('[data-note="2330.TW"]').fill('追蹤營收與現金流，不只看新聞標題');saved=pg.evaluate("JSON.parse(localStorage.getItem('sl16-favs'))");assert saved['2330.TW']['note'].startswith('追蹤營收');check('watchlist note saved through storage interface',lambda:None);screenshot(pg,'07-watchlist.png')
    pg.locator('#favoritesGrid [data-favorite]').click();check('favorite deletion retains tombstone',lambda:None);assert pg.evaluate("JSON.parse(localStorage.getItem('sl16-favs'))['2330.TW'].active") is False
    before=len(requests);pg.locator('[data-page="history"]').click();pg.locator('[data-date="2025-08-15"]').click();pg.wait_for_function("document.querySelector('#historySummary').textContent.includes('2025-08-15')");check('historical snapshot switched',lambda:expect(pg.locator('#historySummary')).to_contain_text('2025-08-15'));screenshot(pg,'08-history.png');assert not any('/market/' in r for r in requests[before:]);check('switch history does not request answer history',lambda:None)
    pg.locator('[data-page="sim"]').click();pg.locator('#simDate').select_option('2025-08-15');pg.wait_for_selector('#simSymbol option',state='attached');pg.locator('#simSymbol').select_option('2330.TW');pg.locator('#tradeReason').fill('盲測教學：先記錄假設，再看後续結果');pg.locator('#simForm button[type="submit"]').click();check('plan locked first',lambda:expect(pg.locator('#simResult')).to_contain_text('盲測計畫已建立'));assert not any('/market/' in r for r in requests);check('no future market reads before reveal',lambda:None);screenshot(pg,'09-blind-plan.png')
    pg.once('dialog',lambda d:d.dismiss());pg.locator('#reveal').click();assert not any('/market/' in r for r in requests);check('cancel reveal leaves future data unread',lambda:None)
    pg.once('dialog',lambda d:d.accept());pg.locator('#reveal').click();pg.wait_for_function("document.querySelector('#tradeLedger').textContent.includes('2330.TW')");assert any('/market/' in r for r in requests);check('future history requested only after confirmation',lambda:None);screenshot(pg,'10-simulation-result.png')
    # Tutorial executes unchanged inline script in the browser.
    t=browser.new_page(viewport={'width':1440,'height':1100});page_errors(t);mount(t,R,tutorial=True);t.wait_for_selector('#learn-eps');check('tutorial has all seven lessons',lambda:expect(t.locator('[id^="lesson-"]')).to_have_count(7));screenshot(t,'11-tutorial.png');layout(t,'desktop-tutorial')
    t.locator('#learn-eps').fill('194.98');t.locator('#learn-old').fill('180');t.locator('#learn-target').fill('22500');t.locator('#learn-price').fill('20000');expect(t.locator('#learn-scenario-result')).to_contain_text('115.4');expect(t.locator('#learn-scenario-result')).to_contain_text('8.32');check('EPS calculator responds to inputs',lambda:None)
    t.locator('#learn-old').fill('');expect(t.locator('#learn-scenario-result')).to_contain_text('缺比較基準');check('missing old EPS stays unknown',lambda:None)
    t.locator('#learn-stop').fill('2000');t.locator('#learn-entry').fill('1000');expect(t.locator('#learn-size-result')).to_contain_text('停損價低於進場價');check('risk calculator rejects invalid stop',lambda:None)
    t.locator('[data-answer="right"]').click();expect(t.locator('#learn-quiz-result')).to_contain_text('正確');check('quiz feedback works',lambda:None)
    t.locator('#learn-stop').fill('94');t.locator('#learn-entry').fill('100');t.locator('#lesson-4').screenshot(path=str(out/'12-tutorial-calculator.png'));report['screenshots'].append('12-tutorial-calculator.png')
    # Native screenshot rendering at three phone sizes, no desktop-wide body.
    for width in [390,360,320]:
        m=browser.new_page(viewport={'width':width,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True);page_errors(m);mount(m,R);layout(m,f'mobile-{width}-home')
        if width==390:screenshot(m,'13-mobile-overview.png')
        for tab in ['stocks','news','history','sim','favorites','method']:
            m.locator(f'[data-page="{tab}"]').click();layout(m,f'mobile-{width}-{tab}')
        m.locator('[data-page="news"]').click();m.locator('#newsQuery').fill('信驊');m.locator('.news-card summary').click();layout(m,f'mobile-{width}-expanded-news')
        if width==390:screenshot(m,'14-mobile-news.png')
        m.locator('#search').fill('2330');m.locator('#search').press('Enter');expect(m.locator('#chart svg')).to_be_visible();m.wait_for_timeout(400);layout(m,f'mobile-{width}-stock-dialog')
        if width==390:screenshot(m,'15-mobile-stock.png',full=False)
        m.close()
        mt=browser.new_page(viewport={'width':width,'height':844});page_errors(mt);mount(mt,R,tutorial=True);mt.wait_for_selector('#learn-eps');layout(mt,f'mobile-{width}-tutorial')
        if width==390:screenshot(mt,'16-mobile-tutorial.png')
        mt.close()
    report['requests']=requests;assert not report['page_errors'],report['page_errors'];report['passed']=True;browser.close()
report['check_count']=len(report['checks']);(out/'BROWSER_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['check_count'],'layouts':len(report['layouts']),'page_errors':report['page_errors'],'screenshots':len(report['screenshots'])},ensure_ascii=False))
