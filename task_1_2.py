import os
import csv
import logging
import traceback
import requests
from datetime import datetime
from OzonAPI import OzonAPI

# Настройка логирования (файл + консоль)
log_dir = "logs"
report_dir = "reports"

os.makedirs(log_dir, exist_ok=True)
os.makedirs(report_dir, exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')


console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


log_filename = os.path.join(log_dir, f"ozon_log_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.log")
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


try:

    LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", 5))
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    api = OzonAPI()
    detail_products = []
    low_stock_items=[]

    # Получение списка товаров с использованием пагинации
    products = api.get_products()
    logger.info(f"Получено {len(products)} товаров из api.get_products()")

    product_ids = [item["product_id"] for item in products]
    logger.info(f"Собрано {len(product_ids)} product_id для детального запроса")

    # Получение дополнительной информации о товарах
    products_info_all = api.get_products_info(product_ids)
    logger.info(f"Получена детальная информация о {len(products_info_all)} товарах")

    # Обработка данных и выделение нужных полей
    for item in products_info_all:
        try:
            name = item.get("name", "Без названия")
            price = item.get("price", "—")
            sku = item.get("sku", "")
            offer_id = item.get("offer_id", "")
            
            stocks_list = item.get("stocks", {}).get("stocks", [])
            stock = stocks_list[0].get("present", 0) if stocks_list else 0
            
            status = "заканчивается" if stock < LOW_STOCK_THRESHOLD else ""
            
            detail_products.append({
                "name": name,
                "price": price,
                "stock": stock,
                "status": status,
                "sku": sku,
                "offer_id": offer_id
            })
            
            if status:
                low_stock_items.append((name, stock, price))
            
        except Exception as e:
            logger.warning(f"Ошибка обработки товара: {e}")
        
    logger.info(f"Обработано {len(detail_products)} товаров для экспорта")

    # Экспорт данных в CSV
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    filename = f"ozon_products_stock_{timestamp}.csv"
    filepath = os.path.join(report_dir, filename)   # ← сохраняем в папку reports

    with open(filepath, mode='w', encoding='utf-8', newline='') as f:
        fieldnames = ["name", "price", "stock", "status", "sku", "offer_id"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detail_products)

    logger.info(f"Файл CSV успешно создан: {filename}")
    logger.info(f"Всего строк в CSV: {len(detail_products)}")

# Функция для отправки сообщения в Telegram
    def send_telegram_message(text):
        if not BOT_TOKEN or not CHAT_ID:
            logger.warning("Telegram бот токен или chat_id не указаны")
            return False
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "parse_mode": "HTML",
            "text": text
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                logger.info("Сообщение успешно отправлено в Telegram")
                return True
            else:
                logger.error(f"Ошибка отправки в Telegram: {r.text}")
                return False
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение в Telegram: {e}")
            return False

    # Формирование сообщения
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    message = f"<b>Отчёт по остаткам на {timestamp}</b>\n\n"
    message += f"Всего товаров: <b>{len(detail_products)}</b> | "
    message += f"Низкий остаток: <b>{len(low_stock_items)}</b>\n\n"

    # Показываем первые 15 товаров
    for item in detail_products[:15]:
        name = item["name"]
        stock = item["stock"]
        price = item["price"]
        status = item["status"]
        
        emoji = "🔴" if "заканчивается" in status or stock == 0 else "✅"
        message += f"{emoji} <b>{name}</b>\n"
        message += f"   Остаток: <b>{stock}</b> шт. | Цена: {price} ₽\n\n"

    if len(detail_products) > 15:
        message += f"... и ещё {len(detail_products) - 15} товаров\n\n"

    message += f"📎 Полный отчёт во вложении."
    send_telegram_message(message)

    # Отправка CSV файла 
    def send_telegram_document(filepath, caption=""):
        if not BOT_TOKEN or not CHAT_ID:
            logger.warning("Telegram данные не настроены")
            return False
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            with open(filepath, 'rb') as f:
                files = {'document': (os.path.basename(filepath), f, 'text/csv')}
                data = {
                    'chat_id': CHAT_ID,
                    'caption': caption,
                    'parse_mode': 'HTML'
                }
                r = requests.post(url, data=data, files=files, timeout=30)
            
            if r.status_code == 200:
                logger.info("CSV файл отправлен в Telegram")
                return True
            else:
                logger.error(f"Ошибка отправки файла: {r.text}")
                return False
        except Exception as e:
            logger.error(f"Не удалось отправить файл: {e}")
            return False

    # Отправляем файл
    send_telegram_document(filepath, f"Полный отчёт по остаткам — {timestamp}")

except Exception as e:
    logger.error("Критическая ошибка при выполнении скрипта!")
    logger.error(f"Тип ошибки: {type(e).__name__}")
    logger.error(f"Сообщение: {e}")
    logger.error("Полный traceback:\n" + traceback.format_exc())

finally:
    logger.info("Выгрузка завершена (с ошибками или успешно)")
    logger.info(f"Лог сохранён в: {log_filename}")