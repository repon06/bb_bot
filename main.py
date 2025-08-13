import asyncio
import time
from datetime import datetime, timedelta, timezone

# print("sys.path:", sys.path)
import schedule

import orders
import telegram
from config import API_KEYS, IS_DEMO, TIMEFRAME, LEVERAGE, TIME_DElTA, tg_channel_insider_id, LAST_MESSAGE_COUNT
from data_fetcher import get_exchange, fetch_recent_data, get_filtered_markets, check_symbol_exists
from helper.design import red, print_graphic, print_candles, green, yellow
from helper.mongo import MongoDBClient
from indicators import calculate_indicators, get_current_price
from orders import print_order_info, get_error, check_and_open_long_order, set_leverage, is_market_order_open, \
    check_order_statuses
from strategy import should_short, should_long


def main():
    # Создаем клиента для базы данных 'crypto' и коллекции 'signals' и 'orders'
    db_client_signals = MongoDBClient(db_name='crypto', collection_name='signals')
    db_client_orders = MongoDBClient(db_name='crypto', collection_name='orders')
    db_orders = MongoDBClient(db_name='crypto', collection_name='orders_general')

    signals_documents = db_client_signals.get_all_documents()
    orders_documents = db_client_orders.get_all_documents()
    # print(f"Удалено документов: {db_client_signals.delete_many({})}")

    usdt_balance = 0.0
    exchange = get_exchange(API_KEYS, is_demo=IS_DEMO)
    markets = get_filtered_markets(exchange)
    markets = {}

    # symbol = SYMBOLS[0] + ":USDT"  # "TROY/USDT:USDT" "APE/USDT:USDT" "ADA/USDT:USDT"
    # if not is_market_order_open(exchange, symbol):
    #    test_open_long_swap(exchange, symbol)

    # stat = check_order_statuses(exchange, 'BUBBLE/USDT', {'order': 1863352043419471104, 'stop_loss_order': 1863352055851388160})
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total']['USDT']
        if usdt_balance > 10:
            print(f"Есть средства для торговли на балансе: {usdt_balance:.2f} USDT!")
    except Exception as e:
        print("Error:", get_error(e))

    # сигнал из файла
    signal_from_file = None  # TODO: пока убрал parse_trade_signals(signals_text)  # from file
    # сигналы из телеги
    # signals_from_tg = asyncio.run(telegram.get_tg_signal(limit=300))
    signals_from_tg = asyncio.run(
        telegram.get_tg_signals_from_insider_trade_by_id(tg_channel_insider_id, limit=LAST_MESSAGE_COUNT))

    if not signals_from_tg and signal_from_file:
        for signal in signal_from_file:
            symbol = signal['symbol']
            buy_price = signal['buy_price']
            take_profits = signal['take_profits']
            stop_loss = signal['stop_loss']
            trade_type = signal['direction']  # LONG/SHORT
            date = signal['date']

    else:
        for signal in signals_from_tg:
            symbol = signal['symbol']
            buy_price = signal['buy_price']  # float(signal['buy_price'])
            take_profits = signal['take_profits']  # [float(tp) for tp in signal['take_profits']]
            stop_loss = signal['stop_loss']  # float(signal['stop_loss'])
            trade_type = signal['direction']  # LONG/SHORT
            date = signal['date']

            # find_signal = db_client_signals.find_one({'symbol': symbol_parce, 'buy_price': buy_price})
            # if not db_client_signals.find_one({'symbol': symbol_parce, 'buy_price': buy_price}):
            #    db_signal_id = db_client_signals.insert_one(signal)  # add mongo
            #    print(f"Inserted signal with symbol: {symbol_parce} and ID: {db_signal_id}")
            ################################################################
            symbol = check_symbol_exists(exchange, symbol)  # TODO: надо ли указывать символ пары в таком виде?
            if symbol:
                signal['symbol'] = symbol
                signal['status']: 'found'
                print(f"Криптопара {green(symbol)} найдена на Bybit в формате: {yellow(symbol)}")

                if not db_client_signals.find_one({'symbol': symbol, 'buy_price': buy_price}):
                    db_client_signals.insert_one(signal)  # add mongo

                # Проверка на открытые ордера
                if orders.check_open_orders(exchange, symbol):
                    print(f"Для символа {red(symbol)} уже есть открытые сделки. Пропускаем открытие новой.")
                    print(
                        f"Found order: {db_client_signals.find_one({'symbol': symbol, 'buy_price': buy_price})}")  # Поиск сигнала в БД
                    orders.auto_move_sl_to_break_even(exchange, symbol, buy_price, trade_type)
                elif date >= datetime.now(timezone.utc) - timedelta(minutes=TIME_DElTA):
                    # Открываем сделку с ТП и СЛ
                    # order_ids = orders.open_spot_order_with_tps_sl(exchange, symbol, buy_price, take_profits, stop_loss)
                    # order_ids = orders.open_perpetual_order(exchange, symbol, buy_price, take_profits, stop_loss,trade_type, current_price)
                    order_ids = orders.open_perpetual_order_by_signal(exchange, signal)

                    if order_ids:
                        db_order_id = db_client_orders.insert_one(order_ids)  # save order in db
                        order_general = {
                            'order_id': order_ids['order'],
                            'date_time': order_ids['date_time'],
                            'symbol': order_ids['symbol'],
                            'type': 'general',
                            'status': 'open',
                            'parent': None,
                            'price': buy_price
                        }
                        order_tps_sl = []
                        for i, tp in enumerate(take_profits):
                            order_tps_sl.append({
                                'order_id': order_ids['take_profits'][i],
                                'date_time': order_ids['date_time'],
                                'symbol': order_ids['symbol'],
                                'type': 'tp',
                                'status': 'open',
                                'parent': order_ids['order'],
                                'price': tp
                            })
                            order_tps_sl.append({
                                'order_id': order_ids['stop_loss'],
                                'date_time': order_ids['date_time'],
                                'symbol': order_ids['symbol'],
                                'type': 'sl',
                                'status': 'open',
                                'parent': order_ids['order'],
                                'price': stop_loss
                            })
                        db_orders.insert_many([order_general] + order_tps_sl)
                        print(
                            f"Found order: {db_client_signals.find_one({'symbol': symbol, 'buy_price': buy_price})}")  # Поиск сигнала

                        statuses = check_order_statuses(exchange, symbol, order_ids)
                        print("Статусы ордеров:", statuses)
                    else:
                        print("Не удалось открыть сделку.")
                else:
                    print(
                        f"Сигнал старее {TIME_DElTA} мин: {round((datetime.now(timezone.utc) - date).total_seconds() / 60)} мин")
            else:
                signal['status']: 'not found'
                symbol = signal['symbol']
                if not db_client_signals.find_one({'symbol': symbol, 'buy_price': buy_price}):
                    db_client_signals.insert_one(signal)  # add mongo
            ################################################################

    ################################################################
    # symbol = 'GOMININGUSDT'  # 'POWRUSDT'
    # symbol = check_symbol_exists(exchange, symbol)
    # if symbol:
    #     print(f"Криптопара {green(symbol)} найдена на Bybit в формате: {yellow(symbol)}")
    #
    #     buy_price = 0.2883000
    #     take_profits = [0.2914713, 0.2943543, 0.2972373, 0.3001203, 0.3030033]
    #     stop_loss = 0.2735967
    #
    #     # Проверка на открытые ордера
    #     if check_open_orders(exchange, symbol):
    #         print(f"Для символа {red(symbol)} уже есть открытые сделки. Пропускаем открытие новой.")
    #     else:
    #         # Открываем сделку с ТП и СЛ
    #         order_ids = open_order_with_tps_sl(exchange, symbol, buy_price, take_profits, stop_loss)
    #
    #         if order_ids:
    #             print(f"Сделка открыта успешно, ID ордера: {order_ids}")
    #
    #             statuses = check_order_statuses(exchange, symbol, order_ids)
    #             print("Статусы ордеров:", statuses)
    #         else:
    #             print("Не удалось открыть сделку.")
    ################################################################
    for symbol, market in markets.items():  # for market in markets:
        # print("limits: " + print_dict(market['limits']))
        print(f"{red(symbol)} / {market['type']} / "
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

                print(f"Тип рынка: {market['type']}")
                if market['type'] == 'linear':
                    exchange.set_leverage(LEVERAGE, symbol)
                    set_leverage(exchange, symbol, leverage=LEVERAGE)

                if not is_market_order_open(exchange, symbol):
                    # Открытие long позиции с расчетными параметрами
                    order = check_and_open_long_order(exchange, symbol, usdt_balance, take_profit, stop_loss)
                    if order is not None:
                        print_order_info(exchange, order['id'], symbol)

    # Закрываем соединение
    db_client_signals.close()
    db_client_orders.close()


if __name__ == "__main__":
    main()
    schedule.every(15).seconds.do(main)

    while True:
        schedule.run_pending()
        time.sleep(1)
