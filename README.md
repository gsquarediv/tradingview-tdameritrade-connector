# tradingview-tdameritrade-connector

This AWS Chalice app functions as a serverless connector between TradingView alert webhooks and the TD Ameritrade API,

TD Ameritrade API equity orders from TradingView webhook alerts

This project was originally forked from PartTimeLarry's option bot. Repurposed to support the following functionality:
* Replaced the option orders with equity orders - it is no longer possible to place option orders with this fork
* Ability to adjust order size based on account equity (buys only)
* Ability to place the same order on multiple accounts
* Token generation is now performed in the app, negating the need to copy a preexisting token from elsewhere
* Token is now stored in S3 and periodically refreshed to eliminate the need to manually acquire a fresh token upon expiry and redeploy the entire package
* Base64 encoded the passphrase to avoid issues with special characters in the passphrase
* HTTP error codes returned from TD Ameritrade are now logged
* Futures are now supported assets to trade (beta)

## PartTimeLarry's YouTube tutorial:

https://www.youtube.com/watch?v=-wT9h9Nc9sk

## Installation

```
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

## TradingView message format

```
{
    "ticker": "{{ticker}}",
    "direction": "{{strategy.order.action}}",
    "passphrase": "Base64EncodedPassphrase",
    "accounts": ["123456789"],
    "size": 1.00
}
```
