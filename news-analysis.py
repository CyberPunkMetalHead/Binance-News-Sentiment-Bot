
# import for environment variables and waiting
import os, time

# used to parse XML feeds
import xml.etree.ElementTree as ET

# we use it to make async http requests
import aiohttp

# allows us to make our functions async
import asyncio

# date modules that we'll most likely need
from datetime import date, datetime, timedelta

# used to grab the XML url list from a CSV file
import csv

# numpy for sums and means
import numpy as np

# nlp library to analyse sentiment
import nltk
import pytz
from nltk.sentiment import SentimentIntensityAnalyzer

# needed for the binance API
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException

# used for binance websocket
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

# used for executing the code
from itertools import count

# we use it to time our parser execution speed
from timeit import default_timer as timer

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import json

# select what coins to look for as keywords in articles headlines
# The key of each dict MUST be the symbol used for that coin on Binance
# Use each list to define keywords separated by commas: 'XRP': ['ripple', 'xrp']
# keywords are case sensitive
default_keywords = {
    'XRP': ['ripple', 'xrp', 'XRP', 'Ripple', 'RIPPLE'],
    'BTC': ['BTC', 'bitcoin', 'Bitcoin', 'BITCOIN'],
    'XLM': ['Stellar Lumens', 'XLM'],
    'BCH': ['Bitcoin Cash', 'BCH'],
    'ETH': ['ETH', 'Ethereum'],
    'BNB': ['BNB', 'Binance Coin'],
    'LTC': ['LTC', 'Litecoin']
}


class BinanceClient:
    def __init__(self, is_test_net: bool, api_key: str, api_secret: str, api_key_test: str, api_secret_test: str,
                 keywords: dict, pairing: str):
        self.api_secret = api_secret
        self.api_key = api_key
        self.api_secret_test = api_secret_test
        self.api_key_test = api_key_test
        self.is_test_net = is_test_net

        self.client = Client(api_key, api_key)
        self.client_test = Client(api_key_test, api_secret_test)
        self.client_test.API_URL = 'https://testnet.binance.vision/api'

        # connect to the websocket client and start the socket
        bsm = BinanceSocketManager(self.client)
        for coin in keywords:
            conn_key = bsm.start_symbol_ticker_socket(coin+pairing, BinanceClient.ticker_socket)
        bsm.start()

    @staticmethod
    def ticker_socket(msg):
        '''Open a stream for financial information for CRYPTO'''
        if msg['e'] != 'error':
            CurrentWallet.CURRENT_PRICE['{0}'.format(msg['s'])] = msg['c']
        else:
            print('error')

    def create_test_order(self, *args, **kwargs):
        if self.is_test_net:
            return self.client_test.create_test_order(*args, **kwargs)

    def create_order(self, *args, **kwargs):
        return self.client.create_order(*args, **kwargs)

    def get_symbol_info(self, symbol: str):
        return self.client.get_symbol_info(symbol)

    def get_all_orders(self, *args, **kwargs):
        return self.client.get_all_orders(*args, **kwargs)


