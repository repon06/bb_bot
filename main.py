import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta, timezone

import schedule
from ccxt import BadSymbol

import orders
import telegram
from config import API_KEYS, IS_DEMO, TIME_DElTA, tg_channel_insider_id, LAST_MESSAGE_COUNT
from data_fetcher import get_exchange, check_symbol_exists
from helper.mongo import MongoDBClient
from orders import get_error, check_order_statuses

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

    # signals_documents = db_client_signals.get_all_documents()
    # orders_documents = db_client_orders.get_all_documents()
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
    signal_from_file = None  # TODO: пока убрал # parse_trade_signals(signals_text)  # from file
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
            link = signal['link']

            try:
                current_price = exchange.fetch_ticker(symbol, params={"type": "future"})['last']
            except BadSymbol as e:
                logging.error(f"Ошибка получения инфы по криптопаре: {e}")
                continue

            signal['current_price'] = current_price
            logging.info(f"Текущая цена {symbol}: {current_price}, цена входа: {buy_price}")

            symbol = check_symbol_exists(exchange, symbol)
            if symbol:
                signal['symbol'] = symbol
                # signal['status']: 'found'
                logging.info(f"Криптопара {symbol} найдена на Bybit в формате: {symbol}")

                # анализ сделок TODO: пока отключил
                # logging.info(f"Анализ закрытых ордеров {yellow(symbol)}:")
                # for r in orders.analyze_closed_orders(exchange, signal):
                # for r in orders.analyze_closed_orders_with_pnl(exchange, signal):
                #    logging.info(f"    {r}")

                # смотрим причину закрытия ордера
                # order = exchange.fetch_order('4493ed53-7556-487b-94dc-21b9c34e65c6', 'THETA/USDT:USDT', params={"acknowledged": True})

                # asyncio.run(telegram.send_to_me(f"ссылка на сигнал: {signal['link']}"))

                # Проверяем, был ли такой сигнал
                existing_signal = db_client_signals.find_signal(symbol, buy_price, trade_type)
                if existing_signal:
                    if orders.check_open_orders(exchange, symbol):
                        # logging.info(orders.get_pnl(exchange, symbol))
                        # Позиция ещё открыта — двигаем SL и не открываем заново
                        logging.info(f"Сигнал по {symbol} уже есть в БД и позиция открыта")
                        orders.auto_move_sl_to_break_even(exchange, symbol, buy_price, trade_type, existing_signal,
                                                          link)
                        continue
                    elif (orders.check_closed_orders(exchange, symbol)
                          or db_client_signals.find_signal(symbol, buy_price, trade_type)):
                        logging.info(f"Позиция по {symbol} уже обработана. Пропуск")
                        continue
                    else:
                        # Сигнал есть, но позиции нет — можно открывать заново
                        logging.info(f"Сигнал по {symbol} уже был, но ордеров нет — открываем заново")
                # else:# Если сигнала ещё нет в БД — добавляем

                # Если дошли сюда — можно открывать сделку если свежий сигнал
                if date >= datetime.now(timezone.utc) - timedelta(minutes=TIME_DElTA):
                    order_ids = orders.open_perpetual_order_by_signal(exchange, signal)

                    if order_ids:
                        asyncio.run(telegram.send_to_me(
                            f"Создан новый ордер по {signal['direction']} сигналу: {signal['symbol']} на цену покупки {signal['buy_price']}"))
                        logging.info(
                            f"Создан новый ордер по {signal['direction']} сигналу: {signal['symbol']} на цену покупки {signal['buy_price']}")

                        # Если сигнала ещё нет в БД — добавляем
                        db_client_signals.insert_signal(signal)
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
                                'type': f"tp{i + 1}",
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

                        # новый ордер в бд order_general
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

    # Закрываем соединение
    db_client_signals.close()
    db_client_orders.close()


def safe_main():
    try:
        main()
    except Exception as e:
        logging.info(f"[ОШИБКА] main(): {e}")
        asyncio.run(telegram.send_to_me(f"[ОШИБКА] main(): {e}"))
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
