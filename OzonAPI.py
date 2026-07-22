import os
import time
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


# Настройка логирования (файл + консоль)
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

log_filename = os.path.join(log_dir, f"ozon_api_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.log")
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)



CLIENT_ID = os.getenv("OZON_CLIENT_ID")
API_KEY = os.getenv("OZON_API_KEY")

if not CLIENT_ID or not API_KEY:
    logger.error("Не найдены ключи Ozon API в .env файле!")
    raise Exception("Не найдены ключи Ozon API")


class OzonAPI:

    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "Client-Id": CLIENT_ID,
            "Api-Key": API_KEY,
            "Content-Type": "application/json"
        })
        logger.info("Инициализация OzonAPI")

    def request(self, endpoint, payload):
        url = self.BASE_URL + endpoint
        logger.info(f"Запрос → {endpoint}")

        for attempt in range(5):
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=20
                )

                if response.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"429 Too Many Requests. Ожидание {wait} сек...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                logger.info(f"Успешный ответ от {endpoint} (статус {response.status_code})")
                return response.json()
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса {endpoint} (попытка {attempt+1}/5): {e}")
                if attempt == 4:
                    logger.error(f"Не удалось выполнить запрос после 5 попыток: {endpoint}")
                    raise
                time.sleep(2 ** attempt)

    def get_products(self, limit=100):
        last_id = ""
        all_products = []
        logger.info("Начало получения списка всех товаров (пагинация)")
        while True:
            try:
                data = self.request(
                    "/v3/product/list",
                    {
                        "filter": {},
                        "last_id": last_id,
                        "limit": limit
                    }
                )
                products = data.get("result", {}).get("items", [])
                if not products:
                    break
                all_products.extend(products)
                logger.info(f"Получено {len(products)} товаров (всего: {len(all_products)})")

                last_id = data.get("result", {}).get("last_id")

                if not last_id:
                    break
            except Exception as e:
                logger.error(f"Ошибка в get_products: {e}")
                break
        
        logger.info(f"Всего получено товаров: {len(all_products)}")
        return all_products
    
    def chunks(self, data, size):
        for i in range(0, len(data), size):
            yield data[i:i + size]

    def get_products_info(self, product_ids):
        all_info = []
        if not product_ids:
            logger.warning("get_products_info вызван с пустым списком product_ids")
            return []

        logger.info(f"Начало получения детальной информации для {len(product_ids)} товаров")

        for chunk in self.chunks(product_ids, 100):
            try:
                data = self.request(
                    "/v3/product/info/list",
                    {
                        "product_id": chunk
                    }
                )
                items = data.get("items", [])
                all_info.extend(items)
                logger.info(f"Получено {len(items)} товаров с информацией")
            except Exception as e:
                logger.error(f"Ошибка при получении информации по чанку: {e}")
        
        logger.info(f"Завершено получение детальной информации. Всего: {len(all_info)} товаров")
        return all_info
