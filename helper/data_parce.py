from datetime import datetime
import re


def parse_trade_signal(signal_text):
    """
    Парсит сигнал о торговле в нужный формат.

    Аргументы:
    signal_text -- строка с сигналом в формате:
        ⚡⚡New Signal #SYMBOL-PAIR или #SYMBOLPAIR
        🌐 Exchange: #Exchange Spot
        Buy:  0.4900000
        TP1:  0.4953900
        TP2:  0.5002900
        TP3:  0.5051900
        TP4:  0.5100900
        TP5:  0.5149900
        STL:  0.4650100

    Возвращает:
    dict -- словарь с парсенными данными:
        {
            'symbol': 'SYMBOL/PAIR',
            'buy_price': 0.4900000,
            'take_profits': [0.4953900, 0.5002900, 0.5051900, 0.5100900, 0.5149900],
            'stop_loss': 0.4650100
        }
    """
    try:
        # Ищем название символа (учитываем как форматы с дефисом, так и без)
        symbol_match = re.search(r'#([\w-]+)', signal_text)
        if not symbol_match:
            raise ValueError("Не удалось найти символ в сигнале.")

        raw_symbol = symbol_match.group(1)
        # Преобразуем символ в формат без "-"
        symbol = raw_symbol.replace('-', '')

        # Ищем цену покупки
        buy_match = re.search(r'Buy:\s+([\d.]+)', signal_text)
        if not buy_match:
            raise ValueError("Не удалось найти цену покупки.")

        buy_price = float(buy_match.group(1))

        # Ищем тейк-профиты
        take_profits = []
        for i in range(1, 6):  # TP1, TP2, ..., TP5
            tp_match = re.search(f'TP{i}:\s+([\d.]+)', signal_text)
            if tp_match:
                take_profits.append(float(tp_match.group(1)))

        # Ищем стоп-лосс
        sl_match = re.search(r'STL:\s+([\d.]+)', signal_text)
        if not sl_match:
            raise ValueError("Не удалось найти стоп-лосс.")

        stop_loss = float(sl_match.group(1))

        return {
            'symbol': symbol,
            'buy_price': buy_price,
            'take_profits': take_profits,
            'stop_loss': stop_loss,
            'date': datetime.now().date()
        }

    except Exception as e:
        print(f"Ошибка при парсинге сигнала: {e}")
        return None


def parse_trade_signals(signals_text):
    """
    Парсит несколько сигналов о торговле в нужный формат.

    Аргументы:
    signals_text -- строка, содержащая несколько сигналов.

    Возвращает:
    list -- список словарей с парсенными сигналами.
    """
    # Разделяем текст на сигналы, каждый из которых начинается с "⚡⚡New Signal"
    signals = re.split(r'(?=⚡⚡New Signal)', signals_text.strip())

    # Убираем пустые строки, которые могли появиться из-за лишних переносов
    signals = [signal.strip() for signal in signals if signal.strip()]

    parsed_signals = []
    for signal_text in signals:
        try:
            parsed_signal = parse_trade_signal(signal_text)
            if parsed_signal:
                parsed_signals.append(parsed_signal)
        except ValueError as e:
            print(f"Ошибка при парсинге сигнала: {e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")

    return parsed_signals
