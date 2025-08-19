import asyncio
import logging
import os
import re

from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, UsernameInvalidError
from telethon.tl.types import PeerChannel

from config import session_name, tg_api_id, tg_api_hash, tg_channel_name, session_insider_account, \
    LOGGING, tg_channel_insider_id

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ])

# Регулярное выражение для парсинга сообщения с сигналом
# signal_pattern = r"⚡.*?New Signal\s#([\w-]+)\s+.*\n\s*`?\s*Buy:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP1:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP2:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP3:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP4:\s*`?\s*([\d.]+)\s*\n\s*`?\s*TP5:\s*`?\s*([\d.]+)\s*\n\s*`?\s*STL:\s*`?\s*([\d.]+)"
# TODO: поменялся формат с 11/08/2025?
signal_pattern = (
    r"(\w+)\s*"  # symbol
    r".*Направление\s*-\s*(\w+).*?"  # direction
    r"Вход по рынку\s*-\s*([\d.]+).*?"  # entry price
    r"Наши цели\s*-\s*([\d., ]+).*?"  # targets
    r"Стоп\s*-\s*([\d.]+)"  # stop loss
)


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


async def get_tg_signals_from_insider_trade_by_name(tg_channel_insider: str, limit=100):
    signals = []
    if os.path.exists(f"{session_insider_account}.session"):
        logging.info("Сессия найдена, используем сохраненную.")
    else:
        logging.info("Сессия не найдена, потребуется авторизация.")

    async with TelegramClient(session_insider_account, tg_api_id, tg_api_hash,
                              system_version='1.38.1',
                              device_model='xiaomi',
                              app_version='1.38.1') as client:

        try:
            channel = await client.get_entity(tg_channel_insider)
        except ChannelPrivateError:
            logging.error(
                "Вы не подписаны на канал или он приватный. Убедитесь, что ваш аккаунт в TelegramClient подписан.")
        except UsernameInvalidError:
            logging.error("Username канала недействителен. Попробуйте по ID.")
            dialog = await check_and_get_tg_channel(client, tg_channel_insider)
            if dialog:
                channel = PeerChannel(dialog.id)

            i = 0
            async for message in client.iter_messages(channel, limit=limit):
                message_text = message.text
                message_text = re.sub(r"[^\w\s.,-]", "", message_text)
                message_date = message.date

                if LOGGING:
                    logging.info(f'{i} ({message_date}): {message_text}')
                i += 1

                match = re.search(signal_pattern, message_text, re.DOTALL)
                if match:
                    symbol = match.group(1)
                    direction = match.group(2)
                    buy_price = float(match.group(3))
                    take_profits = [float(x.strip()) for x in match.group(4).split(',')]
                    stop_loss = float(match.group(5))

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


async def get_tg_signals_from_insider_trade_by_id(tg_channel_insider_id: int, limit=100):
    signals = []
    if os.path.exists(f"{session_insider_account}.session"):
        logging.info("Сессия найдена, используем сохраненную.")
    else:
        logging.info("Сессия не найдена, потребуется авторизация.")

    async with TelegramClient(session_insider_account, tg_api_id, tg_api_hash,
                              system_version='1.38.1',
                              device_model='xiaomi',
                              app_version='1.38.1') as client:

        channel = PeerChannel(tg_channel_insider_id)

        i = 0
        async for message in client.iter_messages(channel, limit=limit):
            if message.text is not None:
                message_text = re.sub(r"[^\w\s.,-]", "", message.text, flags=re.UNICODE)
                message_date = message.date

            if LOGGING:
                logging.info(f'{i} ({message_date}): {message_text}')
            i += 1

            match = re.search(signal_pattern, message_text, re.DOTALL)
            if match:
                symbol = match.group(1)
                direction = match.group(2).lower()  # направление
                buy_price = float(match.group(3))
                take_profits = [float(x.strip()) for x in match.group(4).split(',')]
                stop_loss = float(match.group(5))

                signal_data = {
                    'symbol': symbol,
                    'buy_price': buy_price,
                    'take_profits': take_profits,
                    'stop_loss': stop_loss,
                    'direction': direction,
                    'date': message_date
                }
                signals.append(signal_data)
                # logging.info(f"Новый сигнал: {signal_data}")
    return signals


async def check_and_get_tg_channel(client: TelegramClient, tg_name_find: str):
    '''
    Поиск нужного канала и его ID
    :param client:
    :param tg_name_find:
    :return:
    '''
    dialogs = await client.get_dialogs()

    channels = [d for d in dialogs if d.is_channel]
    if not channels:
        logging.info("Каналы не найдены в вашем аккаунте.")
        return None

    logging.info("\n📋 Найденные каналы:")
    for i, dialog in enumerate(channels):
        line = f"{i + 1}. {dialog.title} (id: {dialog.id})"
        if tg_name_find.lstrip('@') == dialog.title:  # 'Insider_Trade'
            line = f"👉 {line} 👈"
            channel_name = dialog.title
            channel_id = dialog.id
            channel = dialog
        logging.info(line)
    return channel


async def send_to_me(message: str):
    if not os.path.exists(f"{session_name}.session"):
        logging.error("Сессия Telegram не найдена! Сначала авторизуйтесь.")
        return

    async with TelegramClient(session_name, tg_api_id, tg_api_hash) as client:
        await client.send_message('@repon06', message)


async def save_to_me(message: str):
    if not os.path.exists(f"{session_name}.session"):
        logging.error("Сессия Telegram не найдена! Сначала авторизуйтесь.")
        return

    async with TelegramClient(session_name, tg_api_id, tg_api_hash) as client:
        await client.send_message('me', message)


if __name__ == "__main__":
    asyncio.run(send_to_me("Привет! Это тестовое сообщение в Избранное 🚀"))

    # signals = asyncio.run(get_tg_signal(limit=50))
    # logging.info(f"1) Получено {len(signals)} сигналов.")

    # signals = asyncio.run(get_tg_signals_from_insider_trade_by_name(tg_channel_insider_name, limit=50))
    # logging.info(f"2) Получено {len(signals)} сигналов.")

    signals = asyncio.run(get_tg_signals_from_insider_trade_by_id(tg_channel_insider_id, limit=10))
    logging.info(f"3) Получено {len(signals)} сигналов.")
