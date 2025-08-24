for symbol, market in markets.items():  # for market in markets:
    # logging.info("limits: " + print_dict(market['limits']))
    logging.info(f"{symbol} / {market['type']} / "
                 f"limits min: {market['limits']['amount']['min']:.0f} "
                 f"limits max: {market['limits']['amount']['max']:.0f}")
    if market['type'] == 'option':
        continue
    # candles = fetch_recent_data(exchange, symbol=symbol, timeframe=TIMEFRAME, start_date="2024-12-09 15:30:00", limit=50)
    candles = fetch_recent_data(exchange, symbol, TIMEFRAME, limit=50)
    # Рассчитать все индикаторы
    df = calculate_indicators(candles)
    if should_long(df) or should_short(df):
        if should_long(df):
            # Получаем текущую цену
            current_price = get_current_price(df)
            # Вычисление уровней тейк-профита и стоп-лосса
            take_profit = [current_price * 1.01, current_price * 1.03, current_price * 1.07]
            stop_loss = current_price * 0.97  # 0.965

            print_candles(candles)
            print_graphic(candles, symbol, stop_loss, take_profit)

            logging.info(f"Тип рынка: {market['type']}")
            if market['type'] == 'linear':
                exchange.set_leverage(LEVERAGE, symbol)
                set_leverage(exchange, symbol, leverage=LEVERAGE)

            if not is_market_order_open(exchange, symbol):
                # Открытие long позиции с расчетными параметрами
                order = check_and_open_long_order(exchange, symbol, usdt_balance, take_profit, stop_loss)
                if order is not None:
                    print_order_info(exchange, order['id'], symbol)



@deprecated(reason="метод устарел")
def open_short_position(exchange, symbol, amount, take_profits, stop_loss, leverage):
    """
    Открывает короткую позицию на рынке с заданным плечом, тейк-профитом и стоп-лоссом.
    """
    try:
        exchange.set_leverage(leverage, symbol)
        logging.info(f"Плечо {leverage}x установлено для {symbol}")

        order = exchange.create_market_sell_order(symbol, amount)
        logging.info(f"Рыночный ордер на продажу открыт: {order}")

        for i, tp in enumerate(take_profits, start=1):
            try:
                tp_order = exchange.create_limit_buy_order(symbol, amount, tp)
                logging.info(f"Тейк-профит {i} установлен на уровне {tp}: {tp_order}")
            except Exception as e:
                logging.error(f"Ошибка установки тейк-профита {i}: {e}")

        try:
            stop_loss_order = exchange.create_order(
                symbol,
                type="stop_loss_limit",
                side="buy",
                amount=amount,
                price=stop_loss,
                params={"stopPrice": stop_loss}  # Указываем триггер-цену
            )
            logging.info(f"Стоп-лосс установлен на уровне {stop_loss}: {stop_loss_order}")
        except Exception as e:
            logging.error(f"Ошибка установки стоп-лосса: {e}")

    except Exception as e:
        logging.error(f"Ошибка при открытии короткой позиции: {e}")


@deprecated()
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

    logging.info(f"Market type: {market_type}, Precision: {precision_amount}, Lot size: {lot_size}")

    if market_type not in ['swap', 'future']:
        logging.info("Недопустимый тип рынка")
        return

    position = exchange.fetch_position(symbol)
    current_leverage = position.get('leverage', None)

    try:
        if current_leverage != leverage:
            exchange.set_leverage(leverage, symbol)
            logging.info(f"Плечо для {symbol} установлено на {leverage}")
    except Exception as e:
        logging.error(f"Ошибка при установке плеча: {e}")

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
        logging.info(f"Стоимость ордера {cost:.2f} ниже минимальной стоимости сделки {min_order_amt:.2f} USDT")
        return

    logging.info(
        f"Открытие LONG позиции на {symbol} с кол-вом контрактов: {amount_in_contracts}, стоимостью: {cost:.2f} USDT")

    try:
        params = {"category": "linear"}
        order = create_market_long_order(exchange, symbol, amount_in_contracts, params=params)
        logging.info(f"Рыночный ордер на покупку открыт: {order}")
    except Exception as e:
        logging.error(f"Ошибка при открытии ордера: {e}")
        return

    set_take_profits(exchange, symbol, amount_in_contracts / len(take_profits), take_profits)

    set_stop_loss_2(exchange, symbol, stop_loss, amount_in_contracts)


