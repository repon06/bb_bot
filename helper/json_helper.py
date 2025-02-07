import json

from strategy import should_long, should_short


def is_json(string):
    try:
        json.loads(string)
        return True
    except ValueError:
        return False


def get_error(bybit_error):
    error = bybit_error.args[0]
    if is_json(error):
        error_data = json.loads(error[error.find('{'):])
        return error_data.get("retMsg", "No message provided")
    else:
        return error


def print_info(df, symbol):
    if should_long(df) or should_short(df):
        print(symbol)
        print(df.head())  # DataFrame с индикаторами
        print(df['close'].isna().sum())  # Проверьте количество пропущенных значений
        print(df['close'].describe())  # Пример статистики по данным