class CurrentWallet:
    CURRENT_PRICE = {}
    quantity = 0

    def __init__(self, binance_client: BinanceClient, keywords, pairing: str, quantity: float):
        # coins that bought by the bot since its start
        self.coins_in_hand = {}
        CurrentWallet.quantity = quantity
        # initializing the volumes at hand
        for coin in keywords:
            self.coins_in_hand[coin] = 0

        '''For the amount of CRYPTO to trade in USDT'''
        self.lot_size = {}

        '''Find step size for each coin
        For example, BTC supports a volume accuracy of
        0.000001, while XRP only 0.1
        '''
        for coin in keywords:
            try:
                info = binance_client.get_symbol_info(coin+pairing)
                step_size = info['filters'][2]['stepSize']
                self.lot_size[coin+pairing] = step_size.index('1') - 1

                if self.lot_size[coin+pairing]<0:
                    self.lot_size[coin+pairing]=0
            except:
                pass

        for coin in keywords:
            try:
                info = binance_client.get_symbol_info(coin)
                step_size = info['filters'][2]['stepSize']
                self.lot_size[coin] = step_size.index('1') - 1

                if self.lot_size[coin]<0:
                    self.lot_size[coin]=0
            except:
                pass

    def calculate_volume(self):
        while self.CURRENT_PRICE == {}:
            print('Connecting to the socket...')
            time.sleep(3)
        else:
            volume = {}
            for coin in self.CURRENT_PRICE:
                volume[coin] = float(CurrentWallet.quantity / float(self.CURRENT_PRICE[coin]))
                volume[coin] = self.calculate_one_volume_from_lot_size(coin, volume[coin])

            return volume

    def calculate_one_volume_from_lot_size(self, coin, amount):
        if coin not in self.lot_size:
            return float('{:.1f}'.format(amount))
        else:
            return float('{:.{}f}'.format(amount, self.lot_size[coin]))