@deprecated(reason="Этот метод устарел")
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
    logging.info("Market: " + market_type)
    logging.info(f"Максимально допустимое количество контрактов для {symbol}: {market['limits']['amount']['max']}")
    logging.info(f"Точность контрактов для {symbol}: {precision_amount}")
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
        logging.error(f"ОШИБКА: {get_error(e)}")

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
        logging.info(f"Стоимость ордера {cost:.2f} ниже минимальной {min_order_amt:.2f}")
        return

    required_amount_in_usdt = amount * current_price
    if required_amount_in_usdt < min_order_amt:
        raise ValueError(f"Минимальная сумма сделки: {min_order_amt} USDT. Недостаточно средств")

    logging.info(
        f"Открытие LONG позиции на {symbol} с кол-вом: {amount:.2f}, стоимостью: {required_amount_in_usdt:.2f} USDT, max allowed: {max_order_qty}")

    # debug_enable(exchange, True)
    order = create_market_long_order(exchange, symbol, amount, params=params)
    # bybit {"retCode":10001,"retMsg":"The number of contracts exceeds maximum limit allowed: too large, order_qty:8305400000000 \u003e max_qty:2400000000000"
    # debug_enable(exchange, False)
    logging.info(f"Рыночный ордер на покупку открыт: {order}")
    logging.info_order_info(exchange, order['id'], symbol)
    filled_amount = order['filled']

    set_take_profits(exchange, symbol, amount / len(take_profits), take_profits)

    set_stop_loss_2(exchange, symbol, stop_loss, amount)


@deprecated(reason="Этот метод устарел")
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
        logging.info(f"Стоп-лосс установлен на {stop_loss}: {sl_order}")
    except Exception as e:
        logging.error(f"Ошибка установки стоп-лосса: {get_error(e)}")


@deprecated(reason="Этот метод устарел, используем auto_move_sl_to_break_even()")
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
        logging.info(f"Стоп-лосс перемещен в точку безубытка: {sl_order}")
    except Exception as e:
        logging.error(f"Ошибка при переносе стоп-лосса в безубыток: {get_error(e)}")


@deprecated(reason="Этот метод устарел, используем auto_move_sl_to_break_even()")
def check_and_move_to_breakeven(exchange, symbol, entry_price, tp1_price, remaining_amount):
    """
    Проверяет достижение TP1 и перемещает стоп-лосс в безубыток.
    """
    try:
        ticker = exchange.fetch_ticker(symbol)
        last_price = ticker['last']

        if last_price >= tp1_price:
            logging.info(f"Цена достигла TP1 ({tp1_price}). Перемещаем стоп-лосс в безубыток")
            move_stop_to_breakeven(exchange, symbol, entry_price, remaining_amount)
        else:
            logging.info(f"Цена еще не достигла TP1 ({tp1_price}). Текущая цена: {last_price}")
    except Exception as e:
        logging.error(f"Ошибка при проверке TP1: {get_error(e)}")


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
        logging.info(
            f"Недостаточно средств для покупки {min_order_qty} {symbol}. Нужно {required_amount_in_usdt:.2f} USDT")
    else:
        logging.info(
            f"Для покупки мин кол-ва монет ({min_order_qty}) на рынке {symbol}, нужно потратить: {required_amount_in_usdt:.2f} USDT")
        logging.info(f"Доступно для покупки {usdt_balance:.2f} USDT. Ордер можно разместить")

    logging.info(f"У меня должно быть usdt: {required_amount_in_usdt:.2f} "
                 f"я имею usdt: {usdt_balance} "
                 f"цена за 1: {current_price:.10f} "
                 f"минимум: {min_order_qty:.2f} ")

    if required_amount_in_usdt < min_order_amt:
        logging.info(f"Минимальная сумма для ордера: {min_order_amt} USDT. Увеличьте сумму")
        min_amount_in_symbol = min_order_amt / current_price
        min_amount_in_symbol = math.ceil(
            min_amount_in_symbol / min_order_qty) * min_order_qty
    else:
        min_amount_in_symbol = min_order_qty

    logging.info(f"Минимальное количество монет для ордера: {min_amount_in_symbol:.2f}")

    order = open_long_position(exchange, symbol, min_amount_in_symbol, current_price, take_profits, stop_loss)
    return order



