"""Isolated interactive chart acceptance; fixtures never reach the ledger."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def main():
    bars = [dict(time=1700000000+i*300, open=100+i, high=103+i, low=99+i, close=102+i) for i in range(40)]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport=dict(width=1600, height=1000))
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('http://jarvis.test/**', lambda r: r.fulfill(json=dict(success=True, candles=bars)))
        page.goto('http://jarvis.test/')
        page.set_content('<style>#win-chart{height:900px;display:flex;flex-direction:column}.chartToolbar{display:flex}#chartGrid{height:800px}</style><div id="topbar"><nav></nav><div class="topStatus"></div></div><div id="win-chart"><div class="chartToolbar"></div><div id="chartGrid"></div></div>')
        page.add_style_tag(path=str(ROOT/'workstation/jarvis_os_v3_assets/v16_main_trading.css'))
        page.add_script_tag(path=str(ROOT/'workstation/quant_terminal_v2_static/lightweight-charts.standalone.production.js'))
        page.add_script_tag(content='let chartSlots=[{symbol:"BTC",timeframe:"5m"}];let selectedTimeframe="5m";function persistWorkspace(){}function setChartCount(){}function renderChartSlots(){}function loadChart(){}')
        page.add_script_tag(path=str(ROOT/'workstation/jarvis_os_v3_assets/v16_main_trading_runtime.js'))
        for count in range(1,9):
            page.locator(f'[data-v16-chart-count="{count}"]').click()
            assert page.locator('.v16ChartPane').count() == count
            page.wait_for_function(f'V16_CHART_VIEWS.size === {count}')
            assert page.evaluate('localStorage.getItem(V16_LAYOUT_STORAGE)') == str(count)
        before = page.evaluate('chartSlots[1].symbol')
        page.locator('.v16ChartSymbol').first.select_option('SOL')
        assert page.evaluate('chartSlots[1].symbol') == before
        page.set_viewport_size(dict(width=900,height=800))
        page.wait_for_timeout(250)
        assert page.locator('.v16ChartPane').count() == 8
        assert page.locator('.v16ChartPane canvas').count() >= 8
        assert not errors, errors
        print(json.dumps(dict(layouts='1-8 PASS',independence='PASS',persistence='PASS',resize='PASS',errors=errors,data='ISOLATED FIXTURES, NOT LIVE')))
        browser.close()

if __name__ == '__main__':
    main()
