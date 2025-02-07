    crypto_bot/
    │
    ├── config.py             # Конфигурационные параметры
    ├── data_fetcher.py       # Функции для получения данных
    ├── indicators.py         # Расчеты технических индикаторов
    ├── strategy.py           # Логика стратегии
    ├── orders.py             # Управление ордерамиwhich pip
    ├── model.py              # Машинное обучение для анализа сделок
    ├── utils.py              # Вспомогательные функции
    ├── main.py               # Основной скрипт запуска бота
    ├── requirements.txt      # Зависимости
    └── README.md             # Документация

    brew install ta-lib
    pip install TA-Lib    
    pip install -r requirements.txt
    python3 -m pip install <package_name>

python3 -m venv venv

pip install websocket-client    
python main.py

Установите MongoDB через Homebrew:
    brew tap mongodb/brew
    brew install mongodb-community
Запустите MongoDB:
    brew services start mongodb/brew/mongodb-community
    mongod --dbpath ./mongo_data
Остановить МонгоДБ:
    ps aux | grep mongod
    kill <PID>
pip install pymongo