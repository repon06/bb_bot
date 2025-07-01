from datetime import datetime, timezone
from typing import List

import array
import ccxt
import math

from config import LEVERAGE, TRADE_AMOUNT
from helper.calculate import determine_trade_type
from helper.design import red, green, yellow
from helper.json_helper import get_error


def open_position(exchange, symbol, side, amount):
    return exchange.create_order(symbol, type="market", side=side, amount=amount)


def create_market_long_order(exchange, symbol, amount, params=None):
    try:
        # Рыночный ордер на покупку
        order = exchange.create_market_buy_order(symbol, amount, params=params)
        print(f"Рыночный ордер на покупку открыт: {order}")
        return order
    except Exception as e:
        print(f"Ошибка при открытии позиции bybit: {get_error(e)}")
        return None


def open_long_position(exchange, symbol, amount, current_price, take_profits: array = None, stop_loss: float = None):
    """
    Открывает LONG позицию с тейк-профитами и стоп-лоссом.
    """
    print(f"Открытие LONG позиции {red(symbol)} на {amount:.0f} за {current_price:.10f} "
          f"с тейк-профитом {take_profits} и стоп-лоссом {stop_loss:.10f}")
    if take_profits is None and stop_loss is None:

        take_profits = [current_price * 1.015, current_price * 1.03, current_price * 1.06]
        stop_loss = current_price * 0.98

    order = create_market_long_order(exchange, symbol, amount)

    if order is not None:
        set_take_profits(exchange, symbol, amount, take_profits)

        set_stop_loss_market(exchange, symbol, stop_loss, amount)

        print(f"{green("Открыта") if order is not None else red("Не открыта")} LONG позиция "
              f"на {symbol} с тейк-профитом и стоп-лоссом.")
    return order


def open_long_position_old(exchange, symbol, amount, current_price):
    take_profits = [current_price * 1.015, current_price * 1.03, current_price * 1.06]
    stop_loss = current_price * 0.98

    print(f"открытие long позиции {red(symbol)} на {amount:.0f} за {current_price:.10f}")
    order = create_market_long_order(exchange, symbol, amount)

    set_take_profits(exchange, symbol, amount / len(take_profits), take_profits)

    exchange.create_order(symbol, type='stop_loss_limit', side='sell', amount=amount, price=stop_loss,
                          params={'stopPrice': stop_loss})

    print(f"Открыта Long позиция на {symbol} с тейк-профитом и стоп-лоссом.")
    return order


def set_take_profits(exchange, symbol, amount, take_profits: List[float]):
    for i, tp in enumerate(take_profits, start=1):
        try:
            order_tp = exchange.create_limit_sell_order(symbol, amount, tp)
            filled_amount = order_tp['filled']
            print(f"Тейк-профит {i}: {tp:.10f}")
        except Exception as e:
            print(f"Ошибка установки тейк-профита {i} bybit: {get_error(e)}")


def set_stop_loss_market(exchange, symbol, stop_price, amount):
    try:
        # exchange.create_stop_loss_limit_order(symbol, amount, stop_loss)
        order = exchange.create_order(
            symbol=symbol,
            type='stop_loss_market',
            side='sell',
            amount=amount,
            params={
                'stopPrice': stop_price
            }
        )
        print("Стоп-лосс рыночный установлен:", order)
    except Exception as e:
        print("Ошибка установки стоп-лосса:", get_error(e))


def set_leverage(exchange, symbol, leverage):
    """
    Устанавливает плечо для заданного символа.
    """
    market = exchange.market(symbol)
    if 'linear' in market['type']:
        exchange.private_post_private_linear_position_set_leverage({
            'symbol': market['id'],
            'buy_leverage': leverage,
            'sell_leverage': leverage
        })
        exchange.options['leverage'] = LEVERAGE
    else:
        print(f"Leverage setting not supported for {symbol}")


def print_order_info(exchange, order_id, symbol):
    try:
        order_info = exchange.fetch_order(order_id, symbol, {"acknowledged": True})
        print(f"Информация о ордере {order_id}:")
        print(order_info)
    except ccxt.BaseError as e:
        print(f"Ошибка при получении данных о ордере: {e}")
        print(f"Сообщение ошибки: {e.args[0]}")


