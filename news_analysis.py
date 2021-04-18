!pip install requests
!pip install numpy
!pip install python-binance
!pip install nltk

# import for environment variables and waiting
import os, time

# used to parse XML feeds
import xml.etree.ElementTree as ET

# get the XML feed and pass it to Element tree
import requests

# date modules that we'll most likely need
from datetime import date, datetime, timedelta

# used to grab the XML url list from a CSV file
import csv

# numpy for sums and means
import numpy as np

# nlp library to analyse sentiment
import nltk
nltk.download('vader_lexicon')
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


# get binance key and secret from environment variables
api_key = os.getenv('binance_api_stalkbot_testnet')
api_secret = os.getenv('binance_secret_stalkbot_testnet')

# Authenticate with the client
client = Client(api_key, api_secret)

# The API URL is manually changed in the library to work on the testnet
client.API_URL = 'https://testnet.binance.vision/api'




############################################
#     USER INPUT VARIABLES LIVE BELOW      #
# You may edit those to configure your bot #
############################################


# select what coins to look for as keywords in articles headlines
# The key of each dict MUST be the symbol used for that coin on Binance
# Use each list to define keywords separated by commas: 'XRP': ['ripple', 'xrp']
# keywords are case sensitive
keywords = {
    'XRP': ['ripple', 'xrp', 'XRP', 'Ripple', 'RIPPLE'],
    'BTC': ['BTC', 'bitcoin', 'Bitcoin', 'BITCOIN'],
    'XLM': ['Stellar Lumens', 'XLM'],
    #'BCH': ['Bitcoin Cash', 'BCH'],
    #'ETH': ['ETH', 'Ethereum'],
    'BNB' : ['BNB', 'Binance Coin'],
    'LTC': ['LTC', 'Litecoin']
    }

# The Buy amount in the PAIRING symbol, by default USDT
# 100 will for example buy the equivalent of 100 USDT in Bitcoin.
QUANTITY = 100

# define what to pair each coin to
# AVOID PAIRING WITH ONE OF THE COINS USED IN KEYWORDS
PAIRING = 'USDT'

# define how positive the news should be in order to place a trade
# the number is a compound of neg, neu and pos values from the nltk analysis
# input a number between -1 and 1
SENTIMENT_THRESHOLD = 0
NEGATIVE_SENTIMENT_THRESHOLD = 0
# define the minimum number of articles that need to be analysed in order
# for the sentiment analysis to qualify for a trade signal
# avoid using 1 as that's not representative of the overall sentiment
MINUMUM_ARTICLES = 1

# define how often to run the code (check for new + try to place trades)
# in minutes
REPEAT_EVERY = 60


############################################
#        END OF USER INPUT VARIABLES       #
#             Edit with care               #
############################################

# coins that bought by the bot since its start
coins_in_hand  = {}
# initializing the volumes at hand
for coin in keywords:
  coins_in_hand[coin] = 0


# current price of CRYPTO pulled through the websocket
CURRENT_PRICE = {}

def ticker_socket(msg):
    '''Open a stream for financial information for CRYPTO'''
    if msg['e'] != 'error':
        global CURRENT_PRICE
        CURRENT_PRICE['{0}'.format(msg['s'])] = msg['c']
    else:
        print('error')


# connect to the websocket client and start the socket
bsm = BinanceSocketManager(client)
for coin in keywords:
    conn_key = bsm.start_symbol_ticker_socket(coin+PAIRING, ticker_socket)
bsm.start()


def calculate_volume():
    '''Calculate the amount of CRYPTO to trade in USDT'''

    while CURRENT_PRICE == {}:
        print('Connecting to the socket...')
        time.sleep(3)
    else:
        volume = {}
        for coin in CURRENT_PRICE:
            volume[coin] = float(QUANTITY / float(CURRENT_PRICE[coin]))
            volume[coin] = float('{:.6f}'.format(volume[coin]))

        return volume


# load the csv file containg top 100 crypto feeds
# want to scan other websites?
# Simply add the RSS Feed url to the Crypto feeds.csv file
with open('Crypto feeds.csv') as csv_file:

    # open the file
    csv_reader = csv.reader(csv_file)

    # remove any headers
    next(csv_reader, None)

    # create empty list
    feeds = []

    # add each row cotaining RSS url to feeds list
    for row in csv_reader:
        feeds.append(row[0])


# TO DO - run this in multiple processes to speed up the scraping
def get_headlines():
    '''Returns the last headline for each link in the CSV file'''

    # add headers to the request for ElementTree. Parsing issues occur without headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0'
    }

    headlines = {'source': [], 'title': [], 'pubDate' : [] }

    for feed in feeds:
        try:
            # grab the XML for each RSS feed
            r = requests.get(feed, headers=headers, timeout=7)

            # define the root for our parsing
            root = ET.fromstring(r.text)

            # identify the last Headline
            channel = root.find('channel/item/title').text
            pubDate = root.find('channel/item/pubDate').text

            # append the source and the title
            headlines['source'].append(feed)

            # append the publication date
            headlines['pubDate'].append(pubDate)


            # some jank to ensure no alien characters are being passed
            headlines['title'].append(channel.encode('UTF-8').decode('UTF-8'))
            print(channel)
        except:
            print(f'Could not parse {feed}')

    return headlines


def categorise_headlines():
    '''arrange all headlines scaped in a dictionary matching the coin's name'''
    # get the headlines
    headlines = get_headlines()
    categorised_headlines = {}

    # this loop will create a dictionary for each keyword defined
    for keyword in keywords:
        categorised_headlines['{0}'.format(keyword)] = []

    # keyword needs to be a loop in order to be able to append headline to the correct dictionary
    for keyword in keywords:

        # looping through each headline is required as well
        for headline in headlines['title']:

            # appends the headline containing the keyword to the correct dictionary
            if any(key in headline for key in keywords[keyword]):
                categorised_headlines[keyword].append(headline)

    return categorised_headlines