def open_long_position(exchange, symbol, amount, current_price, take_profits: array = None, stop_loss: float = None):
    """
    Открывает LONG позицию с тейк-профитами и стоп-лоссом.
    """
    logging.info(f"Открытие LONG позиции {red(symbol)} на {amount:.0f} за {current_price:.10f} "
                 f"с тейк-профитом {take_profits} и стоп-лоссом {stop_loss:.10f}")
    if take_profits is None and stop_loss is None:
        take_profits = [current_price * 1.015, current_price * 1.03, current_price * 1.06]
        stop_loss = current_price * 0.98

    order = create_market_long_order(exchange, symbol, amount)

    if order is not None:
        set_take_profits(exchange, symbol, amount, take_profits)

        set_stop_loss_market(exchange, symbol, stop_loss, amount)

        logging.info(f"{green("Открыта") if order is not None else red("Не открыта")} LONG позиция "
                     f"на {symbol} с тейк-профитом и стоп-лоссом")
    return order


def open_long_position_old(exchange, symbol, amount, current_price):
    take_profits = [current_price * 1.015, current_price * 1.03, current_price * 1.06]
    stop_loss = current_price * 0.98

    logging.info(f"открытие long позиции {red(symbol)} на {amount:.0f} за {current_price:.10f}")
    order = create_market_long_order(exchange, symbol, amount)

    set_take_profits(exchange, symbol, amount / len(take_profits), take_profits)

    exchange.create_order(symbol, type='stop_loss_limit', side='sell', amount=amount, price=stop_loss,
                          params={'stopPrice': stop_loss})

    logging.info(f"Открыта Long позиция на {symbol} с тейк-профитом и стоп-лоссом")
    return order


def set_take_profits(exchange, symbol, amount, take_profits: List[float]):
    for i, tp in enumerate(take_profits, start=1):
        try:
            order_tp = exchange.create_limit_sell_order(symbol, amount, tp)
            filled_amount = order_tp['filled']
            logging.info(f"Тейк-профит {i}: {tp:.10f}")
        except Exception as e:
            logging.error(f"Ошибка установки тейк-профита {i} bybit: {get_error(e)}")


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
        logging.info("Стоп-лосс рыночный установлен:", order)
    except Exception as e:
        logging.error("Ошибка установки стоп-лосса:", get_error(e))



def open_position(exchange, symbol, side, amount):
    return exchange.create_order(symbol, type="market", side=side, amount=amount)


def create_market_long_order(exchange, symbol, amount, params=None):
    try:
        # Рыночный ордер на покупку
        order = exchange.create_market_buy_order(symbol, amount, params=params)
        logging.info(f"Рыночный ордер на покупку открыт: {order}")
        return order
    except Exception as e:
        logging.error(f"Ошибка при открытии позиции bybit: {get_error(e)}")
        return None