class SentimentAnalyzer:
    # Make headlines global variable as it should be the same across all functions
    headlines = {'source': [], 'title': [], 'pubDate': []}
    feeds = []
    hours_past = 0
    keywords = {}

    def __init__(self, binance_client: BinanceClient, current_wallet: CurrentWallet, quantity: int, pairing: str,
                 sentiment_threshold: float, negative_sentiment_threshold: float, minimum_articles: int,
                 hours_past: int, keywords: dict):
        self.binance_client = binance_client
        self.current_wallet = current_wallet
        SentimentAnalyzer.hours_past = hours_past
        self.minimum_articles = minimum_articles
        self.negative_sentiment_threshold = negative_sentiment_threshold
        self.sentiment_threshold = sentiment_threshold
        self.pairing = pairing
        self.quantity = quantity
        SentimentAnalyzer.keywords = keywords

        SentimentAnalyzer.load_feeds()

    @staticmethod
    async def get_feed_data(session, feed, headers):
        '''
        Get relevant data from rss feed, in async fashion
        :param feed: The name of the feed we want to fetch
        :param headers: The header we want on the request
        :return: None, we don't need to return anything we append it all on the headlines dict
        '''
        headlines = SentimentAnalyzer.headlines

        try:
            async with session.get(feed, headers=headers, timeout=60) as response:
                # define the root for our parsing
                text = await response.text()
                root = ET.fromstring(text)

                channel = root.find('channel/item/title').text
                pubDate = root.find('channel/item/pubDate').text
                # some jank to ensure no alien characters are being passed
                title = channel.encode('UTF-8').decode('UTF-8')

                # convert pubDat to datetime
                published = datetime.strptime(pubDate.replace("GMT", "+0000"), '%a, %d %b %Y %H:%M:%S %z')
                # calculate timedelta
                time_between = datetime.now(pytz.utc) - published

                #print(f'Czas: {time_between.total_seconds() / (60 * 60)}')

                if time_between.total_seconds() / (60 * 60) <= SentimentAnalyzer.hours_past:
                    # append the source
                    headlines['source'].append(feed)
                    # append the publication date
                    headlines['pubDate'].append(pubDate)
                    # append the title
                    headlines['title'].append(title)
                    print(channel)

        except Exception as e:
            # Catch any error and also print it
            print(f'Could not parse {feed} error is: {e}')

    @staticmethod
    async def get_headlines():
        '''
        Creates a an async task for each of our feeds which are appended to headlines
        :return: None
        '''
        # add headers to the request for ElementTree. Parsing issues occur without headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0'
        }

        # A nifty timer to see how long it takes to parse all the feeds
        start = timer()
        async with aiohttp.ClientSession() as session:
            tasks = []
            for feed in SentimentAnalyzer.feeds:
                task = asyncio.ensure_future(SentimentAnalyzer.get_feed_data(session, feed, headers))
                tasks.append(task)

            # This makes sure we finish all tasks/requests before we continue executing our code
            await asyncio.gather(*tasks)
        end = timer()
        print("Time it took to parse feeds: ", end - start)

    @staticmethod
    def categorise_headlines():
        '''arrange all headlines scraped in a dictionary matching the coin's name'''
        # get the headlines
        asyncio.run(SentimentAnalyzer.get_headlines())
        categorised_headlines = {}

        # this loop will create a dictionary for each keyword defined
        for keyword in SentimentAnalyzer.keywords:
            categorised_headlines['{0}'.format(keyword)] = []

        # keyword needs to be a loop in order to be able to append headline to the correct dictionary
        for keyword in SentimentAnalyzer.keywords:

            # looping through each headline is required as well
            for headline in SentimentAnalyzer.headlines['title']:
                # appends the headline containing the keyword to the correct dictionary
                if any(key in headline for key in SentimentAnalyzer.keywords[keyword]):
                    categorised_headlines[keyword].append(headline)

        return categorised_headlines

    @staticmethod
    def analyse_headlines():
        '''Analyse categorised headlines and return NLP scores'''
        sia = SentimentIntensityAnalyzer()
        categorised_headlines = SentimentAnalyzer.categorise_headlines()

        sentiment = {}

        for coin in categorised_headlines:
            if len(categorised_headlines[coin]) > 0:
                # create dict for each coin
                sentiment['{0}'.format(coin)] = []
                # append sentiment to dict
                for title in categorised_headlines[coin]:
                    sentiment[coin].append(sia.polarity_scores(title))

        return sentiment

    @staticmethod
    def compile_sentiment():
        '''Arranges every compound value into a list for each coin'''
        sentiment = SentimentAnalyzer.analyse_headlines()
        compiled_sentiment = {}

        for coin in sentiment:
            compiled_sentiment[coin] = []

            for item in sentiment[coin]:
                # append each compound value to each coin's dict
                compiled_sentiment[coin].append(sentiment[coin][sentiment[coin].index(item)]['compound'])

        return compiled_sentiment

    @staticmethod
    def compound_average():
        '''Calculates and returns the average compound sentiment for each coin'''
        compiled_sentiment = SentimentAnalyzer.compile_sentiment()
        headlines_analysed = {}

        for coin in compiled_sentiment:
            headlines_analysed[coin] = len(compiled_sentiment[coin])

            # calculate the average using numpy if there is more than 1 element in list
            compiled_sentiment[coin] = np.array(compiled_sentiment[coin])

            # get the mean
            compiled_sentiment[coin] = np.mean(compiled_sentiment[coin])

            # convert to scalar
            compiled_sentiment[coin] = compiled_sentiment[coin].item()

        return compiled_sentiment, headlines_analysed

    @staticmethod
    def load_feeds(filename='Crypto feeds.csv'):
        # load the csv file contain top 100 crypto feeds
        # want to scan other websites?
        # Simply add the RSS Feed url to the Crypto feeds.csv file
        with open(filename) as csv_file:
            # open the file
            csv_reader = csv.reader(csv_file)

            # remove any headers
            next(csv_reader, None)

            # add each row containing RSS url to feeds list
            for row in csv_reader:
                SentimentAnalyzer.feeds.append(row[0])

    def buy(self, compiled_sentiment, headlines_analysed):
        '''Check if the sentiment is positive and keyword is found for each handle'''
        volume = self.current_wallet.calculate_volume()
        coins_in_hand = self.current_wallet.coins_in_hand

        for coin in compiled_sentiment:
            # check if the sentiment and number of articles are over the given threshold
            trade_pair = coin + self.pairing

            if compiled_sentiment[coin] > self.sentiment_threshold and headlines_analysed[coin] >= self.minimum_articles and coins_in_hand[coin]==0:
                # check the volume looks correct
                print(f'preparing to buy {volume[trade_pair]} {coin} with {self.pairing} at {self.current_wallet.CURRENT_PRICE[trade_pair]}')

                # create test order before pushing an actual order
                test_order = self.binance_client.create_test_order(symbol=trade_pair, side='BUY', type='MARKET', quantity=volume[trade_pair])

                # try to create a real order if the test orders did not raise an exception
                try:
                    buy_limit = self.binance_client.create_order(
                        symbol=trade_pair,
                        side='BUY',
                        type='MARKET',
                        quantity=volume[trade_pair]
                    )

                #error handling here in case position cannot be placed
                except Exception as e:
                    print(e)

                # run the else block if the position has been placed and return some info
                else:
                    # adds coin to our portfolio
                    coins_in_hand[coin] += volume[trade_pair]

                    # retrieve the last order
                    order = self.binance_client.get_all_orders(symbol=trade_pair, limit=1)

                    if order:
                        # convert order timestamp into UTC format
                        time = order[0]['time'] / 1000
                        utc_time = datetime.fromtimestamp(time)

                        # grab the price of CRYPTO the order was placed at for reporting
                        bought_at = self.current_wallet.CURRENT_PRICE[trade_pair]

                        # print order confirmation to the console
                        print(f"order {order[0]['orderId']} has been placed on {coin} with {order[0]['origQty']} at {utc_time} and bought at {bought_at}")
                    else:
                        print('Could not get last order from Binance!')

            else:
                print(f'Sentiment not positive enough for {coin}, or not enough headlines analysed or already bought: {compiled_sentiment[coin]}, {headlines_analysed[coin]}')

    def sell(self, compiled_sentiment, headlines_analysed):
        '''Check if the sentiment is negative and keyword is found for each handle'''
        coins_in_hand = self.current_wallet.coins_in_hand

        for coin in compiled_sentiment:
            # check if the sentiment and number of articles are over the given threshold
            trade_pair = coin + self.pairing

            if compiled_sentiment[coin] < self.negative_sentiment_threshold and headlines_analysed[coin] >= self.minimum_articles and coins_in_hand[coin]>0:

                # check the volume looks correct
                print(f'preparing to sell {coins_in_hand[coin]} {coin} at {self.current_wallet.CURRENT_PRICE[trade_pair]}')

                amount_to_sell = self.current_wallet.calculate_one_volume_from_lot_size(trade_pair, coins_in_hand[coin]*99.5/100)

                # create test order before pushing an actual order
                test_order = self.binance_client.create_test_order(symbol=trade_pair, side='SELL', type='MARKET', quantity=amount_to_sell)

                # try to create a real order if the test orders did not raise an exception
                try:
                    buy_limit = self.binance_client.create_order(
                        symbol=trade_pair,
                        side='SELL',
                        type='MARKET',
                        quantity=amount_to_sell
                    )

                #error handling here in case position cannot be placed
                except Exception as e:
                    print(e)

                # run the else block if the position has been placed and return some info
                else:
                    # set coin to 0
                    coins_in_hand[coin]=0
                    # retrieve the last order
                    order = self.binance_client.get_all_orders(symbol=trade_pair, limit=1)

                    if order:
                        # convert order timestamp into UTC format
                        time = order[0]['time'] / 1000
                        utc_time = datetime.fromtimestamp(time)

                        # grab the price of CRYPTO the order was placed at for reporting
                        sold_at = self.current_wallet.CURRENT_PRICE[trade_pair]

                        # print order confirmation to the console
                        print(f"order {order[0]['orderId']} has been placed on {coin} with {order[0]['origQty']} coins sold for {sold_at} each at {utc_time}")
                    else:
                        print('Could not get last order from Binance!')

            else:
                print(f'Sentiment not negative enough for {coin}, not enough headlines analysed or not enough {coin} to sell: {compiled_sentiment[coin]}, {headlines_analysed[coin]}')