def check_and_open_long_order(exchange, symbol, usdt_balance, take_profits: array = None, stop_loss: float = None):
    market = exchange.market(symbol)
    min_order_qty = market['limits']['amount']['min']
    min_order_amt = market['limits']['cost']['min']
    max_order_qty = market['limits']['amount']['max']

    current_price = exchange.fetch_ticker(symbol)['last']

    required_amount_in_usdt = min_order_qty * current_price
    # max_amount_in_usdt = max_order_qty * current_price
    if required_amount_in_usdt < 5: required_amount_in_usdt = 5

    if usdt_balance < required_amount_in_usdt:
        print(f"Недостаточно средств для покупки {min_order_qty} {symbol}. Нужно {required_amount_in_usdt:.2f} USDT.")
    else:
        print(
            f"Для покупки мин кол-ва монет ({min_order_qty}) на рынке {symbol}, нужно потратить: {required_amount_in_usdt:.2f} USDT.")
        print(f"Доступно для покупки {usdt_balance:.2f} USDT. Ордер можно разместить.")

    print(f"У меня должно быть usdt: {required_amount_in_usdt:.2f} "
          f"я имею usdt: {usdt_balance} "
          f"цена за 1: {current_price:.10f} "
          f"минимум: {min_order_qty:.2f} ")

    if required_amount_in_usdt < min_order_amt:
        print(f"Минимальная сумма для ордера: {min_order_amt} USDT. Увеличьте сумму.")
        min_amount_in_symbol = min_order_amt / current_price
        min_amount_in_symbol = math.ceil(
            min_amount_in_symbol / min_order_qty) * min_order_qty
    else:
        min_amount_in_symbol = min_order_qty

    print(f"Минимальное количество монет для ордера: {min_amount_in_symbol:.2f}")

    order = open_long_position(exchange, symbol, min_amount_in_symbol, current_price, take_profits, stop_loss)
    return order


def open_short_position(exchange, symbol, amount, take_profits, stop_loss, leverage):
    """
    Открывает короткую позицию на рынке с заданным плечом, тейк-профитом и стоп-лоссом.
    """
    try:
        exchange.set_leverage(leverage, symbol)
        print(f"Плечо {leverage}x установлено для {symbol}.")

        order = exchange.create_market_sell_order(symbol, amount)
        print(f"Рыночный ордер на продажу открыт: {order}")

        for i, tp in enumerate(take_profits, start=1):
            try:
                tp_order = exchange.create_limit_buy_order(symbol, amount, tp)
                print(f"Тейк-профит {i} установлен на уровне {tp}: {tp_order}")
            except Exception as e:
                print(f"Ошибка установки тейк-профита {i}: {e}")

        try:
            stop_loss_order = exchange.create_order(
                symbol,
                type="stop_loss_limit",
                side="buy",
                amount=amount,
                price=stop_loss,
                params={"stopPrice": stop_loss}  # Указываем триггер-цену
            )
            print(f"Стоп-лосс установлен на уровне {stop_loss}: {stop_loss_order}")
        except Exception as e:
            print(f"Ошибка установки стоп-лосса: {e}")

    except Exception as e:
        print(f"Ошибка при открытии короткой позиции: {e}")


