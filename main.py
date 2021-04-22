# -*- coding: utf-8 -*-
# # at the very beginning of the script
# # @http://www.gevent.org/intro.html#monkey-patching
# import gevent.monkey
# gevent.monkey.patch_all(ssl=False)
import argparse
import time
import ujson as json
import warnings
warnings.filterwarnings("ignore")

from loguru import logger
from bot import BinanceTradeBot
from utils import str2bool


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=str2bool, nargs='?', const=True, default=False, help="Use test-net or main-net.")
    parser.add_argument("--proxy", type=str2bool, nargs='?', const=True, default=False, help="Use proxy.")
    args = parser.parse_args()
    use_test_net = args.test
    use_proxy = args.proxy

    ak, sk = "", ""
    if use_test_net:
        ak = os.getenv("BINANCE_TEST_NET_API_KEY")
        sk = os.getenv("BINANCE_TEST_NET_SECRET_KEY")
        if ak == None or ak == "" or sk == None or sk == "" :
            logger.critical("please provide BINANCE_TEST_NET_API_KEY and BINANCE_TEST_NET_SECRET_KEY first")
    else:
        ak = os.getenv("BINANCE_MAIN_NET_API_KEY")
        sk = os.getenv("BINANCE_MAIN_NET_SECRET_KEY")
        if ak == None or ak == "" or sk == None or sk == "" :
            logger.critical("please provide BINANCE_MAIN_NET_API_KEY and BINANCE_MAIN_NET_SECRET_KEY first")        

    proxies = {}
    http_proxy, https_proxy = "", ""
    if use_proxy:
        http_proxy = os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("HTTPS_PROXY")
        if http_proxy == None or http_proxy == "" or https_proxy == None or https_proxy == "":
            logger.critical("please provide HTTP_PROXY and HTTPS_PROXY first")
    if http_proxy != "" and https_proxy != "":
        proxies["http"] = http_proxy
        proxies["https"] = https_proxy

    bot = BinanceTradeBot(ak=ak, sk=sk, proxies=proxies, test=use_test_net)
    while not bot.is_ready():
        logger.info("... ... ...")
        time.sleep(2)
    
    fr = open("coin_dict.json", "r")
    coin_dict = json.load(fr)
    fr.close()
    bot.prepare_coins(coin_dict)
    fr = open("feeds.txt", "r")
    feed_list = [line.strip() for line in fr.readlines()]
    fr.close()
    bot.prepare_rss_feeds(feed_list)
    bot.prepare_lot_size()

    for i in count():
        compiled_sentiment, analysed_headlines = bot.compound_average()
        logger.info("BUY CHECKS:")
        bot.buy(compiled_sentiment, analysed_headlines)
        logger.info("SELL CHECKS:")
        bot.sell(compiled_sentiment, analysed_headlines)
        logger.info("Iteration {}".format(i))
        time.sleep(600)
