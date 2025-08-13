import talib


def calculate_support_resistance(df):
    high = df['high'].rolling(window=10).max()  # 10 последних свечей
    low = df['low'].rolling(window=10).min()
    return high.iloc[-1], low.iloc[-1]


def calculate_take_profit_using_resistance(current_price, resistance):
    return resistance if resistance > current_price else None


def calculate_ema_take_profit(df, ema_period=9):
    ema = talib.EMA(df['close'], timeperiod=ema_period)
    return ema.iloc[-1]


def calculate_take_profit_using_atr(df, atr_multiplier=2):
    atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    return df['close'].iloc[-1] + (atr.iloc[-1] * atr_multiplier)


def calculate_fibonacci_levels(low, high, levels=[0.382, 0.5, 0.618]):
    return [high - (high - low) * level for level in levels]


def calculate_dynamic_take_profit(current_price, volatility):
    return current_price + (current_price * volatility)


def calculate_combined_take_profits(current_price, df):
    fixed_tp = current_price * 1.01  # 1%
    atr_tp = calculate_take_profit_using_atr(df, atr_multiplier=2)
    resistance_tp = calculate_support_resistance(df)[0]
    return [fixed_tp, atr_tp, resistance_tp]


####
# Расчет волатильности на основе закрывающих цен
def calculate_volatility(df, window=14):
    returns = df['close'].pct_change()  # Процентное изменение цены
    volatility = returns.rolling(window=window).std()  # Стандартное отклонение
    return volatility.iloc[-1]  # Последняя рассчитанная волатильность


def calculate_average_volatility(df, window=14):
    high_low_diff = df['high'] - df['low']
    avg_volatility = high_low_diff.rolling(window=window).mean() / df['close'].mean()
    return avg_volatility.iloc[-1]


####
def calculate_long_stop_loss_atr(df, atr_multiplier=1.5):
    """
    Рассчитывает стоп-лосс на основе ATR (Average True Range).

    :param df: DataFrame с колонками 'high', 'low', 'close'.
    :param atr_multiplier: Множитель ATR для расчета.
    :return: Уровень стоп-лосса.
    """
    atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    last_atr = atr.iloc[-1]
    current_price = df['close'].iloc[-1]
    return current_price - last_atr * atr_multiplier  # Для LONG


def calculate_long_stop_loss_risk_management(entry_price, balance, risk_per_trade, position_size):
    """
    Рассчитывает стоп-лосс на основе управления рисками.

    :param entry_price: Цена входа в сделку.
    :param balance: Текущий баланс аккаунта.
    :param risk_per_trade: Процент риска на сделку (например, 2% = 0.02).
    :param position_size: Размер позиции в монетах.
    :return: Уровень стоп-лосса.
    """
    max_loss = balance * risk_per_trade  # Максимальная сумма риска
    stop_loss = entry_price - (max_loss / position_size)  # Для LONG
    return stop_loss


def calculate_trailing_long_stop_loss(current_price, trailing_percentage):
    """
    Рассчитывает динамический стоп-лосс.

    :param current_price: Текущая цена актива.
    :param trailing_percentage: Процент от текущей цены для установки стоп-лосса.
    :return: Уровень стоп-лосса.
    """
    return current_price * (1 - trailing_percentage)


def determine_trade_type(buy_price, take_profits, stop_loss, current_price=None):
    """
    Определяет тип сделки (long или short) на основе цен входа, тейк-профитов и стоп-лосса.

    Аргументы:
    buy_price -- цена входа в сделку
    take_profits -- список целей для тейк-профитов
    stop_loss -- уровень стоп-лосса
    current_price -- текущая цена (если передается)

    Возвращает:
    Тип сделки ('long' или 'short') или None, если не удается определить.
    """
    if current_price is None:
        # Начальная проверка на основе buy_price
        if all(tp > buy_price for tp in take_profits) and stop_loss < buy_price:
            return 'long'
        elif all(tp < buy_price for tp in take_profits) and stop_loss > buy_price:
            return 'short'
    else:
        # Проверка после получения текущей цены
        if all(tp > current_price for tp in take_profits) and stop_loss < current_price:
            return 'long'
        elif all(tp < current_price for tp in take_profits) and stop_loss > current_price:
            return 'short'
        elif take_profits[0] < current_price:
            return 'short'
        elif take_profits[0] > current_price:
            return 'long'

    # Если не удалось определить тип сделки
    return None
