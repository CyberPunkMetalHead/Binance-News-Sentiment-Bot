Fully functioning Binance Trading bot that Buys cryptocurrency based on Daily news sentiment from the top 100 crypto feeds.

Main Features:
Pull and analyse the last headline from the top 100 crypto news sites

Provide an overview on the most mentioned coin across all the headlines

Analyse the sentiment of each headline and categorise the output by coin

Place a Buy order if the compound sentiment is positive

The bot sells %99.5 of the coins it bought in order to avoid exceptions

"coins_in_hand" dictionary stores the amount of coins the bot bought and currently holding.

Configurable options

Works with any number of cryptocurrencies

For a complete step-by-step setup guide please see: https://www.cryptomaton.org/2021/04/17/how-to-code-a-binance-crypto-trading-bot-that-trades-based-on-daily-news-sentiment/

## Known Issues:
If you receive an error similar to
```python news-analysis.py
Traceback (most recent call last):
  File "news-analysis.py", line 41, in <module>
    from binance.websockets import BinanceSocketManager
ModuleNotFoundError: No module named 'binance.websockets'
```
you should install python-binance at an older version (pre 1.0.0)
`pip install python-binance==0.7.1`
