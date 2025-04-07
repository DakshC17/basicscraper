import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json
import time
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.110 Safari/537.36"
]

# Stealthy Selenium Page Fetcher
def get_page_source(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    user_agent = random.choice(USER_AGENTS)
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument("accept-language=en-US,en;q=0.9")

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    driver.get(url)
    time.sleep(random.uniform(3, 6))
    page_source = driver.page_source
    driver.quit()
    return page_source

# Detect site type
def detect_website_type(url, soup):
    domain = url.lower()
    if "wikipedia.org" in domain:
        return "wikipedia"
    elif "myntra.com" in domain:
        return "myntra"
    elif "flipkart.com" in domain:
        return "flipkart"
    elif soup.find("article"):
        return "blog"
    elif soup.find("h1") and soup.find("p"):
        return "generic"
    else:
        return "unknown"

# Wikipedia parser
def parse_wikipedia(soup):
    title = soup.find("h1").text if soup.find("h1") else "No title"
    summary = ""
    for para in soup.select("div.mw-parser-output > p"):
        text = para.get_text(strip=True)
        if text:
            summary += text + "\n"
            if len(summary) > 500:
                break
    return {
        "type": "wikipedia",
        "title": title,
        "summary": summary.strip()
    }

# Myntra parser
def parse_myntra(soup):
    products = []
    for product in soup.select("li.product-base"):
        title = product.select_one("h3.product-brand")
        name = product.select_one("h4.product-product")
        price = product.select_one("span.product-discountedPrice")
        original_price = product.select_one("span.product-strike")
        discount = product.select_one("span.product-discountPercentage")
        image = product.select_one("img.img-responsive")
        products.append({
            "brand": title.get_text(strip=True) if title else None,
            "name": name.get_text(strip=True) if name else None,
            "price": price.get_text(strip=True) if price else None,
            "original_price": original_price.get_text(strip=True) if original_price else None,
            "discount": discount.get_text(strip=True) if discount else None,
            "image_url": image['src'] if image and image.get('src') else None
        })
    return {
        "type": "myntra",
        "products": products
    }

# Generic fallback
def parse_generic(soup):
    title = soup.title.string.strip() if soup.title else "No title"
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 50]
    return {
        "type": "generic",
        "title": title,
        "summary": " ".join(paragraphs[:3])
    }

# Main cleaner
def clean_and_structure_data(html_content, url):
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove unnecessary tags
    for tag in soup(["script", "style", "noscript", "footer", "nav", "aside", "form", "input"]):
        tag.decompose()

    # Remove hidden elements
    for element in soup.find_all(attrs={"style": lambda x: x and "display:none" in x}):
        element.decompose()

    # Extract clean visible text blocks
    text_blocks = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = tag.get_text(strip=True)
        if text and len(text.split()) > 3:  # Ignore too-short or empty lines
            text_blocks.append(text)

    return {
        "page_title": soup.title.string.strip() if soup.title else "No title found",
        "source_url": url,
        "text_blocks": text_blocks
    }

# Streamlit UI
st.set_page_config(page_title="🌐 Powerful Dynamic Scraper", layout="centered")
st.title("🕵️ Powerful Dynamic Scraper")

st.markdown("Bypasses most bot protections. Scrape websites like Wikipedia, Myntra, Blogs, etc.")

url = st.text_input("Enter a URL to scrape", placeholder="https://www.wikipedia.org")

if st.button("Scrape"):
    if not url.startswith("http"):
        st.error("Please enter a valid URL with http or https.")
    else:
        try:
            html = get_page_source(url)
            cleaned_data = clean_and_structure_data(html, url)

            st.success("✅ Scraping successful! Here's the cleaned structured data:")
            st.json(cleaned_data)

            json_str = json.dumps(cleaned_data, indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name="scraped_data.json",
                mime="application/json"
            )

        except Exception as e:
            st.error(f"❌ Failed to scrape: {e}")
