import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
import json

# Setup headless Chrome driver
def get_dynamic_page(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Use system Chromium if available
    chrome_options.binary_location = "/usr/bin/chromium-browser"

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager(driver_version="135.0.7049.52").install()),
        options=chrome_options
    )

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
    })

    driver.get(url)
    time.sleep(5)  # wait for dynamic content to load
    html = driver.page_source
    driver.quit()
    return html

# Clean and extract product-level data
def extract_products(html):
    soup = BeautifulSoup(html, "html.parser")
    product_data = []

    # Remove unnecessary tags
    for tag in soup(["script", "style", "noscript", "footer", "nav", "aside", "form", "input"]):
        tag.decompose()

    # Attempt to find product containers
    containers = soup.find_all(lambda tag: tag.name in ["div", "section", "article"] and (
        "product" in (tag.get("class") or []) or "item" in (tag.get("class") or []) or len(tag.find_all("p")) > 2
    ))

    price_regex = re.compile(r'[\₹\$\€]\s?[0-9,.]+')

    for c in containers:
        text = c.get_text(separator=" ", strip=True)

        # Skip containers with very little content
        if len(text.split()) < 5:
            continue

        title = ""
        brand = ""
        price = ""
        quantity = ""
        description = ""

        # Title / Name (h1-h4 or strong tags)
        for h in c.find_all(["h1", "h2", "h3", "h4", "strong"]):
            title = h.get_text(strip=True)
            if title:
                break

        # Brand (look for "Brand" keyword nearby)
        brand_text = c.find(string=re.compile(r'Brand[:\s]', re.I))
        if brand_text:
            brand = brand_text.strip()

        # Price
        found_price = price_regex.findall(c.get_text())
        if found_price:
            price = found_price[0]

        # Quantity
        quantity_match = re.search(r'(\d+\s?(g|ml|kg|pack|pcs|piece|tablet|capsule))', text, re.I)
        if quantity_match:
            quantity = quantity_match.group(1)

        # Description (first decent paragraph or block of text)
        paragraphs = c.find_all("p")
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            if len(p_text.split()) > 5:
                description = p_text
                break

        product_data.append({
            "title": title,
            "brand": brand,
            "price": price,
            "quantity": quantity,
            "description": description
        })

    return product_data

# Streamlit UI
st.set_page_config(page_title="🛒 Product Web Scraper", layout="centered")
st.title("🛍️ Dynamic Product Scraper")

st.markdown("Scrape structured **product-wise data** from any public shopping/product page.")

url = st.text_input("Enter product page URL", placeholder="https://example.com")

if st.button("Scrape Products"):
    if not url.startswith("http"):
        st.error("Please enter a valid URL starting with http or https.")
    else:
        try:
            with st.spinner("Scraping... Please wait"):
                html = get_dynamic_page(url)
                products = extract_products(html)

            if not products:
                st.warning("No product-like content was extracted. The site may use anti-bot techniques or custom JS.")

            st.success(f"✅ Found {len(products)} products.")
            for i, prod in enumerate(products):
                st.subheader(f"🧾 Product {i+1}")
                st.text(f"Title: {prod['title']}")
                st.text(f"Brand: {prod['brand']}")
                st.text(f"Price: {prod['price']}")
                st.text(f"Quantity: {prod['quantity']}")
                st.text(f"Description: {prod['description']}")

            # Download JSON
            st.download_button(
                label="📥 Download All as JSON",
                data=json.dumps(products, indent=2),
                file_name="products.json",
                mime="application/json"
            )
        except Exception as e:
            st.error(f"❌ Failed to scrape: {e}")
