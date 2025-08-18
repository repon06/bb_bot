import logging

from pymongo import MongoClient

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)


class MongoDBClient:
    def __init__(self, db_name, collection_name, host='localhost', port=27017):
        """
        Инициализация клиента MongoDB.

        :param db_name: Имя базы данных.
        :param collection_name: Имя коллекции.
        :param host: Хост MongoDB (по умолчанию 'localhost').
        :param port: Порт MongoDB (по умолчанию 27017).
        """
        self.client = MongoClient(host, port)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def _insert_one(self, data):
        """Вставляет один документ в коллекцию."""
        result = self.collection.insert_one(data)
        logging.info(f"Inserted signal or order with symbol: {data} and ID: {result.inserted_id}")
        return result.inserted_id

    def _find_one(self, query):
        """Ищет один документ, соответствующий запросу."""
        return self.collection.find_one(query)

    def find_all(self, query=None):
        """Ищет все документы, соответствующие запросу."""
        return list(self.collection.find(query or {}))

    def update_one(self, query, update_data):
        """Обновляет один документ, соответствующий запросу."""
        result = self.collection.update_one(query, {'$set': update_data})
        return result.modified_count

    def delete_one(self, query):
        """Удаляет один документ, соответствующий запросу."""
        result = self.collection.delete_one(query)
        return result.deleted_count

    def delete_many(self, query):
        """Удаляет все документы, соответствующие запросу."""
        result = self.collection.delete_many(query)
        return result.deleted_count

    def close(self):
        """Закрывает соединение с MongoDB."""
        self.client.close()

    def get_all_documents(self):
        """
        Возвращает все документы из коллекции.
        """
        return list(self.collection.find())

    def insert_many(self, param):
        result = self.collection.insert_many(param)
        logging.info(f"Inserted signal or order with symbol: {param} and IDs: {result.inserted_ids}")
        return result.inserted_ids

    # --- Специфичные методы для сигналов ---
    def find_signal(self, symbol, buy_price, direction):
        return self._find_one({'symbol': symbol, 'buy_price': buy_price, 'direction': direction})

    def insert_signal(self, signal):
        return self._insert_one(signal)

    def insert_order(self, order):
        return self._insert_one(order)
