from datetime import datetime


def to_datetime(timestamp):
    # print(candle_datetime.strftime('%Y-%m-%d %H:%M:%S'))
    return datetime.fromtimestamp(timestamp / 1000)


def to_timestamp(date_time):
    return int(datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
