JARVIS TRADING CORE V2

Replace the files in C:\Jarvis\agents\trading_core with this package.

Compile:
python -m py_compile .\agents\trading_core\core.py
python -m py_compile .\agents\trading_core\context_engine.py
python -m py_compile .\agents\trading_core\cli.py

Test the 15m context / 5m trigger architecture:
python -m agents.trading_core.cli --symbol NIFTY --mtf --bars 1000
python -m agents.trading_core.cli --symbol BANKNIFTY --mtf --bars 1000

Test the preferred-market scan:
python -m agents.trading_core.cli --scan --timeframe 5m --bars 1000

Test paper-readiness without placing an order:
python -m agents.trading_core.cli --symbol BANKNIFTY --paper-ready --bars 1000

NO LIVE ORDER EXECUTION EXISTS.
