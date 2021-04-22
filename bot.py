# -*- coding: utf-8 -*-
import datetime
import feedparser
import numpy as np
# import grequests
import requests
from binance.client import Client as BnClient
from binance.exceptions import BinanceAPIException
from loguru import logger
from nltk.sentiment import SentimentIntensityAnalyzer
from timeit import default_timer as timer


class BinanceTradeBot(BnClient):
    '''
    币安交易机器人
    币安Restful Api: https://api.binance.com/api/v3/
    '''
    def __init__(self, ak: str, sk: str, proxies: dict, test: bool):
        if proxies == {}:
            BnClient.__init__(self, api_key=ak, api_secret=sk, requests_params={"verify": False, "timeout": 10})
        else:
            BnClient.__init__(self, api_key=ak, api_secret=sk, requests_params={"proxies": proxies, "verify": False, "timeout": 10})
        if test:
            # change the API_URL manually to work on the test net
            self.API_URL = "https://testnet.binance.vision/api"
            self.test = True
            logger.info("******************** USE TESTNET ******************** ")
        else:
            self.test = False
            logger.info("******************** USE MAINNET ******************** ")

        self.PAIRING = "USDT"
        # the buy amount in the PAIRING symbol, by default USDT,
        # for example, buy the equivalent of 100 USDT in BTC.
        self.QUANTITY = 100
        # define how positive/negative the news should be in order to place a trade.
        # the number is a compound value of neg, neu and pos values from the nltk analysis.
        # between 0 and 1
        self.SENTIMENT_THRESHOLD = 0.001
        # between 0 and -1
        self.NEGATIVE_SENTIMENT_THRESHOLD = -0.001
        # define the minimum number of articles that need to be analysed in order
        # for the sentiment analysis to qualify for a trade signal.
        self.MINIMUM_ARTICLES = 5
        self.REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"}

        self.asset_balance = {}

    def is_ready(self):
        '''
        测试网络时延: httpstat https://api.binance.com/api/v3/ping
        '''
        ready = True
        try:
            self.ping()
        except BinanceAPIException as e:
            logger.error("Failed to setup the BinanceTradeBot, err: {}.".format(str(e)))
            ready = False
        finally:
            if ready:
                if self.test:
                    logger.info("BinanceTradeBot has got ready now, let's hack with the test net.")
                else:
                    logger.info("BinanceTradeBot has got ready now, let's hack with the main net.")
            return ready


    def prepare_coins(self, coins: dict):
        self.coin_dict = coins

    def prepare_rss_feeds(self, feeds: list):
        self.feed_list = feeds
        logger.info("Import {} RSS feeds".format(len(self.feed_list)))
    
    def prepare_lot_size(self):
        '''
        Find out the trade size for each coin.
        For example, BTC supports a volume accuracy of 0.000001, while XRP only supports 0.1.
        '''
        self.lot_size = {}
        for coin in self.coin_dict.keys():
            info = self.get_symbol_info(coin+self.PAIRING)
            if info != None:
                filters = info.get("filters", [])
                for flt in filters:
                    if flt["filterType"] == "LOT_SIZE":
                        step_size = flt["stepSize"]
                        self.lot_size[coin+self.PAIRING] = step_size.index('1') - 1
                        logger.info("LOT SIZE of {} is {}".format(coin+self.PAIRING, step_size))
                        break
            else:
                logger.warning("Failed to fetch information about {}".format(coin+self.PAIRING))

    def __fetch_headlines(self):
        headlines = []
        start = timer()
        with requests.Session() as session:
            for url in self.feed_list:
                try:
                    r = session.get(url, headers=self.REQUEST_HEADERS, timeout=10)
                    if r.status_code != 200:
                        logger.error("Failed to parse rss feed {}, status code: {}", url, r.status_code)
                    else:
                        logger.info("Parse rss feed {}", url)
                        news_feed = feedparser.parse(r.text)
                        if len(news_feed.entries) <= 1:
                            continue
                        entry = news_feed.entries[1]
                        headline = {}
                        headline["source"] = url
                        headline["title"] = entry.get("title", "")
                        headline["pub_date"] = entry.get("published", "")
                        # TODO: 不处理曾经已经处理过的标题
                        headlines.append(headline)
                except requests.exceptions.ReadTimeout as e:
                    logger.error("Timeout to parse rss feed {}", url)
        end = timer()
        logger.debug("It took {}s to parse all rss feeds".format(end - start))
        return headlines

    def __categorise_headlines(self):
        categorised_headlines = {}
        headlines = self.__fetch_headlines()
        for coin in self.coin_dict.keys():
            categorised_headlines[coin] = []
            for headline in headlines:
                if headline["title"] != "":
                    if any(key in headline["title"] for key in self.coin_dict[coin]):
                        categorised_headlines[coin].append(headline["title"])
        return categorised_headlines

    def __analyse_headlines(self):
        sentiment = {}
        categorised_headlines = self.__categorise_headlines()
        sia = SentimentIntensityAnalyzer()
        for coin in categorised_headlines.keys():
            if len(categorised_headlines[coin]) > 0:
                sentiment[coin] = []
                for title in categorised_headlines[coin]:
                    sentiment[coin].append(sia.polarity_scores(title))
        return sentiment

    def __compile_sentiment(self):
        compiled_sentiment = {}
        sentiment = self.__analyse_headlines()
        for coin in sentiment.keys():
            compiled_sentiment[coin] = []
            for item in sentiment[coin]:
                compiled_sentiment[coin].append(sentiment[coin][sentiment[coin].index(item)]["compound"])
        return compiled_sentiment

    def compound_average(self):
        analysed_headlines = {}
        compiled_sentiment = self.__compile_sentiment()
        for coin in compiled_sentiment.keys():
            analysed_headlines[coin] = len(compiled_sentiment[coin])
            compiled_sentiment[coin] = np.array(compiled_sentiment[coin])
            compiled_sentiment[coin] = np.mean(compiled_sentiment[coin])
            compiled_sentiment[coin] = compiled_sentiment[coin].item()
            logger.debug("<{}, {}>".format(coin, compiled_sentiment[coin]))
        return compiled_sentiment, analysed_headlines

    def __calculate_volume(self):
        # TODO: fetch current price of all coins
        self.current_price = {}
        volume = {}
        for coin in self.current_price.keys():
            volume[coin] = float(self.QUANTITY) / float(self.current_price[coin])
            lot = self.lot_size.get(coin+self.PAIRING, 0)
            if lot > 0:
                volume[coin] = float("{:.{}f}".format(volume[coin], lot))
            else:
                volume[coin] = float("{:.1f}".format(volume[coin]))
        return volume

    def buy(self, compiled_sentiment, analysed_headlines):
        volume = self.__calculate_volume()
        for coin in compiled_sentiment.keys():
            if compiled_sentiment[coin] > self.SENTIMENT_THRESHOLD and analysed_headlines[coin] >= self.MINIMUM_ARTICLES:
                log.info("Preparing to buy {} {} with {} at {}".format(
                    volume[coin+self.PAIRING], coin, self.PAIRING, self.current_price[coin+self.PAIRING])
                )
                try:
                    self.create_test_order(
                        symbol=coin+self.PAIRING,
                        side="BUY",
                        type="MARKET",
                        quantity=volume[coin+self.PAIRING]
                    )
                    try:
                        buy_limit = self.create_order(
                            symbol=coin+self.PAIRING,
                            side="BUY",
                            type="MARKET",
                            quantity=volume[coin+self.PAIRING]
                        )
                        time.sleep(0.5)

                        self.asset_balance[coin] += volume[coin+self.PAIRING]
                        order = self.get_all_orders(symbol=coin+self.PAIRING, limit=1)
                        time = order[0]["time"] / 1000
                        utc_time = datetime.fromtimestamp(time)
                        bought_at = self.current_price[coin+self.PAIRING]
                        logger.info("Order {} has been placed on {} with {} coins at {} and bought at {}".format(
                            order[0]["orderId"], coin, order[0]["origQty"], utc_time, bought_at
                        ))
                    except BinanceAPIException as e:
                        logger.error("Failed to create a real order".format(str(e)))
                except BinanceAPIException as e:
                    logger.error("Failed to create a test order".format(str(e)))
            else:
                logger.warning("Sentiment is not positive enough for {}, or not enough headlines analysed".format(coin))

    def sell(self, compiled_sentiment, analysed_headlines):
        for coin in compiled_sentiment.keys():
            if compiled_sentiment[coin] < self.NEGATIVE_SENTIMENT_THRESHOLD and analysed_headlines[coin] >= self.MINIMUM_ARTICLES and self.asset_balance[coin] > 0:
                log.info("Preparing to sell {} {} at {}".format(
                    self.asset_balance[coin], coin, self.current_price[coin+self.PAIRING]
                ))
                try:
                    self.create_test_order(
                        symbol=coin+self.PAIRING,
                        side="SELL",
                        type="MARKET",
                        quantity=self.asset_balance[coin]*95/100
                    )
                    try:
                        buy_limit = self.create_order(
                            symbol=coin+self.PAIRING,
                            side="SELL",
                            type="MARKET",
                            quantity=self.asset_balance[coin]*95/100
                        )
                        time.sleep(0.5)

                        self.asset_balance[coin] = 0
                        order = self.get_all_orders(symbol=coin+self.PAIRING, limit=1)
                        time = order[0]["time"] / 1000
                        utc_time = datetime.fromtimestamp(time)
                        sold_at = self.current_price[coin+self.PAIRING]
                        logger.info("Order {} has been placed on {} with {} coins at and sold for {}".format(
                            order[0]["orderId"], coin, order[0]["origQty"], utc_time, sold_at
                        ))
                    except BinanceAPIException as e:
                        logger.error("Failed to create a real order".format(str(e)))
                except BinanceAPIException as e:
                    logger.error("Failed to create a test order".format(str(e)))
            else:
                logger.warning("Sentiment is not negative enough for {}, or not enough headlines analysed or not enough {} to sell".format(coin, coin))