def analyse_headlines():
    '''Analyse categorised headlines and return NLP scores'''
    sia = SentimentIntensityAnalyzer()
    categorised_headlines = categorise_headlines()

    sentiment = {}

    for coin in categorised_headlines:
        if len(categorised_headlines[coin]) > 0:
            # create dict for each coin
            sentiment['{0}'.format(coin)] = []
            # append sentiment to dict
            for title in categorised_headlines[coin]:
                sentiment[coin].append(sia.polarity_scores(title))

    return sentiment


def compile_sentiment():
    '''Arranges every compound value into a list for each coin'''
    sentiment = analyse_headlines()
    compiled_sentiment = {}

    for coin in sentiment:
        compiled_sentiment[coin] = []

        for item in sentiment[coin]:
            # append each compound value to each coin's dict
            compiled_sentiment[coin].append(sentiment[coin][sentiment[coin].index(item)]['compound'])

    return compiled_sentiment

def compound_average():
    '''Calculates and returns the average compoud sentiment for each coin'''
    compiled_sentiment = compile_sentiment()
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


def buy(compiled_sentiment, headlines_analysed):
    '''Check if the sentiment is positive and keyword is found for each handle'''
    volume = calculate_volume()

    for coin in compiled_sentiment:

        # check if the sentiment and number of articles are over the given threshold
        if compiled_sentiment[coin] > SENTIMENT_THRESHOLD and headlines_analysed[coin] >= MINUMUM_ARTICLES:

            # check the volume looks correct
            print(f'preparing to buy {volume[coin+PAIRING]} {coin} for {QUANTITY} {PAIRING} at {CURRENT_PRICE[coin+PAIRING]}')

            # create test order before pushing an actual order
            test_order = client.create_test_order(symbol=coin+PAIRING, side='BUY', type='MARKET', quantity=volume[coin+PAIRING])

            # try to create a real order if the test orders did not raise an exception
            try:
                buy_limit = client.create_order(
                    symbol=coin+PAIRING,
                    side='BUY',
                    type='MARKET',
                    quantity=volume[coin+PAIRING]
                )
                coins_in_hand[coin] += volume[coin+PAIRING]

            #error handling here in case position cannot be placed
            except BinanceAPIException as e:
                print(e)

            except BinanceOrderException as e:
                print(e)

            # run the else block if the position has been placed and return some info
            else:
                # retrieve the last order
                order = client.get_all_orders(symbol=coin+PAIRING, limit=1)

                # convert order timsestamp into UTC format
                time = order[0]['time'] / 1000
                utc_time = datetime.fromtimestamp(time)

                # grab the price of CRYPTO the order was placed at for reporting
                bought_at = CURRENT_PRICE[coin+PAIRING]

                # print order condirmation to the console
                print(f"order {order[0]['orderId']} has been placed on {coin} with {order[0]['origQty']} at {utc_time} and bought at {bought_at}")

        else:
            print(f'Sentiment not positive enough for {coin}, or not enough headlines analysed: {compiled_sentiment[coin]}, {headlines_analysed[coin]}')

def sell(compiled_sentiment, headlines_analysed):
    '''Check if the sentiment is negative and keyword is found for each handle'''
    for coin in compiled_sentiment:

        # check if the sentiment and number of articles are over the given threshold
        if compiled_sentiment[coin] < NEGATIVE_SENTIMENT_THRESHOLD and headlines_analysed[coin] >= MINUMUM_ARTICLES and coins_in_hand[coin]>0:

            # check the volume looks correct
            print(f'preparing to sell {coins_in_hand[coin]} {coin} at {CURRENT_PRICE[coin+PAIRING]}')

            # create test order before pushing an actual order
            test_order = client.create_test_order(symbol=coin+PAIRING, side='SELL', type='MARKET', quantity=coins_in_hand[coin]*99.5/100 )

            # try to create a real order if the test orders did not raise an exception
            try:
                buy_limit = client.create_order(
                    symbol=coin+PAIRING,
                    side='SELL',
                    type='MARKET',
                    quantity=coins_in_hand[coin]*99.5/100 
                )
                coins_in_hand[coin]=0
            #error handling here in case position cannot be placed
            except BinanceAPIException as e:
                print(e)

            except BinanceOrderException as e:
                print(e)

            # run the else block if the position has been placed and return some info
            else:
                # retrieve the last order
                order = client.get_all_orders(symbol=coin+PAIRING, limit=1)

                # convert order timsestamp into UTC format
                time = order[0]['time'] / 1000
                utc_time = datetime.fromtimestamp(time)

                # grab the price of CRYPTO the order was placed at for reporting
                sold_at = CURRENT_PRICE[coin+PAIRING]

                # print order condirmation to the console
                print(f"order {order[0]['orderId']} has been placed on {coin} with {order[0]['origQty']} coins sold for {sold_at} each at {utc_time}")


        else:
            print(f'Sentiment not negative enough for {coin}, not enough headlines analysed or not enough {coin} to sell: {compiled_sentiment[coin]}, {headlines_analysed[coin]}')

if __name__ == '__main__':
    print('Press Ctrl-Q to stop the script')
    for i in count():
        compiled_sentiment, headlines_analysed = compound_average()
        print("\nBUY CHECKS:")
        buy(compiled_sentiment, headlines_analysed)
        print("\nSELL CHECKS:")
        sell(compiled_sentiment, headlines_analysed)
        print(f'Iteration {i}')
        time.sleep(60 * REPEAT_EVERY)