@deprecated(reason="Этот метод устарел")
def open_spot_order_with_tps_sl(exchange, market_symbol, buy_price, take_profits, stop_loss):
    """
    Открывает СПОТовую сделку на Bybit (лонг или шорт), автоматически определяет тип сделки,
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
        logging.info(f"Тип рынка для {market_symbol}: {market_type}")

        ticker = exchange.fetch_ticker(market_symbol)
        current_price = ticker['last']
        logging.info(
            f"Текущая рыночная цена для {market_symbol}: {green(current_price)}\n"
            f"Мы указывали цену открытия ордера: {red(buy_price)}")

        initial_trade_type = determine_trade_type(buy_price, take_profits, stop_loss)
        if not initial_trade_type:
            logging.info(
                "Не удалось определить начальный тип сделки. Проверьте значения buy_price, take_profits и stop_loss")
            return []

        trade_type = determine_trade_type(buy_price, take_profits, stop_loss, current_price)
        if not trade_type:
            logging.info("Текущая цена изменяет логику сделки, сделка не будет открыта")
            return []

        if initial_trade_type != trade_type:
            logging.info(f"Тип сделки изменился: с {initial_trade_type} на {trade_type}. Ордер не будет открыт")
            return []

        market_info = exchange.market(market_symbol)
        min_order_size = market_info['limits']['amount']['min']

        order_amount = TRADE_AMOUNT / current_price
        if order_amount < min_order_size:
            logging.info(f"Количество ордера {order_amount} меньше минимально допустимого {min_order_size}")
            return []

        logging.info(
            f"Открываем {green(initial_trade_type)} ордер на {order_amount:.6f} {market_symbol} по цене {current_price}")
        order = exchange.create_order(
            symbol=market_symbol,
            type='market',
            side='buy' if trade_type == 'long' else 'sell',
            amount=order_amount
        )

        logging.info(f"Ордер {initial_trade_type} на вход открыт: {order['id']}")
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
            logging.info("Стоп-лосс не установлен. Закрываем все позиции и ордера")
            close_all_orders_and_positions(exchange, market_symbol, trade_type)

        order_ids['date_time'] = datetime.now(timezone.utc)
        return order_ids
    except Exception as e:
        logging.error(f"Ошибка при открытии сделки для {market_symbol}: {e}")
        return {}


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
                logging.info(f"Стоп-лосс успешно установлен с ID: {sl_order_id} на попытке {attempt}")
                return sl_order_id
        except Exception as e:
            logging.error(f"Попытка {attempt} установить стоп-лосс не удалась: {e}")

        if attempt < max_retries:
            logging.info(f"Ждем {retry_delay} секунд перед повторной попыткой..")
            time.sleep(retry_delay)

    logging.error("Не удалось установить стоп-лосс после всех попыток")
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
        logging.info(f"Тип рынка для {market_symbol}: {market_type}")

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
            logging.info(f"Неизвестный тип рынка для {market_symbol}: {market_type}")
            return None

        logging.info(f"Стоп-лосс установлен на {stop_loss}, ID ордера: {sl_order['id']}")
        return sl_order['id']

    except Exception as sl_error:
        logging.error(f"Ошибка при установке стоп-лосса на {stop_loss}: {sl_error}")
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
            logging.info(f"Тейк-профит установлен на {tp}, ID ордера: {tp_order['id']}")
        except Exception as tp_error:
            logging.error(f"Ошибка при установке тейк-профита на {tp}: {tp_error}")

    return order_ids


@deprecated()
def move_sl_to_break_even(exchange, market_symbol, entry_price, trade_type):
    # Получаем все открытые ордера по символу
    open_orders = exchange.fetch_open_orders(symbol=market_symbol)
    closed_orders = exchange.fetch_closed_orders(symbol=market_symbol)

    # Ищем первый сработавший тейк-профит
    first_tp = None
    for order in closed_orders:
        if order['side'] == ('sell' if trade_type == 'long' else 'buy') and order['status'] == 'closed':
            first_tp = order
            break

    if not first_tp:
        logging.info("Ни один тейк-профит ещё не сработал")
        return None

    # Ставим стоп-лосс в безубыток
    stop_price = entry_price
    sl_order_id = set_stop_loss_perpetual(
        exchange, market_symbol, trade_type, order_amount=first_tp['amount'], stop_loss=stop_price
    )
    if sl_order_id:
        logging.info(f"Стоп перенесён в безубыток на {stop_price}, ID: {sl_order_id}")
    return sl_order_id


def auto_move_sl_to_break_even(exchange, symbol, buy_price, trade_type):
    """
    Авто-перенос SL в безубыток после первого срабатывшего ТП
    Работает для частично закрытых позиций: СЛ обновляется на цену входа
    """
    try:
        # Определяем стороны ордеров для TP и SL
        tp_side = 'sell' if trade_type == 'long' else 'buy'
        sl_side = 'sell' if trade_type == 'long' else 'buy'

        # 1. Получаем закрытые ордера (для определения сработавших TP)
        closed_orders = exchange.fetch_closed_orders(symbol=symbol)
        first_tp = None
        for order in sorted(closed_orders, key=lambda o: o['timestamp']):
            # Ищем первый сработавший TP (reduceOnly=True)
            if order['side'] == tp_side and order.get('reduceOnly', False) and order['status'] == 'closed':
                first_tp = order
                break

        if not first_tp:
            logging.info(f"Перенос SL в безубыток не нужен — TP ещё не сработал для {symbol}")
            return

        # 2. Получаем все открытые ордера
        open_orders = exchange.fetch_open_orders(symbol=symbol)

        # Ищем текущий SL среди открытых ордеров
        existing_sl = None
        for order in open_orders:
            if order['side'] == sl_side and order.get('reduceOnly', False):
                existing_sl = order
                break

        # 3. Если SL уже на цене безубытка — выходим
        if existing_sl and float(existing_sl.get('stopPrice', 0)) == float(buy_price):
            logging.info(f"SL уже в безубытке ({buy_price}) для {symbol}, перенос не требуется")
            return

        # 4. Удаляем старый SL, если он есть
        if existing_sl:
            exchange.cancel_order(existing_sl['id'], symbol=symbol)
            logging.info(f"Удалён старый SL ({existing_sl.get('stopPrice')}) для {symbol}")

        # 5. Определяем количество для нового SL
        amount = None
        if existing_sl:
            amount = float(existing_sl['amount'])
        else:
            # Берём текущую позицию, если SL не найден
            position = exchange.fetch_positions([symbol])[0]
            amount = abs(float(position['contracts']))
            if amount == 0:
                logging.info(f"Позиция по {symbol} пустая, SL не создаём")
                return

        # 6. Получаем текущую цену
        current_price = float(exchange.fetch_ticker(symbol)['last'])

        # 7. Выбираем корректный sl_trigger_price для Bybit
        if trade_type == 'long':
            sl_trigger_price = min(float(buy_price), current_price * 0.999)
        else:
            sl_trigger_price = max(float(buy_price), current_price * 1.001)

        # 8. Создаём новый SL на выбранной цене
        new_sl = exchange.create_order(
            symbol=symbol,
            type='market',  # рыночный SL через stopLossPrice
            side=sl_side,
            amount=amount,
            params={
                'stopLossPrice': sl_trigger_price,
                'reduceOnly': True
            }
        )
        logging.info(
            f"Стоп перенесён в безубыток: выбрана цена SL = {sl_trigger_price} (buy_price={buy_price}, current_price={current_price}), ID: {new_sl['id']}")

    except Exception as e:
        logging.error(f"Ошибка переноса SL в безубыток для {symbol}: {e}")



def __auto_move_sl_to_break_even(exchange, symbol, buy_price, trade_type, existing_signal, mode="breakeven"):
    """
    Авто-перенос SL:
    - mode="breakeven": переносим стоп в цену входа после TP1.
    - mode="trailing": двигаем стоп по мере достижения каждого TP (на предыдущий TP).
    """

    try:
        take_profits = existing_signal["take_profits"]
        sl_price = existing_signal["stop_loss"]

        # Получаем ордера
        open_orders = exchange.fetch_open_orders(symbol=symbol)
        closed_orders = exchange.fetch_closed_orders(symbol=symbol)

        # Определяем, какой TP уже сработал
        tp_hit_index = None
        for i, tp_price in enumerate(take_profits):
            tp_filled = any(
                (o.get("stopPrice") in (tp_price, buy_price) or
                 o.get("triggerPrice") in (tp_price, buy_price) or
                 o.get("takeProfitPrice") in (tp_price, buy_price)) and o.get("status") == "closed"
                for o in closed_orders
            )
            if tp_filled:
                tp_hit_index = i
            else:
                break

        if tp_hit_index is None:
            logging.info(f"По {symbol} ещё не сработал ни один TP — стоп не двигаем")
            return

        # Определяем новую цену SL
        if mode == "breakeven":
            new_sl_price = buy_price  # всегда безубыток
        elif mode == "trailing":
            if tp_hit_index == 0:
                new_sl_price = buy_price
            else:
                new_sl_price = take_profits[tp_hit_index - 1]  # предыдущий TP
        else:
            logging.info(f"Неизвестный режим {mode}")
            return

        # Проверяем, есть ли уже такой SL
        existing_sl = next((o for o in open_orders
                            if float(o.get("stopPrice", 0)) == float(new_sl_price)), None)

        if existing_sl:
            logging.info(f"SL уже установлен на {new_sl_price} для {symbol}")
            return

        # Считаем объём
        amount = sum(float(o["amount"]) for o in open_orders if o.get("reduceOnly", False))
        if amount == 0:
            logging.info(f"Нет объёма для установки SL по {symbol}")
            return

        # Ставим новый SL
        sl_side = "sell" if trade_type == "long" else "buy"
        new_sl = exchange.create_order(
            symbol=symbol,
            type="market",
            side=sl_side,
            amount=amount,
            params={"stopLossPrice": new_sl_price, "reduceOnly": True}
        )

        # Удаляем старый SL
        old_sl = next((o for o in open_orders if o.get("stopPrice")), None)
        if old_sl:
            exchange.cancel_order(old_sl["id"], symbol=symbol)
            logging.info(f"Удалён старый SL {old_sl.get('stopPrice')} для {symbol}")

        logging.info(f"SL перенесён на {new_sl_price} для {symbol}, ID={new_sl['id']}")

    except Exception as e:
        logging.error(f"Ошибка переноса SL для {symbol}: {e}")
