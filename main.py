import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta, timezone

import schedule

import orders
import telegram
from config import API_KEYS, IS_DEMO, TIMEFRAME, LEVERAGE, TIME_DElTA, tg_channel_insider_id, LAST_MESSAGE_COUNT
from data_fetcher import get_exchange, fetch_recent_data, check_symbol_exists
from helper.design import red, print_graphic, print_candles, green, yellow
from helper.mongo import MongoDBClient
from indicators import calculate_indicators, get_current_price
from orders import print_order_info, get_error, check_and_open_long_order, set_leverage, is_market_order_open, \
    check_order_statuses
from strategy import should_short, should_long

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ])


def main():
    # Создаем клиента для базы данных 'crypto' и коллекции 'signals' и 'orders'
    db_client_signals = MongoDBClient(db_name='crypto', collection_name='signals')
    db_client_orders = MongoDBClient(db_name='crypto', collection_name='orders')
    db_orders = MongoDBClient(db_name='crypto', collection_name='orders_general')

    signals_documents = db_client_signals.get_all_documents()
    orders_documents = db_client_orders.get_all_documents()
    # logging.info(f"Удалено документов: {db_client_signals.delete_many({})}")

    usdt_balance = 0.0
    exchange = get_exchange(API_KEYS, is_demo=IS_DEMO)
    # список валют markets = get_filtered_markets(exchange)
    markets = {}
    signals_to_process = []

    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total']['USDT']
        if usdt_balance > 10:
            logging.info(f"Есть средства для торговли на балансе: {usdt_balance:.2f} USDT!")
    except Exception as e:
        logging.info("Error:", get_error(e))

    # сигнал из файла
    signal_from_file = None  # TODO: пока убрал parse_trade_signals(signals_text)  # from file
    # сигналы из телеги
    # signals_from_tg = asyncio.run(telegram.get_tg_signal(limit=300))
    signals_from_tg = asyncio.run(
        telegram.get_tg_signals_from_insider_trade_by_id(tg_channel_insider_id, limit=LAST_MESSAGE_COUNT))

    if signal_from_file:
        signals_to_process.extend(signal_from_file)
    if signals_from_tg:
        signals_to_process.extend(signals_from_tg)

        for signal in signals_to_process:
            symbol = signal['symbol']
            buy_price = signal['buy_price']
            take_profits = signal['take_profits']
            stop_loss = signal['stop_loss']
            trade_type = signal['direction']  # LONG/SHORT
            date = signal['date']

            current_price = exchange.fetch_ticker(symbol, params={"type": "future"})['last']
            signal['current_price'] = current_price
            logging.info(f"Текущая цена {green(symbol)}: {current_price}, цена входа: {buy_price}")

            symbol = check_symbol_exists(exchange, symbol)
            if symbol:
                signal['symbol'] = symbol
                signal['status']: 'found'
                logging.info(f"Криптопара {green(symbol)} найдена на Bybit в формате: {yellow(symbol)}")

                # анализ сделок TODO: пока отключил
                # logging.info(f"Анализ закрытых ордеров {yellow(symbol)}:")
                # for r in orders.analyze_closed_orders(exchange, signal):
                # for r in orders.analyze_closed_orders_with_pnl(exchange, signal):
                #    logging.info(f"    {r}")

                # Проверяем, был ли такой сигнал
                existing_signal = db_client_signals.find_signal(symbol, buy_price, trade_type)
                if existing_signal:
                    if orders.check_open_orders(exchange, symbol):
                        # logging.info(orders.get_pnl(exchange, symbol))
                        # Позиция ещё открыта — двигаем SL и не открываем заново
                        logging.info(f"Сигнал по {green(symbol)} уже есть в БД и позиция открыта")
                        orders.auto_move_sl_to_break_even(exchange, symbol, buy_price, trade_type, existing_signal)
                        continue
                    elif (orders.check_closed_orders(exchange, symbol)
                          or db_client_signals.find_signal(symbol, buy_price, trade_type)):
                        logging.info(f"Позиция по {green(symbol)} уже обработана. Пропуск")
                        continue
                    else:
                        # Сигнал есть, но позиции нет — можно открывать заново
                        logging.info(f"Сигнал по {green(symbol)} уже был, но ордеров нет — открываем заново")
                # else:# Если сигнала ещё нет в БД — добавляем

                # Если дошли сюда — можно открывать сделку если свежий сигнал
                if date >= datetime.now(timezone.utc) - timedelta(minutes=TIME_DElTA):
                    order_ids = orders.open_perpetual_order_by_signal(exchange, signal)

                    asyncio.run(telegram.send_to_me(
                        f"Создан новый ордер по {signal['direction']} сигналу: {signal['symbol']} на цену покупки {signal['buy_price']}"))
                    logging.info(
                        f"Создан новый ордер по {signal['direction']} сигналу: {signal['symbol']} на цену покупки {signal['buy_price']}")
                    # Если сигнала ещё нет в БД — добавляем
                    db_client_signals.insert_signal(signal)

                    if order_ids:
                        db_order_id = db_client_orders.insert_order(order_ids)  # save order in db

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
                                'type': 'tp' + i + 1,
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
                        logging.info(
                            f"Found order: {db_client_signals.find_signal(symbol, buy_price, trade_type)}")  # Поиск сигнала

                        statuses = check_order_statuses(exchange, symbol, order_ids)
                        logging.info("Статусы ордеров:", statuses)
                    else:
                        logging.info("Не удалось открыть сделку")
                else:
                    logging.info(
                        f"Сигнал старее {TIME_DElTA} мин: {round((datetime.now(timezone.utc) - date).total_seconds() / 60)} мин")
            else:
                signal['status']: 'not found'
                symbol = signal['symbol']
                if not db_client_signals.find_signal(symbol, buy_price, trade_type):
                    db_client_signals.insert_signal(signal)  # add mongo
            ################################################################

    for symbol, market in markets.items():  # for market in markets:
        # logging.info("limits: " + print_dict(market['limits']))
        logging.info(f"{red(symbol)} / {market['type']} / "
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

    # Закрываем соединение
    db_client_signals.close()
    db_client_orders.close()


def safe_main():
    try:
        main()
    except Exception as e:
        logging.info(f"[ОШИБКА] main(): {e}")
        telegram.send_to_me(f"[ОШИБКА] main(): {e}")
        traceback.print_exc()


if __name__ == "__main__":
    safe_main()  # первый запуск сразу
    schedule.every(10).seconds.do(safe_main)  # периодический запуск

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logging.info(f"[ОШИБКА] schedule.run_pending(): {e}")
            traceback.print_exc()
        time.sleep(1)
