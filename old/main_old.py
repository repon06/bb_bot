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