def open_long_position_with_tp_sl(exchange, symbol, leverage, take_profits=None, stop_loss=None):
    current_price = exchange.fetch_ticker(symbol)['last']
    usdt_balance = exchange.fetch_balance()['USDT']['free']

    if take_profits is None:
        take_profits = [round(current_price * 1.015, 4), round(current_price * 1.03, 4), round(current_price * 1.06, 4)]
    if stop_loss is None:
        stop_loss = round(current_price * 0.98, 4)

    market = exchange.market(symbol)
    market_type = market['type']
    precision_amount = market['precision']['amount']
    lot_size = market['limits']['amount']['min']

    min_order_qty = market['limits']['amount']['min']
    max_order_qty = market['limits']['amount']['max']

    print(f"Market type: {market_type}, Precision: {precision_amount}, Lot size: {lot_size}")

    if market_type not in ['swap', 'future']:
        print("Недопустимый тип рынка")
        return

    position = exchange.fetch_position(symbol)
    current_leverage = position.get('leverage', None)

    try:
        if current_leverage != leverage:
            exchange.set_leverage(leverage, symbol)
            print(f"Плечо для {symbol} установлено на {leverage}")
    except Exception as e:
        print(f"Ошибка при установке плеча: {e}")

    contract_size = usdt_balance / current_price
    amount_in_contracts = round(contract_size / lot_size) * lot_size

    if amount_in_contracts > max_order_qty:
        amount_in_contracts = max_order_qty
    if amount_in_contracts < min_order_qty:
        amount_in_contracts = min_order_qty

    cost = amount_in_contracts * current_price
    min_order_amt = market['limits']['cost'].get('min', 1.0)
    if min_order_amt is None: min_order_amt = 1
    if cost < min_order_amt:
        print(f"Стоимость ордера {cost:.2f} ниже минимальной стоимости сделки {min_order_amt:.2f} USDT")
        return

    print(f"Открытие LONG позиции на {symbol} с кол-вом контрактов: {amount_in_contracts}, стоимостью: {cost:.2f} USDT")

    try:
        params = {"category": "linear"}
        order = create_market_long_order(exchange, symbol, amount_in_contracts, params=params)
        print(f"Рыночный ордер на покупку открыт: {order}")
    except Exception as e:
        print(f"Ошибка при открытии ордера: {e}")
        return

    set_take_profits(exchange, symbol, amount_in_contracts / len(take_profits), take_profits)

    set_stop_loss_2(exchange, symbol, stop_loss, amount_in_contracts)


