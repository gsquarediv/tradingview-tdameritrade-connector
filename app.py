from tda import auth, client
from tda.orders import equities
import os, json, datetime
from chalice import Chalice
from chalicelib import config

app = Chalice(app_name='tradingview-tdameritrade-alert')

token_path = os.path.join(os.path.dirname(__file__), 'chalicelib', 'token')

c = auth.client_from_token_file(token_path, config.api_key)

@app.route('/quote/{symbol}')
def quote(symbol):
    response = c.get_quote(symbol)

    return response.json()

@app.route('/accounts')
def accounts():
    response = c.get_accounts()

    return response.json()

@app.route('/account/{number}')
def account(number):
    response = c.get_account(number)

    return response.json()

@app.route('/account/{number}/positions')
def positions(number, fields=client.Client.Account.Fields.POSITIONS):
    response = c.get_account(number, fields=client.Client.Account.Fields.POSITIONS)

    positions = response.json().get("securitiesAccount").get("positions")

    simplified = {}
    for x in positions:
        simplified.update({x.get("instrument").get("symbol"): x.get("longQuantity")})

    return simplified

@app.route('/order', methods=['POST'])
def order():
    webhook_message = app.current_request.json_body

    print(webhook_message)
    
    if 'passphrase' not in webhook_message:
        return {
            "code": "error",
            "message": "Unauthorized, no passphrase"
        }

    if webhook_message['passphrase'] != config.passphrase:
        return {
            "code": "error",
            "message": "Invalid passphrase"
        }

    if webhook_message['direction'] == "buy":
        price = quote(webhook_message["ticker"]).get(webhook_message["ticker"]).get("askPrice")
        balance = account(config.account_id).get("securitiesAccount").get("currentBalances").get("availableFunds")
        quantity = balance // price
        response = c.place_order(config.account_id, equities.equity_buy_market(webhook_message["ticker"], quantity))
    elif webhook_message['direction'] == "sell":
        quantity = positions(config.account_id).get(webhook_message["ticker"])
        response = c.place_order(config.account_id, equities.equity_sell_market(webhook_message["ticker"], quantity))

    return {
        "code": "ok"
    }