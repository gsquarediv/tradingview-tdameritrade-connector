import json
import math
import os
import httpx
from base64 import b64decode

import boto3
from chalice import Chalice, UnauthorizedError, Rate
from tda import auth, client
from tda.orders import equities

from chalicelib import config

app = Chalice(app_name='tradingview-tdameritrade-alert')

# Get a fresh token from TD Ameritrade and upload it to AWS S3
def get_new_token():
    s3 = boto3.client('s3')
    token_path = os.path.join(os.path.dirname(__file__), 'chalicelib', 'token.json')
    auth.client_from_manual_flow(config.api_key, 'https://localhost', token_path)
    s3.upload_file(token_path, 'td-ameritrade', 'token.json')
    return

def read_token():
    s3 = boto3.client('s3')
    try:
        s3_object = s3.get_object(Bucket='td-ameritrade', Key='token.json')
    except s3.exceptions.NoSuchKey:
        get_new_token()
        s3_object = s3.get_object(Bucket='td-ameritrade', Key='token.json')
    s3token = json.loads(s3_object['Body'].read().decode('utf-8'))
    return s3token

def write_token(token, *args, **kwargs):
    s3 = boto3.client('s3')
    s3.put_object(Body=json.dumps(token), Bucket='td-ameritrade', Key='token.json')
    return

c = auth.client_from_access_functions(config.api_key, token_read_func=read_token, token_write_func=write_token)

# Cron job to keep the refresh token alive if no REST calls are made during the expiration window
@app.schedule(Rate(1, unit=Rate.DAYS)) # Run once per day
def keep_alive(self):
    c.ensure_updated_refresh_token()
    print("Token refreshed.")
    return

@app.route('/quote/{symbol}')
def get_quote(symbol):
    response = c.get_quotes(symbol)

    return response.json()

def calculate_notional_value(quote):
    if quote.get("assetType") == c.Markets.FUTURE.name:
        price = quote.get("askPriceInDouble") * quote.get("futureMultiplier")
    else:
        price = quote.get("askPrice")
    return price

def account(number):
    response = c.get_account(number)

    return response.json()

def positions(number):
    response = c.get_account(number, fields=client.Client.Account.Fields.POSITIONS)

    positions = response.json().get("securitiesAccount").get("positions")

    simplified = {}
    for x in positions:
        simplified.update({x.get("instrument").get("symbol"): x.get("longQuantity")})

    return simplified

@app.route('/order', methods=['POST'])
def order():
    webhook_message = app.current_request.json_body
    ticker = webhook_message['ticker']

    print(webhook_message)
    
    if 'passphrase' not in webhook_message:
        raise UnauthorizedError("Unauthorized, no passphrase")

    try:
        if str(b64decode(webhook_message['passphrase']), "utf-8") != config.passphrase:
            raise UnauthorizedError("Invalid passphrase")
    except:
        raise UnauthorizedError("Invalid passphrase")

    for x in webhook_message['accounts']:
        if webhook_message['direction'] == "buy":
            quote = get_quote(ticker).get(ticker)
            price = calculate_notional_value(quote)
            balance = account(x).get("securitiesAccount").get("currentBalances").get("availableFunds")
            quantity = math.floor(webhook_message['size'] * (balance / price))
            response = c.place_order(x, equities.equity_buy_market(ticker, quantity))
            try: 
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                print(json.dumps(response.json(), indent=4))
                raise e
        elif webhook_message['direction'] == "sell":
            quantity = positions(x).get(ticker)
            if quantity is not None:
                response = c.place_order(x, equities.equity_sell_market(ticker, quantity))
                try: 
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(json.dumps(response.json(), indent=4))
                    raise e

    return {
        "code": "ok"
    }