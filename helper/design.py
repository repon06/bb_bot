import json
import os

import matplotlib.pyplot as plt
import pandas as pd
from colorama import Fore, Style

from helper.date_helper import to_datetime


def red(text):
    return f"{Fore.RED}{str(text)}{Style.RESET_ALL}"


def green(text):
    return f"{Fore.GREEN}{str(text)}{Style.RESET_ALL}"


def yellow(text):
    return f"{Fore.YELLOW}{str(text)}{Style.RESET_ALL}"


def print_dict(dict):
    json.dumps(dict, indent=4)


def print_candles(candles):
    for candle in candles:  # Вывод первых нескольких свечей
        print(f"Timestamp: {to_datetime(candle[0])}, Open: {candle[1]:.10f}, "
              f"High: {candle[2]:.10f}, Low: {candle[3]:.10f}, Close: {candle[4]:.10f}, Volume: {candle[5]}")


def print_graphic(candles, symbol, stop_loss=None, take_profits=None):
    # Перевести данные в pandas DataFrame
    data = []
    for candle in candles:
        data.append({
            'timestamp': to_datetime(candle[0]),
            'open': candle[1],
            'high': candle[2],
            'low': candle[3],
            'close': candle[4],
            'volume': candle[5]
        })

    # Создаем DataFrame
    df = pd.DataFrame(data)

    # Визуализируем график
    plt.figure(figsize=(10, 6))

    # График закрытия (Close)
    plt.plot(df['timestamp'], df['close'], label='Close', color='blue')

    # График открытия (Open)
    plt.plot(df['timestamp'], df['open'], label='Open', color='green', linestyle='--')

    # График максимальной цены (High)
    plt.plot(df['timestamp'], df['high'], label='High', color='red', linestyle=':')

    # График минимальной цены (Low)
    plt.plot(df['timestamp'], df['low'], label='Low', color='orange', linestyle='-.')

    # Добавление уровней тейк-профита
    if take_profits:
        for i, tp in enumerate(take_profits, start=1):
            plt.axhline(y=tp, color='green', linestyle='--', alpha=0.7, label=f'Take Profit {i}')
            plt.text(df['timestamp'].iloc[-1], tp, f'TP{i}: {tp:.4f}', color='green', fontsize=9)

    # Добавление уровня стоп-лосса
    if stop_loss:
        plt.axhline(y=stop_loss, color='red', linestyle='--', alpha=0.7, label='Stop Loss')
        plt.text(df['timestamp'].iloc[-1], stop_loss, f'SL: {stop_loss:.4f}', color='red', fontsize=9)

    # Настройка графика
    plt.title(f'Price Data for {symbol}')
    plt.xlabel('Timestamp')
    plt.ylabel('Price (USDT)')
    plt.legend()
    plt.grid(True)

    # Отображение графика
    plt.xticks(rotation=45)  # Поворот меток времени для лучшего отображения
    plt.tight_layout()  # Автоматическая настройка размера

    save_graphic(plt, candles, symbol)
    plt.show()


def save_graphic(plt, candles, symbol):
    # Формирование имени файла с текущей датой и временем
    timestamp_str = to_datetime(candles[-1][0]).strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"graphics/{symbol.replace('/', '_')}_{timestamp_str}.png"  # Имя файла с валютой и временем

    # Создаем директорию, если она не существует
    directory = os.path.dirname(filename)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Сохранение графика в файл
    plt.savefig(filename)
    plt.close()  # Закрытие графика, чтобы избежать пустого файла
    print(f"График сохранен в файл: {filename}")
