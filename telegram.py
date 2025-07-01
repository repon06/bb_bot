import asyncio
import logging
import os
import re

from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, UsernameInvalidError

from config import session_name, tg_api_id, tg_api_hash, tg_channel_name

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Регулярное выражение для парсинга сообщения с сигналом
signal_pattern = r"⚡.*?New Signal\s#([\w-]+)\s+.*\n\s*`?\s*Buy:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP1:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP2:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP3:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP4:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP5:\s*`?\s*([\d.]+)\s*\n\s*`?\s*STL:\s*`?\s*([\d.]+)"


# TODO: поменялся формат с 20/06/2025?

async def get_tg_signal(limit=100):
    signals = []
    if os.path.exists(f"{session_name}.session"):
        logging.info("Сессия найдена, используем сохраненную.")
    else:
        logging.info("Сессия не найдена, потребуется авторизация.")

    async with TelegramClient(session_name, tg_api_id, tg_api_hash,
                              system_version='1.38.1',
                              device_model='xiaomi',
                              app_version='1.38.1') as client:

        channel = await client.get_entity(tg_channel_name)

        async for message in client.iter_messages(channel, limit=limit):
            message_text = message.text
            message_date = message.date

            match = re.search(signal_pattern, message_text)
            if match:
                symbol = match.group(1)
                buy_price = float(match.group(2))
                take_profits = [float(match.group(i)) for i in range(3, 8)]
                stop_loss = float(match.group(8))

                signal_data = {
                    'symbol': symbol,
                    'buy_price': buy_price,
                    'take_profits': take_profits,
                    'stop_loss': stop_loss,
                    'date': message_date
                }
                signals.append(signal_data)
                # logging.info(f"Новый сигнал: {signal_data}")

    return signals


async def get_tg_signals_from_insider_trade(limit=100):
    signals = []
    if os.path.exists(f"{session_name}.session"):
        logging.info("Сессия найдена, используем сохраненную.")
    else:
        logging.info("Сессия не найдена, потребуется авторизация.")

    async with TelegramClient(session_name, tg_api_id, tg_api_hash,
                              system_version='1.38.1',
                              device_model='xiaomi',
                              app_version='1.38.1') as client:

        try:
            channel = await client.get_entity('@Insider_Trade')
        except ChannelPrivateError:
            print("Вы не подписаны на канал или он приватный. Убедитесь, что ваш аккаунт в TelegramClient подписан.")
        except UsernameInvalidError:
            print("Username канала недействителен. Попробуйте по ID.")

        async for message in client.iter_messages(channel, limit=limit):
            message_text = message.text
            message_date = message.date
    return None


# Запуск асинхронной функции
if __name__ == "__main__":
    signals = asyncio.run(get_tg_signal(limit=50))
    logging.info(f"Получено {len(signals)} сигналов.")

    signals = asyncio.run(get_tg_signals_from_insider_trade(limit=50))
    logging.info(f"Получено {len(signals)} сигналов.")