if __name__ == '__main__':
    argument_parser = ArgumentParser('Binance news sentiment bot.', formatter_class=ArgumentDefaultsHelpFormatter)
    argument_parser.add_argument('-q', '--quantity', type=int, default=100, dest='QUANTITY', help='The Buy amount in the PAIRING symbol, by default USDT 100 will for example buy the equivalent of 100 USDT in Bitcoin.')
    argument_parser.add_argument('-p', '--pairing', type=str, default='USDT', dest='PAIRING', help='Define what to pair each coin to. AVOID PAIRING WITH ONE OF THE COINS USED IN KEYWORDS.')
    argument_parser.add_argument('-s', '--sentiment-threshold', type=float, default=0, dest='SENTIMENT_THRESHOLD', help='Define how positive the news should be in order to place a trade. The number is a compound of neg, neu and pos values from the nltk analysis. Input a number between -1 and 1.')
    argument_parser.add_argument('-n', '--negative-sentiment-threshold', type=float, default=0, dest='NEGATIVE_SENTIMENT_THRESHOLD', help='Define how positive the news should be in order to place a trade. The number is a compound of neg, neu and pos values from the nltk analysis. Input a number between -1 and 1.')
    argument_parser.add_argument('-a', '--minimum-articles', type=int, default=1, dest='MINUMUM_ARTICLES', help='Define the minimum number of articles that need to be analysed in order for the sentiment analysis to qualify for a trade signal. Avoid using 1 as that\'s not representative of the overall sentiment.')
    argument_parser.add_argument('-r', '--repeat-every', type=int, default=60, dest='REPEAT_EVERY', help='Define how often to run the code (check for new + try to place trades)in minutes.')
    argument_parser.add_argument('-o', '--hours-past', type=int, default=24, dest='HOURS_PAST', help='Define how old an article can be to be included in hours.')
    argument_parser.add_argument('-k', '--keywords', type=json.loads, default=default_keywords, dest='KEYWORDS', help='Select what coins to look for as keywords in articles headlines. The key of each dict MUST be the symbol used for that coin on Binance. Use each list to define keywords separated by commas, don\'t forget to escape double quotes, don\'t use any spaces: {\"XRP\":[\"ripple\",\"xrp\"]}. Keywords are case sensitive.')
    argument_parser.add_argument('-t', '--test-net', type=bool, default=True, dest='TESTNET', help='Use testnet or live.')
    argument_parser.add_argument('--api-key', type=str, default='', dest='API_KEY')
    argument_parser.add_argument('--api-secret', type=str, default='', dest='API_SECRET')
    argument_parser.add_argument('--api-key-test', type=str, default='', dest='API_KEY_TEST')
    argument_parser.add_argument('--api-secret-test', type=str, default='', dest='API_SECRET_TEST')
    args = argument_parser.parse_args()

    print(f'args={args}')

    binance_client = BinanceClient(args.TESTNET, args.API_KEY, args.API_SECRET, args.API_KEY_TEST, args.API_SECRET_TEST,
                                   args.KEYWORDS, args.PAIRING)
    current_wallet = CurrentWallet(binance_client, args.KEYWORDS, args.PAIRING, args.QUANTITY)
    sentiment_analyzer = SentimentAnalyzer(binance_client, current_wallet, args.QUANTITY, args.PAIRING,
                                           args.SENTIMENT_THRESHOLD, args.NEGATIVE_SENTIMENT_THRESHOLD,
                                           args.MINUMUM_ARTICLES, args.HOURS_PAST, args.KEYWORDS)

    print('Press Ctrl-Q to stop the script')
    for i in count():
        compiled_sentiment, headlines_analysed = SentimentAnalyzer.compound_average()
        print("\nBUY CHECKS:")
        sentiment_analyzer.buy(compiled_sentiment, headlines_analysed)
        print("\nSELL CHECKS:")
        sentiment_analyzer.sell(compiled_sentiment, headlines_analysed)
        print('\nCurrent bot holdings: ')

        coins_in_hand = sentiment_analyzer.current_wallet.coins_in_hand

        for coin in coins_in_hand:
            if coins_in_hand[coin] > 0:
                print(f'{coin}: {coins_in_hand[coin]}')

        print(f'\nIteration {i}')
        time.sleep(60 * args.REPEAT_EVERY)