def open_long_position_with_tp_sl_OLD(exchange, symbol, leverage, take_profits=None, stop_loss=None):
    current_price = exchange.fetch_ticker(symbol)['last']
    usdt_balance = exchange.fetch_balance()['USDT']['free']

    if take_profits is None:
        take_profits = [round(current_price * 1.015, 4), round(current_price * 1.03, 4), round(current_price * 1.06, 4)]
    if stop_loss is None:
        stop_loss = round(current_price * 0.98, 4)

    market = exchange.market(symbol)
    market_type = market['type']
    precision_amount = int(market['precision']['amount']) \
        if market['precision']['amount'] > 1 \
        else market['precision']['amount']
    print("Market: " + market_type)
    print(f"Максимально допустимое количество контрактов для {symbol}: {market['limits']['amount']['max']}")
    print(f"Точность контрактов для {symbol}: {precision_amount}")
    if market_type not in ['swap', 'future']:
        return
    position = exchange.fetch_position(symbol)
    current_leverage = position.get('leverage', None)

    try:
        # Установка плеча
        if market_type in ['swap', 'future']:
            params = {"category": "linear"}
            if current_leverage != leverage:
                exchange.set_leverage(leverage, symbol)
                # ccxt.base.errors.BadRequest: bybit = leverage not modified
                # "retMsg":"buy leverage invalid"
    except Exception as e:
        print(f"ОШИБКА: {get_error(e)}")

    min_order_qty = market['limits']['amount']['min']
    min_order_amt = market['limits']['cost']['min']
    max_order_qty = market['limits']['amount']['max']
    amount_in_symbol = usdt_balance / current_price
    amount = max(min_order_qty, amount_in_symbol)
    amount = round(amount // precision_amount) * precision_amount

    if min_order_amt is None or min_order_amt != min_order_amt:
        min_order_amt = 1.0

    if amount < min_order_qty:
        amount = min_order_qty
    if amount > max_order_qty:
        amount = max_order_qty

    cost = amount * current_price
    if cost < min_order_amt:
        print(f"Стоимость ордера {cost:.2f} ниже минимальной {min_order_amt:.2f}")
        return

    required_amount_in_usdt = amount * current_price
    if required_amount_in_usdt < min_order_amt:
        raise ValueError(f"Минимальная сумма сделки: {min_order_amt} USDT. Недостаточно средств.")

    print(
        f"Открытие LONG позиции на {symbol} с кол-вом: {amount:.2f}, стоимостью: {required_amount_in_usdt:.2f} USDT, max allowed: {max_order_qty}")

    # debug_enable(exchange, True)
    order = create_market_long_order(exchange, symbol, amount, params=params)
    # bybit {"retCode":10001,"retMsg":"The number of contracts exceeds maximum limit allowed: too large, order_qty:8305400000000 \u003e max_qty:2400000000000"
    # debug_enable(exchange, False)
    print(f"Рыночный ордер на покупку открыт: {order}")
    print_order_info(exchange, order['id'], symbol)
    filled_amount = order['filled']

    set_take_profits(exchange, symbol, amount / len(take_profits), take_profits)

    set_stop_loss_2(exchange, symbol, stop_loss, amount)


def set_stop_loss_2(exchange, symbol, stop_loss, amount):
    try:
        sl_order = exchange.create_order(
            symbol=symbol,
            type="market",  # Рыночный ордер
            side="sell",
            amount=amount,
            params={
                "triggerPrice": stop_loss,
                "reduceOnly": True,
                "category": "linear",
                "triggerDirection": 2
            }
        )
        print(f"Стоп-лосс установлен на {stop_loss}: {sl_order}")
    except Exception as e:
        print(f"Ошибка установки стоп-лосса: {get_error(e)}")


def move_stop_to_breakeven(exchange, symbol, entry_price, remaining_amount):
    """
    Перемещает стоп-лосс в точку безубыточности.
    """
    try:
        # Удаляем старый стоп-лосс (если необходимо)
        # exchange.cancel_all_orders(symbol, params={"reduceOnly": True})

        sl_order = exchange.create_order(
            symbol=symbol,
            type="market",
            side="sell",
            amount=remaining_amount,
            params={
                "triggerPrice": entry_price,
                "reduceOnly": True,
                "category": "linear",
                "triggerDirection": 2
            }
        )
        print(f"Стоп-лосс перемещен в точку безубытка: {sl_order}")
    except Exception as e:
        print(f"Ошибка при переносе стоп-лосса в безубыток: {get_error(e)}")


def check_and_move_to_breakeven(exchange, symbol, entry_price, tp1_price, remaining_amount):
    """
    Проверяет достижение TP1 и перемещает стоп-лосс в безубыток.
    """
    try:
        ticker = exchange.fetch_ticker(symbol)
        last_price = ticker['last']

        if last_price >= tp1_price:
            print(f"Цена достигла TP1 ({tp1_price}). Перемещаем стоп-лосс в безубыток.")
            move_stop_to_breakeven(exchange, symbol, entry_price, remaining_amount)
        else:
            print(f"Цена еще не достигла TP1 ({tp1_price}). Текущая цена: {last_price}")
    except Exception as e:
        print(f"Ошибка при проверке TP1: {get_error(e)}")


def is_market_order_open(exchange, symbol: str):
    """проверить если такой ордер открыт"""
    order_list = exchange.fetch_open_orders(symbol)
    order_list = [order for order in order_list if order['type'] == 'market' and order['status'] == 'open']
    print(f"Открытых ордеров {symbol}: {len(order_list)}")
    # 'orderType': 'Limit' type='limit'
    return len(order_list) > 0


def open_order_with_tps_sl(exchange, market_symbol, buy_price, take_profits, stop_loss):
    """
    Открывает сделку на Bybit (лонг или шорт), автоматически определяет тип сделки,
    устанавливает тейк-профиты и стоп-лосс, и возвращает список ID ордеров.

    Аргументы:
    exchange -- экземпляр объекта ccxt биржи
    market_symbol -- строка в формате 'POWR/USDT:USDT'
    buy_price -- цена входа в сделку
    take_profits -- список целей для тейк-профитов
    stop_loss -- уровень стоп-лосса

    Возвращает:
    Список ID ордеров []
    """
    try:
        market_type = get_market_type(exchange, market_symbol)
        print(f"Тип рынка для {market_symbol}: {market_type}")

        ticker = exchange.fetch_ticker(market_symbol)
        current_price = ticker['last']
        print(
            f"Текущая рыночная цена для {market_symbol}: {green(current_price)}\n"
            f"Мы указывали цену открытия ордера: {red(buy_price)}")

        initial_trade_type = determine_trade_type(buy_price, take_profits, stop_loss)
        if not initial_trade_type:
            print("Не удалось определить начальный тип сделки. Проверьте значения buy_price, take_profits и stop_loss.")
            return []

        trade_type = determine_trade_type(buy_price, take_profits, stop_loss, current_price)
        if not trade_type:
            print("Текущая цена изменяет логику сделки, сделка не будет открыта.")
            return []

        if initial_trade_type != trade_type:
            print(f"Тип сделки изменился: с {initial_trade_type} на {trade_type}. Ордер не будет открыт.")
            return []

        market_info = exchange.market(market_symbol)
        min_order_size = market_info['limits']['amount']['min']

        order_amount = TRADE_AMOUNT / current_price
        if order_amount < min_order_size:
            print(f"Количество ордера {order_amount} меньше минимально допустимого {min_order_size}.")
            return []

        print(
            f"Открываем {green(initial_trade_type)} ордер на {order_amount:.6f} {market_symbol} по цене {current_price}.")
        order = exchange.create_order(
            symbol=market_symbol,
            type='market',
            side='buy' if trade_type == 'long' else 'sell',
            amount=order_amount
        )

        print(f"Ордер {initial_trade_type} на вход открыт: {order['id']}")
        order_id = order['id']
        # entry_order['id'] = order['id']

        order_ids = {'symbol': market_symbol, 'order': order_id, 'take_profits': [], 'stop_loss': None}

        tp_order_ids = set_take_profit(exchange, market_symbol, trade_type, order_amount, take_profits)
        # order_ids.extend(tp_order_ids)  # Добавляем ID ордеров тейк-профитов в общий список
        order_ids['take_profits'].extend(tp_order_ids)

        sl_order_id = retry_set_stop_loss(exchange, market_symbol, trade_type, order_amount, stop_loss)

        if sl_order_id:
            # order_ids.append(sl_order_id)  # Добавляем ID ордера, если стоп-лосс был успешно установлен
            order_ids['stop_loss'] = sl_order_id  # Добавляем ID ордера стоп-лосса
        elif not sl_order_id:
            print("Стоп-лосс не установлен. Закрываем все позиции и ордера.")
            close_all_orders_and_positions(exchange, market_symbol, trade_type)

        order_ids['date_time'] = datetime.now(timezone.utc)
        return order_ids
    except Exception as e:
        print(f"Ошибка при открытии сделки для {market_symbol}: {e}")
        return {}


def get_market_type(exchange, symbol):
    """
    Проверяет наличие криптопары на бирже и возвращает её тип рынка (спот или фьючерс).
    """
    try:
        markets = exchange.load_markets()

        formatted_symbol = format_symbol(symbol, markets)

        if formatted_symbol in markets:
            market_type = markets[formatted_symbol]['type']
            print(f"Символ {formatted_symbol} найден. Тип рынка: {market_type}")
            return market_type
        else:
            print(f"Символ {formatted_symbol} не найден.")
            return None
    except Exception as e:
        print(f"Ошибка при проверке символа {symbol}: {e}")
        return None


def format_symbol(symbol, markets):
    """
    Автоматически форматирует символ в вид BASE/QUOTE.
    """
    possible_quotes = ['USDT', 'BTC', 'ETH']
    for quote in possible_quotes:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            formatted = f"{base}/{quote}"
            if formatted in markets:
                return formatted
    return symbol


def check_order_statuses(exchange, market_symbol, order_ids):
    """
    Проверяет статусы ордеров по их ID.

    Аргументы:
    exchange -- экземпляр объекта ccxt биржи
    market_symbol -- строка в формате 'POWR/USDT:USDT'
    order_ids -- словарь с ID ордеров { 'order': order_id, 'take_profits': [tp_order_ids], 'stop_loss': stop_loss_order_id}

    Возвращает:
    Словарь со статусами ордеров.
    """
    try:
        statuses = {'order': None, 'take_profit_orders': {}, 'stop_loss_order': None}

        if 'order' in order_ids and order_ids['order']:
            order_id = order_ids['order']
            entry_status = exchange.fetch_open_order(order_id, market_symbol)
            if not entry_status:  # Если ордер уже закрыт
                entry_status = exchange.fetch_closed_order(order_id, market_symbol)
            statuses['order'] = entry_status['status']
            # print(f"Ордер на вход {order_id}: статус - {entry_status['status']}")

        if 'take_profits' in order_ids:
            for tp_order_id in order_ids['take_profits']:
                tp_status = exchange.fetch_open_order(tp_order_id, market_symbol)
                if not tp_status:  # Если ордер уже закрыт
                    tp_status = exchange.fetch_closed_order(tp_order_id, market_symbol)
                statuses['take_profit_orders'][tp_order_id] = tp_status['status']
                # print(f"Тейк-профит ордер {tp_order_id}: статус - {tp_status['status']}")

        if 'stop_loss_order' in order_ids and order_ids['stop_loss_order']:
            stop_loss_order_id = order_ids['stop_loss_order']
            sl_status = exchange.fetch_open_order(stop_loss_order_id, market_symbol)
            if not sl_status:
                sl_status = exchange.fetch_closed_order(stop_loss_order_id, market_symbol)
            statuses['stop_loss_order'] = sl_status['status']
            # print(f"Стоп-лосс ордер {stop_loss_order_id}: статус - {sl_status['status']}")

        return statuses

    except Exception as e:
        print(f"Ошибка при проверке статусов ордеров: {e}")
        return None


def check_open_orders(exchange, symbol):
    """
    Проверяет наличие открытых ордеров для указанного символа.

    Аргументы:
    exchange -- экземпляр объекта ccxt биржи
    symbol -- строка в формате 'GOMINING/USDT'

    Возвращает:
    bool -- True, если есть открытые ордера для этого символа, иначе False
    """
    try:
        open_orders = exchange.fetch_open_orders(symbol)
        if open_orders:
            print(f"Есть открытые ордера для {green(symbol)}: {yellow(len(open_orders))} ордеров.")
            return True
        else:
            print(f"Нет открытых ордеров для {symbol}.")
            return False
    except Exception as e:
        print(f"Ошибка при проверке открытых ордеров для {symbol}: {e}")
        return False


def close_all_orders_and_positions(exchange, market_symbol, trade_type):
    """
    Закрывает все открытые позиции и отменяет все активные ордера для указанного символа.

    Аргументы:
    exchange -- экземпляр объекта ccxt биржи
    market_symbol -- строка в формате 'BTC/USDT'
    trade_type -- тип сделки ('long' или 'short')
    """
    try:
        open_orders = exchange.fetch_open_orders(market_symbol)
        for order in open_orders:
            exchange.cancel_order(order['id'], market_symbol)
            print(f"Отменен ордер {order['id']} на {order['price']} {market_symbol}.")

        position = exchange.fetch_position(market_symbol)
        position_amount = position['amount']

        if position_amount > 0:
            side = 'sell' if trade_type == 'long' else 'buy'
            close_order = exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=side,
                amount=position_amount
            )
            print(f"Позиция закрыта, ID ордера: {close_order['id']}")
        else:
            print("Нет открытых позиций для закрытия.")
    except Exception as e:
        print(f"Ошибка при закрытии ордеров и позиций: {e}")


