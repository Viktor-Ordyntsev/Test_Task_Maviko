import pandas as pd
import re
import sys

def clean_price(price):
    if pd.isna(price) or price == '':
        return None
    p = str(price).strip()
    p = re.sub(r'[^\d.,]', '', p)
    p = p.replace(',', '.')
    try:
        return float(p)
    except ValueError:
        return None


def parse_name(text):
    if pd.isna(text) or not isinstance(text, str):
        return pd.Series([None, None, '1'])
    
    text = text.strip()
    
    brand = None
    brand_match = re.search(r'\b(Mavico|MAVICO|DBA|Деталиус)\b', text, re.IGNORECASE)
    if brand_match:
        brand = brand_match.group(1)
    else:
        brand_fallback = re.match(r'^([A-Za-zА-Яа-яЁё]+)', text)
        brand = brand_fallback.group(1) if brand_fallback else None
    

    pattern = rf'{re.escape(brand)}\s+([A-Z0-9][A-Z0-9.-]*[A-Z0-9]|[\w]+)'
    oem_match = re.search(pattern, text, re.IGNORECASE)
    
    # Количество
    qty_match = re.search(r'(\d+)\s*(шт|комплект|комп|к-т|пара|set|pcs)', text, re.IGNORECASE)
    qty = qty_match.group(1) if qty_match else '1'
    
    oem = oem_match.group(1) if oem_match else None
    return pd.Series([brand, oem, qty])


if __name__ == "__main__":
    input_file = 'catalog_raw.csv'
    output_file = 'catalog_clean.csv'
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print(f"Читаем файл: {input_file}")
    df = pd.read_csv(input_file, dtype=str)
    
    print(f"Исходный размер: {df.shape}")
    
    df = df.dropna(how='all').reset_index(drop=True)
    
    df['price'] = df['price'].apply(clean_price)
    
    df[['brand', 'oem_number', 'quantity']] = df['name'].apply(parse_name)
    
    df = df.drop_duplicates(subset=['offer_id', 'name']).reset_index(drop=True)
    
    cols = ['offer_id', 'brand', 'oem_number', 'name', 'price', 'quantity', 'stock']
    df_clean = df[cols].copy()
    
    df_clean.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"Готово! Сохранено в {output_file}")
    print(f"Итоговый размер: {df_clean.shape}")
    print("\nПервые 5 строк:")
    print(df_clean.head().to_string(index=False))