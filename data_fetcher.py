from datetime import datetime, timedelta
from typing import Optional

import ccxt

from config import IS_DEMO, LOGGING, DELTA, LEVERAGE, SYMBOLS, debug_enable
from helper.calculate import calculate_support_resistance, \
    calculate_take_profit_using_resistance, calculate_ema_take_profit, calculate_take_profit_using_atr, \
    calculate_fibonacci_levels, calculate_dynamic_take_profit, calculate_combined_take_profits, calculate_volatility, \
    calculate_average_volatility, calculate_long_stop_loss_atr, calculate_trailing_long_stop_loss
from helper.date_helper import to_timestamp
from helper.design import green, yellow, red
from helper.json_helper import print_info
from indicators import calculate_indicators
from orders import open_long_position_with_tp_sl


def get_exchange(api_keys, is_demo=False):
    env = "demo" if is_demo else "real"
    keys = api_keys[env]

    # Создание подключения к Bybit
    exchange = ccxt.bybit(
        {'apiKey': keys["API_KEY"],
         'secret': keys["API_SECRET"], 'urls': {
            'api': {
                'public': keys["BASE_URL"],
                'private': keys["BASE_URL"],
            }
        },
         'enableRateLimit': True,
         'options': {'defaultType': 'swap'}
         # 'options': {'defaultType': 'future'} # чтобы все запросы шли к фьючерсному API
         })

    # Включение демо-торговли, если это указано
    exchange.enable_demo_trading(is_demo)
    debug_enable(exchange, LOGGING)
    return exchange


def fetch_candles(exchange, symbol, timeframe, since):
    return exchange.fetch_ohlcv(symbol, timeframe, since)


def fetch_recent_data(exchange, symbol: str, timeframe: str, start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None, limit: int = 100):
    """
    Загружает данные свечей (OHLCV) для заданного символа и таймфрейма.

    :param exchange: Объект биржи (ccxt)
    :param symbol: Символ валютной пары (например, "BTC/USDT")
    :param timeframe: Таймфрейм свечей (например, "5m")
    :param start_date: Начальная дата диапазона (datetime, по умолчанию None - за последний час)
    :param limit: Количество свечей (по умолчанию 100)
    :return: Список свечей OHLCV
    """
    if start_date is not None and end_date is None:
        since = to_timestamp(start_date)
    elif start_date is not None and end_date is not None:
        start_timestamp = to_timestamp(start_date)
        end_timestamp = to_timestamp(end_date)

        candles = []
        while start_timestamp < end_timestamp:
            new_candles = exchange.fetch_ohlcv(symbol, timeframe, since=start_timestamp, limit=limit)
            if not new_candles: break
            candles.extend(new_candles)
            start_timestamp = new_candles[-1][0] + 1
        return candles
    else:
        since = int((datetime.now() - timedelta(hours=DELTA)).timestamp() * 1000)
    return exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)


def fetch_data_for_interval(exchange, symbol: str, timeframe: str, start_date: str, end_date: str, limit: int = 100):
    start_timestamp = to_timestamp(start_date)
    end_timestamp = to_timestamp(end_date)

    candles = []
    while start_timestamp < end_timestamp:
        new_candles = exchange.fetch_ohlcv(symbol, timeframe, since=start_timestamp, limit=limit)
        if not new_candles:
            break
        candles.extend(new_candles)
        start_timestamp = new_candles[-1][0] + 1

    return candles


def get_filtered_markets(exchange):
    markets = exchange.load_markets()

    # Фильтрация только спотовых рынков и только SYMBOLS
    markets = {symbol: market for symbol, market in markets.items()
               # if market['type'] == 'spot'
               # if market['type'] == 'linear'
               # if market['type'] == 'swap' # market['type'] == 'swap' выбирает только бессрочные контракты
               if symbol.split(':USDT')[0] in SYMBOLS
               }
    print(f"Доступные рынки на {green('demo') if IS_DEMO else yellow('real')}:", list(markets.keys()))
    return markets


def check_symbol_exists(exchange, symbol) -> str:
    """
    Проверяет наличие криптопары на бирже.
    """
    try:
        # Загружаем рынки
        markets = exchange.load_markets()
        possible_quotes = ['USDT']

        for quote in possible_quotes:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                formatted_symbol = f"{base}/{quote}"

                # Проверка на наличие символа с постфиксом
                for market in markets.keys():
                    if market.startswith(formatted_symbol):
                        print(f"Криптопара {green(symbol)} найдена на Bybit как {market}.")
                        return market

        print(f"Криптопара {red(symbol)} не найдена на Bybit!")
        return None
    except Exception as e:
        print(f"Ошибка при проверке символа {symbol}: {e}")
        return None


def check_symbol_exists(exchange, symbol):
    """
    Проверяет наличие криптопары на бирже, приоритет — perpetual.
    """
    try:
        markets = exchange.load_markets()
        if symbol.endswith('USDT'):
            base = symbol[:-4]
            perp_symbol = f"{base}/USDT:USDT"  # perpetual
            spot_symbol = f"{base}/USDT"  # spot

            if perp_symbol in markets:
                print(f"Криптопара {symbol} найдена как {perp_symbol} (perpetual).")
                return perp_symbol

            if spot_symbol in markets:
                print(f"Криптопара {symbol} найдена как {spot_symbol} (spot).")
                return spot_symbol

        print(f"Криптопара {symbol} не найдена.")
        return None
    except Exception as e:
        print(f"Ошибка при проверке символа {symbol}: {e}")
        return None


def load_open_swap_order(exchange, symbol):
    return exchange.fetch_open_orders(symbol=symbol)


def test_open_long_swap(exchange, symbol):
    candles = fetch_recent_data(exchange, symbol=symbol, timeframe="5m", limit=100)
    # Рассчитать все индикаторы
    df = calculate_indicators(candles)
    print_info(df, symbol=symbol)
    ################################################################
    current_price = exchange.fetch_ticker(symbol)['last']  # Текущая цена
    # Пример:
    resistance_level = calculate_support_resistance(df)[0]
    take_profit1 = calculate_take_profit_using_resistance(current_price, resistance_level)
    print(f"Take-profit по high/low:{take_profit1}")
    # Пример:
    take_profit1 = calculate_ema_take_profit(df)
    print(f"Take-profit по EMA: {take_profit1}")
    # Пример:
    take_profit3 = calculate_take_profit_using_atr(df)
    print(f"Take-profit по ATR: {take_profit3}")
    # Пример:
    volatility = max(calculate_volatility(df), calculate_average_volatility(df))
    take_profit4 = calculate_dynamic_take_profit(current_price, volatility)
    print("Take-profit по волантильности: " + str(take_profit4))
    # Пример:
    low, high = df['low'].min(), df['high'].max()
    take_profit7 = calculate_fibonacci_levels(low, high)
    print(f"Take-profit по fibonachi: {str(take_profit7)}")
    # Пример:
    take_profit5 = calculate_combined_take_profits(current_price, df)
    print("Take-profit по combine: " + str(take_profit5))
    # Пример:
    stop_loss1 = calculate_long_stop_loss_atr(df, atr_multiplier=2)
    print(f"Stop Loss: {stop_loss1:.2f}")
    # Пример:
    trailing_percentage = 0.02  # 2%
    stop_loss2 = calculate_trailing_long_stop_loss(current_price, trailing_percentage)
    print(f"Trailing Stop Loss: {stop_loss2:.2f}")
    ################################################################
    open_long_position_with_tp_sl(exchange, symbol, LEVERAGE, take_profit7, stop_loss2)