import time


def retry_set_stop_loss(exchange, market_symbol, trade_type, order_amount, stop_loss, max_retries=5, retry_delay=10):
    """
    установить стоп-лосс с повторными попытками в случае неудачи.

    Аргументы:
    exchange -- экземпляр объекта ccxt биржи
    market_symbol -- строка в формате 'BTC/USDT'
    trade_type -- тип сделки ('long' или 'short')
    order_amount -- количество для стоп-лосса
    stop_loss -- уровень стоп-лосса
    max_retries -- максимальное количество попыток (по умолчанию 5)
    retry_delay -- задержка между попытками в секундах (по умолчанию 10 секунд)

    Возвращает:
    ID установленного стоп-лосса или None, если установка не удалась.
    """
    sl_order_id = None

    for attempt in range(1, max_retries + 1):
        try:
            sl_order_id = set_stop_loss(exchange, market_symbol, trade_type, order_amount, stop_loss)
            if sl_order_id:
                print(f"Стоп-лосс успешно установлен с ID: {sl_order_id} на попытке {attempt}.")
                return sl_order_id
        except Exception as e:
            print(f"Попытка {attempt} установить стоп-лосс не удалась: {e}")

        if attempt < max_retries:
            print(f"Ждем {retry_delay} секунд перед повторной попыткой...")
            time.sleep(retry_delay)

    print("Не удалось установить стоп-лосс после всех попыток.")
    return None


