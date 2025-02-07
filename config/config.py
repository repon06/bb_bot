API_KEYS = {
    "demo": {
        "API_KEY": "v0unD4I4FfynY10Hl1",
        "API_SECRET": "dmBztY3WFwaR8fkm5Of95bPaRAh2J65399FO",
        "BASE_URL": "https://api-demo.bybit.com",
    },
    "real": {
        "API_KEY": "",
        "API_SECRET": "",
        "BASE_URL": "https://api.bybit.com",
    }
}

# API ID и API Hash на https://my.telegram.org/auth
tg_api_id = ''
tg_api_hash = ''
tg_channel_name = '@MYH_System'  # имя канала
session_name = 'session_name'

IS_DEMO = True  # если демо счет - можно вынести в конфигурацию
LOGGING = False  # логировать запросы
WEB_SOCKET_PRIVATE = "wss://stream-demo.bybit.com"
WEB_SOCKET_PUBLIC = "wss://stream.bybit.com"

SYMBOLS = ["YFI/USDT", "OSMO/USDT", "BTC/USDT", "TROY/USDT", "APE/USDT", "DOGE/USDT", "SHIB1000/USDT", "TIA/USDT",
           "1000BONK/USDT",
           "BCH/USDT", "SUSHI/USDT ", "ADA/USDT", "BTT/USDT", "NFT/USDT", "BABYDOGE/USDT", "GCAKE/USDT",
           "3P/USDT", "LADYS/USDT", "COQ/USDT", "SATS/USDT", "PURSE/USDT", "HTX/USDT"]
LEVERAGE = 20  # Плечо х20 кросс
TIMEFRAME = "15m"  # 5
DELTA = 6  # за сколько брать данные - до

TIME_DElTA = 30  # сигнал за эту дельту не рассматривать
TRADE_AMOUNT = 500  # Сумма для покупки в USDT


def debug_enable(exchange, value: bool):
    exchange.verbose = value  # Включение логирования
