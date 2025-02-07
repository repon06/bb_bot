import pandas as pd
import talib

columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']


def calculate_rsi(data, period=14):
    """Relative Strength Index (RSI)"""
    df = pd.DataFrame(data, columns=columns)
    df['RSI'] = talib.RSI(df['close'], timeperiod=period)
    return df


def calculate_ema(data, period=9):
    """
    Стратегия - скользящие средние
    Exponential Moving Average
    :param data:
    :param period:
    :return:
    """
    df = pd.DataFrame(data, columns=columns)
    df['EMA'] = talib.EMA(df['close'], timeperiod=period)
    return df


def calculate_indicators(data):
    """Рассчитываем стратегии RSI & EMA"""
    import pandas as pd
    import talib

    df = pd.DataFrame(data, columns=columns)
    # Проверить, есть ли NaN в данных
    if df['close'].isna().sum() > 0:
        df['close'] = df['close'].fillna(method='ffill')

    df['RSI'] = talib.RSI(df['close'], timeperiod=14)
    df['EMA'] = talib.EMA(df['close'], timeperiod=9)

    # Удаляем строки с NaN
    df = df.dropna(subset=['RSI', 'EMA'])
    return df


# Получаем текущую цену из последних данных
def get_current_price(df: pd.DataFrame) -> float:
    return df['close'].iloc[-1]
