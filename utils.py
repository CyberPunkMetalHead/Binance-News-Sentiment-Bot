# -*- coding: utf-8 -*-
import argparse
import requests
import ujson as json
from loguru import logger


def fetch_coin_list():
    proxies = {
        "http": "http://172.16.1.135:3128/",
        "https": "http://172.16.1.135:3128/",
    }
    r = requests.get(url="https://open.aicoin.cn/api/v1/coin-list", proxies=proxies)
    if r.status_code == 200:
        with open("coin_list.json", "w") as fw:
            json.dump(fw, r.json(), indent=4)
    else:
        logger.critical("Failed to fetch coin list from aicoin, status code: {}.".format(r.status_code))


def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


if __name__ == "__main__":
    fetch_coin_list()
