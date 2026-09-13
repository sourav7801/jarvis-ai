"""Real rich-terminal browser checks. All market responses are isolated fixtures."""
from pathlib import Path
import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation/quant_terminal_v2_static"

def main():
    bars = [dict(time=1700000000+i*300, open=100+i, high=103+i, low=99+i, close=102+i, volume=100) for i in range(80)]
    reads = []
    def serve(route):
        path = urlparse(route.request.url).path
        file = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
        if file.is_file() and STATIC in file.resolve().parents:
            route.fulfill(path=str(file), content_type="text/html" if file.suffix == ".html" else "text/css" if file.suffix == ".css" else "application/javascript")
        elif path == "/api/candles":
            reads.append(route.request.url)
            route.fulfill(json=dict(success=True, candles=bars, source="ISOLATED_FIXTURE", bars=len(bars)))
        else:
            route.fulfill(json=dict(success=False, message="Isolated test: external service unavailable"))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport=dict(width=1800,height=1100))
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/*", serve)
        page.goto("http://jarvis.test/")
        page.wait_for_function("chartSlots.length === 4 && chartSlots.every(s => s.chart)")
        for count in range(1,9):
            page.locator(f'[data-layout="{count}"]').click(timeout=2000)
            page.wait_for_function(f"chartSlots.length === {count} && chartSlots.every(s => s.chart)")
            assert page.locator(".chart-cell").count() == count
        page.locator('[data-slot="0"] [data-chart-timeframe]').select_option("15m")
        page.wait_for_function('chartSlots[0].timeframe === "15m"')
        assert page.evaluate('chartSlots[1].timeframe') == "5m"
        page.locator('[data-slot="0"] [data-chart-symbol]').select_option("SOL")
        page.wait_for_function('chartSlots[0].symbol === "SOL" && chartSlots[0].data.length > 0')
        assert page.evaluate('chartSlots[1].symbol') == "BANKNIFTY"
        page.locator('[data-workspace="SWING"]').click()
        assert page.evaluate('chartSlots[0].symbol') != "SOL"
        page.locator('[data-workspace="INTRADAY"]').click()
        assert page.evaluate('chartSlots[0].symbol') == "SOL"
        page.reload()
        page.wait_for_function('chartSlots.length === 8 && chartSlots[0].symbol === "SOL"')
        assert page.evaluate('chartSlots[0].timeframe') == "15m"
        for width in (1100,800,1800):
            page.set_viewport_size(dict(width=width,height=1100))
            page.wait_for_timeout(150)
            assert page.locator(".chart-cell").count() == 8
        assert not errors, errors
        print(json.dumps(dict(layouts="1-8 PASS", isolation="PASS", persistence="PASS", resize="PASS", errors=errors, fixture_candle_reads=len(reads), data="ISOLATED FIXTURES, NOT LIVE")))
        browser.close()

if __name__ == "__main__":
    main()
