import json
import os
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

URL = "https://coins.bank.gov.ua/catalog.html"
BASE_URL = "https://coins.bank.gov.ua"
JSON_FILE = "coins.json"

NEWNESS_HOURS = 24

headers = {"User-Agent": "Mozilla/5.0"}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def clean_spaces(text):
    return re.sub(r"\s+", " ", text).strip()


def format_price(price_text):
    if not price_text:
        return "Немає ціни"

    price_text = clean_spaces(price_text)

    match = re.search(r"[\d\s]+(?:[,.]\d+)?", price_text)
    if not match:
        return price_text

    number_raw = match.group(0)
    number_clean = re.sub(r"\s+", "", number_raw)

    if "," in number_clean or "." in number_clean:
        integer_part, decimal_part = re.split(r"[,.]", number_clean, maxsplit=1)
        formatted_number = f"{int(integer_part):,}".replace(",", " ")
        formatted_number = f"{formatted_number},{decimal_part}"
    else:
        formatted_number = f"{int(number_clean):,}".replace(",", " ")

    suffix = price_text[match.end() :].strip()
    prefix = price_text[: match.start()].strip()

    result = " ".join(part for part in [prefix, formatted_number, suffix] if part)
    return clean_spaces(result)


def parse_coins():
    response = requests.get(URL, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    products = soup.find_all("div", class_="product")

    coins = []

    for product in products:
        name_tag = product.find("a", class_="model_product")
        price_tag = product.find("span", class_="new_price")
        link_tag = product.find("a", class_="p_img_href")
        sale_date_tag = product.find("div", class_="label3 product_label")

        if not name_tag or not link_tag:
            continue

        name = clean_spaces(name_tag.text)
        price = format_price(price_tag.text if price_tag else "")
        link = BASE_URL + link_tag["href"]

        sale_date = clean_spaces(sale_date_tag.text) if sale_date_tag else "Немає дати"

        classes = link_tag.get("class", [])
        in_stock = "nostock" not in classes

        coins.append(
            {
                "name": name,
                "price": price,
                "link": link,
                "sale_date": sale_date,
                "in_stock": in_stock,
            }
        )

    return coins


def load_old_coins():
    if not os.path.exists(JSON_FILE):
        return []

    with open(JSON_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_coins(coins):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(coins, file, ensure_ascii=False, indent=4)


def merge_with_history(old_coins, new_coins):
    old_by_link = {coin["link"]: coin for coin in old_coins}
    current_time = now_iso()

    merged = []

    for coin in new_coins:
        old_coin = old_by_link.get(coin["link"])

        if old_coin:
            coin["first_seen_at"] = old_coin.get("first_seen_at", current_time)
        else:
            coin["first_seen_at"] = current_time

        coin["last_seen_at"] = current_time
        merged.append(coin)

    return merged


def is_new_coin(coin):
    first_seen_at = parse_iso(coin.get("first_seen_at"))

    if not first_seen_at:
        return False

    return datetime.now() - first_seen_at <= timedelta(hours=NEWNESS_HOURS)


def get_new_coins(coins):
    return [coin for coin in coins if is_new_coin(coin)]


def get_available_coins(coins):
    return [coin for coin in coins if coin["in_stock"]]


def get_soon_coins(coins):
    return [
        coin
        for coin in coins
        if not coin["in_stock"] and coin["sale_date"] != "Немає дати"
    ]


def compare_coins(old_coins, new_coins):
    events = []

    old_by_link = {coin["link"]: coin for coin in old_coins}

    for new_coin in new_coins:
        old_coin = old_by_link.get(new_coin["link"])

        if old_coin is None:
            events.append(
                {
                    "type": "new_coin",
                    "coin": new_coin,
                    "message": f"Нова монета: {new_coin['name']}",
                }
            )
            continue

        if old_coin["in_stock"] != new_coin["in_stock"]:
            if new_coin["in_stock"]:
                message = f"Зʼявилась в наявності: {new_coin['name']}"
            else:
                message = f"Зникла з наявності: {new_coin['name']}"

            events.append(
                {"type": "stock_changed", "coin": new_coin, "message": message}
            )

        if old_coin["sale_date"] != new_coin["sale_date"]:
            events.append(
                {
                    "type": "sale_date_changed",
                    "coin": new_coin,
                    "message": (
                        f"Змінилась дата продажу: {new_coin['name']}\n"
                        f"Було: {old_coin['sale_date']}\n"
                        f"Стало: {new_coin['sale_date']}"
                    ),
                }
            )

    return events


def format_coin(coin):
    new_mark = " [НОВА]" if is_new_coin(coin) else ""

    return (
        f"{coin['name']}{new_mark}\n"
        f"Ціна: {coin['price']}\n"
        f"Дата: {coin['sale_date']}\n"
        f"В наявності: {'Так' if coin['in_stock'] else 'Ні'}\n"
        f"Посилання: {coin['link']}"
    )


def print_coins(title, coins):
    print("\n" + title)
    print("=" * 50)

    if not coins:
        print("Нічого не знайдено")
        return

    for coin in coins:
        print(format_coin(coin))
        print("-" * 50)


def main():
    old_coins = load_old_coins()
    parsed_coins = parse_coins()
    coins = merge_with_history(old_coins, parsed_coins)

    events = compare_coins(old_coins, coins)

    if events:
        print("\nПодії")
        print("=" * 50)

        for event in events:
            print(event["message"])
            print(format_coin(event["coin"]))
            print("-" * 50)
    else:
        print("\nЗмін немає")

    print_coins("Нові монети за останні 24 години", get_new_coins(coins))
    print_coins("Монети в наявності", get_available_coins(coins))
    print_coins("Монети, які скоро зʼявляться", get_soon_coins(coins))

    save_coins(coins)

    print("\ncoins.json успішно оновлений")


if __name__ == "__main__":
    main()
