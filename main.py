import requests
from bs4 import BeautifulSoup

url = "https://coins.bank.gov.ua/catalog.html"

headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers)

x = 1
print(x)

soup = BeautifulSoup(response.text, "html.parser")

products = soup.find_all("div", class_="product")

for product in products:
    # Назва
    name_tag = product.find("a", class_="model_product")

    # Ціна
    price_tag = product.find("span", class_="new_price")

    # Посилання
    link_tag = product.find("a", class_="model_product")

    if name_tag:
        name = name_tag.text.strip()

        link = "https://coins.bank.gov.ua" + link_tag["href"]

        if price_tag:
            price = price_tag.text.strip()
        else:
            price = "Немає ціни"

        print("=" * 50)
        print("Назва:", name)
        print("Ціна:", price)
        print("Посилання:", link)
