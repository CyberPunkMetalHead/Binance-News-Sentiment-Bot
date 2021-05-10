Binance news sentiment bot
==========================

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

## Run options
```
-h | --help                             -   See help.
--api-key                               -   Binance API key.
--api-secret                            -   Binance API decret. 
--api-key-test                          -   Binance API key for test net.
--api-secret-test                       -   Binance API decret for test net.
-t | --test-net                         -   Try to place a test order before a real order.
-q | --quantity                         -   The Buy amount in the PAIRING symbol, by default USDT 100 will for example buy the equivalent of 100 USDT in Bitcoin. Default - 100.
-p | --pairing                          -   Define what to pair each coin to. AVOID PAIRING WITH ONE OF THE COINS USED IN KEYWORDS. Default - 'USDT'
-s | --sentiment-threshold              -   Define how positive the news should be in order to place a trade. The number is a compound of neg, neu and pos values from the nltk analysis. Input a number between -1 and 1. Default - 0
-n | --negative-sentiment-threshold     -   Define how positive the news should be in order to place a trade. The number is a compound of neg, neu and pos values from the nltk analysis. Input a number between -1 and 1. Default - 0
-a | --minimum-articles                 -   Define the minimum number of articles that need to be analysed in order for the sentiment analysis to qualify for a trade signal. Avoid using 1 as that\'s not representative of the overall sentiment. Default - 1
-r | --repeat-every                     -   Define how often to run the code (check for new + try to place trades)in minutes. Default - 60
-o | --hours-past                       -   Define how old an article can be to be included in hours. Default - 24
-k | --keywords                         -   Select what coins to look for as keywords in articles headlines. The key of each dict MUST be the symbol used for that coin on Binance. Use each list to define keywords separated by commas, don\'t forget to escape double quotes, don\'t use any spaces: {\"XRP\":[\"ripple\",\"xrp\"]}. Keywords are case sensitive. See defauld in file news-analysis.py -> 'keywords' variable.
```

If 

# Docker version

### How to build
```docker
docker build -t <docker-image-tag> .
```

### How to run

#### Default run
```docker
docker run --restart always <docker-image-tag>
```

#### Run with options
```docker
docker run --restart always <docker-image-tag> <options>
```

#### Run with custom 'Crypto feeds' file
1) Create your own 'Crypto feeds' file.
2) Run container
   ```docker
   docker run --restart always -v <path-to-your-file>:/Crypto\ feeds.csv <docker-image-tag> <options>
   ```