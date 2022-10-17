from tda import auth, client
from tda.orders import equities
import os, datetime
from chalice import Chalice, Cron, UnauthorizedError
from chalicelib import config
from shutil import copyfile

app = Chalice(app_name='tradingview-tdameritrade-alert')

try:
    token_path = os.path.join(os.path.normpath('/tmp'), 'token.json')
    token_exists = os.path.exists(token_path)
    if token_exists == False:
        copyfile(os.path.join(os.path.dirname(__file__), 'chalicelib', 'token.json'), token_path)
except:
    token_path = os.path.join(os.path.dirname(__file__), 'chalicelib', 'token.json')

try:
    c = auth.client_from_token_file(token_path, config.api_key)
except FileNotFoundError:
    c = auth.client_from_manual_flow(config.api_key, 'https://localhost', token_path)

@app.route('/quote/{symbol}')
def quote(symbol):
    response = c.get_quote(symbol)

    return response.json()

# cron job to keep the refresh token alive if no REST calls are made during the expiration window
timezone = datetime.datetime.now().hour - datetime.datetime.utcnow().hour
@app.schedule(Cron(0, 17 - timezone, '?', '*', '1-5', '*')) # Run every Monday - Friday at 1700 local time
def accounts(_):
    response = c.get_accounts()
    print(response.json())
    return

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
    accounts = webhook_message["accounts"]
    size = 1.00 # portion of free equity to allocate to incoming buy orders

    print(webhook_message)
    
    if 'passphrase' not in webhook_message:
        raise UnauthorizedError("Unauthorized, no passphrase")

    if webhook_message['passphrase'] != config.passphrase:
        raise UnauthorizedError("Invalid passphrase")

    for x in accounts:
        if webhook_message['direction'] == "buy":
            price = quote(webhook_message["ticker"]).get(webhook_message["ticker"]).get("askPrice")
            balance = account(x).get("securitiesAccount").get("currentBalances").get("availableFunds")
            quantity = size * (balance // price)
            c.place_order(x, equities.equity_buy_market(webhook_message["ticker"], quantity))
        elif webhook_message['direction'] == "sell":
            quantity = positions(x).get(webhook_message["ticker"])
            if quantity is not None:
                c.place_order(x, equities.equity_sell_market(webhook_message["ticker"], quantity))

    return {
        "code": "ok"
    }