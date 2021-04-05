from datetime import datetime, date, timedelta
import requests, json, re, os


sentiment_key = os.getenv('sentiment_key')
websearch_key = os.getenv('websearch_key')

# user input variables
# The key can be fed to the trading terminal for a position request.
# Values are keyowrds to search the web for
crypto_key_pairs = {"BTCUSD":"Bitcoin", "ETHUSD":"Ethereum", "LTCUSD":"Litecoin", "XRPUSD":"Ripple", "BATUSD":"BATUSD, basic attention token", "DSHUSD":"Dash Coin", "EOSUSD":"EOS", "ETCUSD":"ETC", "IOTUSD":"IOTA", "NEOUSD":"NEO", "OMGUSD":"OMISE Go", "TRXUSD":"Tron", "XLMUSD":"Stellar Lumens", "XMRUSD":"Monero", "ZECUSD":"Zcash"}
#define from published date
date_since = date.today() - timedelta(days=1)

#store inputs in different lists
cryptocurrencies = []
crypto_keywords = []

#Storing keys and values in separate lists. Keys are used with the MT5 API while Values stand as values for the sentiment analysis
for i in range(len(crypto_key_pairs)):
    cryptocurrencies.append(list(crypto_key_pairs.keys())[i])
    crypto_keywords.append(list(crypto_key_pairs.values())[i])


# Search the web for news unsing the websearch api, send a request for each crypto in cryprocurrencies
def get_news_headlines():
    '''Search the web for news headlines based the keywords in the global variable'''
    news_output = {}

    #TO DO - looping through keywords created odd looking dicts. Gotta loop through keys instead.
    for crypto in crypto_keywords:

        #create empty dicts in the news output
        news_output["{0}".format(crypto)] = {'description': [], 'title': []}

        #configure the fetch request and select date range. Increase date range by adjusting timedelta(days=1)
        url = "https://contextualwebsearch-websearch-v1.p.rapidapi.com/api/search/NewsSearchAPI"
        querystring = {"q":str(crypto),"pageNumber":"1","pageSize":"30","autoCorrect":"true","fromPublishedDate":date_since,"toPublishedDate":"null"}
        headers = {
            'x-rapidapi-key': websearch_key,
            'x-rapidapi-host': "contextualwebsearch-websearch-v1.p.rapidapi.com"
            }

        #get the raw response
        response = requests.request("GET", url, headers=headers, params=querystring)

        # convert response to text format
        result = json.loads(response.text)

        #store each headline and description in the dicts above
        for news in result['value']:
            news_output[crypto]["description"].append(news['description'])
            news_output[crypto]["title"].append(news['title'])

    return news_output


def analyze_headlines():
    '''Analyse each headline pulled trhough the API for each crypto'''
    news_output = get_news_headlines()

    for crypto in crypto_keywords:

        #empty list to store sentiment value
        news_output[crypto]['sentiment'] = {'pos': [], 'mid': [], 'neg': []}

        # analyse the description sentiment for each crypto news gathered
        if len(news_output[crypto]['description']) > 0:
            for title in news_output[crypto]['title']:

                # remove all non alphanumeric characters from payload
                titles = re.sub('[^A-Za-z0-9]+', ' ', title)

                import http.client
                conn = http.client.HTTPSConnection('text-sentiment.p.rapidapi.com')

                #format and sent the request
                payload = 'text='+titles
                headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'x-rapidapi-key': sentiment_key,
                    'x-rapidapi-host': 'text-sentiment.p.rapidapi.com'
                    }
                conn.request("POST", "/analyze", payload, headers)

                #get the response and format it
                res = conn.getresponse()
                data = res.read()
                title_sentiment = json.loads(data)

                #assign each positive, neutral and negative count to another list in the news output dict
                if not isinstance(title_sentiment, int):
                    if title_sentiment['pos'] == 1:
                        news_output[crypto]['sentiment']['pos'].append(title_sentiment['pos'])
                    elif title_sentiment['mid'] == 1:
                        news_output[crypto]['sentiment']['mid'].append(title_sentiment['mid'])
                    elif title_sentiment['neg'] == 1:
                        news_output[crypto]['sentiment']['neg'].append(title_sentiment['neg'])
                    else:
                        print(f'Sentiment not found for {crypto}')

    return news_output


def calc_sentiment():
    '''Use the sentiment returned in the previous function to calculate %'''
    news_output = analyze_headlines()

    #re-assigned the sentiment list value to a single % calc of all values in each of the 3 lists
    for crypto in crypto_keywords:

        #length of title list can't be 0 otherwise we'd be dividing by 0 below
        if len(news_output[crypto]['title']) > 0:

            news_output[crypto]['sentiment']['pos'] = len(news_output[crypto]['sentiment']['pos'])*100/len(news_output[crypto]['title'])
            news_output[crypto]['sentiment']['mid'] = len(news_output[crypto]['sentiment']['mid'])*100/len(news_output[crypto]['title'])
            news_output[crypto]['sentiment']['neg'] = len(news_output[crypto]['sentiment']['neg'])*100/len(news_output[crypto]['title'])

            #print the output  for each coin to verify the result
            print(crypto, news_output[crypto]['sentiment'])

    return news_output

# TO DO - If integrated with an exhange, add weight logic to avid placing a trade
# when only 1 article is found and the sentiment is positive.

#call the function
#Delete Call if adding trading logic. Assign the function to a variable instead.
calc_sentiment()
