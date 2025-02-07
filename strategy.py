from helper.design import red


def should_short(df):
    result = False
    rsi = df['RSI'].iloc[-1]
    ema = df['EMA'].iloc[-1]
    last_close = df['close'].iloc[-1]
    # Условие на SHORT: RSI выше 70 и цена ниже EMA
    # return last_rsi > rsi_threshold and last_close < last_ema
    if rsi > 70 and last_close < ema:
        result = True
        print(f"RSI: {rsi:.2f}, EMA: {ema:.2f}, Last Close: {last_close:.2f}")
        print(f"{red('Есть') if result else 'Нет'} сигнал на SHORT")

    return result


def should_long(df, rsi_threshold=30):
    result = False
    """
    Определяет, стоит ли открывать длинную позицию на основе индикаторов RSI и EMA.
    Args:
        df (DataFrame): Таблица с данными, включая RSI и EMA.
        rsi_threshold (int): Граница RSI для открытия позиции (по умолчанию: 30).

    Returns:
        bool: True, если есть сигнал на покупку (long), иначе False.
    """
    # Получаем последние значения индикаторов
    last_rsi = df['RSI'].iloc[-1]
    last_close = df['close'].iloc[-1]
    last_ema = df['EMA'].iloc[-1]

    # Условие на LONG: RSI ниже 30 и цена выше EMA
    # return last_rsi < rsi_threshold and last_close > last_ema

    # Условие: RSI ниже порога и цена выше EMA
    if last_rsi < rsi_threshold and last_close > last_ema:
        result = True
        print(f"{red("Есть") if result else "Нет"} сигнал на LONG")
    return result  # Нет сигнала


def should_long(df, rsi_threshold=30, volume_threshold=100):
    result = False
    last_rsi = df['RSI'].iloc[-1]
    last_close = df['close'].iloc[-1]
    last_ema = df['EMA'].iloc[-1]
    last_volume = df['volume'].iloc[-1]

    # Условие на RSI, EMA и объем
    if last_rsi < rsi_threshold and last_close > last_ema and last_volume > volume_threshold:
        result = True
        print(f"{red("Есть") if result else "Нет"} сигнал на LONG")
    return result