def set_stop_loss(exchange, market_symbol, trade_type, order_amount, stop_loss):
    """
    Устанавливает стоп-лосс для ордера в зависимости от типа рынка (Spot или Derivatives).

    Аргументы:
    exchange -- экземпляр объекта ccxt биржи
    market_symbol -- строка символа в формате 'SYMBOL/USDT'
    trade_type -- тип сделки ('long' или 'short')
    order_amount -- количество для ордера
    stop_loss -- цена срабатывания стоп-лосса

    Возвращает:
    ID ордера, если стоп-лосс успешно установлен, иначе None.
    """
    try:
        market_type = get_market_type(exchange, market_symbol)  # Определяем тип рынка
        print(f"Тип рынка для {market_symbol}: {market_type}")

        if market_type == 'spot':
            # Для Spot используем 'limit' ордер с параметром stopPrice
            sl_order = exchange.create_order(
                symbol=market_symbol,
                type='limit',
                side='sell' if trade_type == 'long' else 'buy',
                amount=order_amount,
                price=stop_loss,
                params={
                    'stopPrice': stop_loss,
                    'reduce_only': True
                }
            )
        elif market_type == 'swap' or market_type == 'future':
            # Для Derivatives используем 'market' ордер с параметром triggerDirection
            sl_order = exchange.create_order(
                symbol=market_symbol,
                type='market',
                side='sell' if trade_type == 'long' else 'buy',
                amount=order_amount,
                params={
                    'stopPrice': stop_loss,
                    'triggerDirection': 'below' if trade_type == 'long' else 'above',
                    'reduce_only': True
                }
            )
        else:
            print(f"Неизвестный тип рынка для {market_symbol}: {market_type}")
            return None

        print(f"Стоп-лосс установлен на {stop_loss}, ID ордера: {sl_order['id']}.")
        return sl_order['id']

    except Exception as sl_error:
        print(f"Ошибка при установке стоп-лосса на {stop_loss}: {sl_error}")
        return None


def set_take_profit(exchange, market_symbol, trade_type, order_amount, take_profits):
    """
        Устанавливает тейк-профиты для ордера.

        Аргументы:
        exchange -- экземпляр объекта ccxt биржи
        market_symbol -- строка с символом рынка, например 'BTC/USDT'
        trade_type -- тип сделки, 'long' или 'short'
        order_amount -- количество ордера
        take_profits -- список уровней тейк-профитов

        Возвращает:
        Список ID ордеров тейк-профитов.
        """
    order_ids = []

    for tp in take_profits:
        try:
            tp_order = exchange.create_order(
                symbol=market_symbol,
                type='limit',
                side='sell' if trade_type == 'long' else 'buy',
                amount=order_amount / len(take_profits),
                price=tp,
                params={
                    'take_profit_price': tp,
                    'reduce_only': True
                }
            )
            order_ids.append(tp_order['id'])
            print(f"Тейк-профит установлен на {tp}, ID ордера: {tp_order['id']}.")
        except Exception as tp_error:
            print(f"Ошибка при установке тейк-профита на {tp}: {tp_error}")

    return order_ids
