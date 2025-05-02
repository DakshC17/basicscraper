import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import re
import random

# User agents list defined to avoid detection
# This list can be expanded with more user agents for better randomness
# Note: The user agents should be updated periodically to avoid detection
# as websites may block known user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.110 Safari/537.36"
]

# Function to fetch dynamic content using Selenium
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

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception:
        pass

    page_source = driver.page_source
    driver.quit()
    return page_source

# Function to clean and structure extracted data
def clean_and_structure_data(html_content, url):
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove unwanted tags
    for tag in soup(["script", "style", "noscript", "footer", "nav", "aside", "form", "input"]):
        tag.decompose()

    # Remove hidden elements
    for element in soup.find_all(style=lambda s: s and "display:none" in s):
        element.decompose()

    data = {
        "page_title": soup.title.string.strip() if soup.title else "No title found",
        "source_url": url,
        "language": soup.html.get("lang", "not specified") if soup.html else "not specified",
        "headings": [],
        "paragraphs": [],
        "prices": [],
        "images": [],
        "list_items": []
    }

    # Extract headings
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if text:
            data["headings"].append(text)

    # Extract paragraphs
    for tag in soup.find_all("p"):
        text = tag.get_text(strip=True)
        if text and len(text.split()) > 3:
            data["paragraphs"].append(text)

    # Price pattern matching
    price_regex = re.compile(r'[\₹\$\€]\s?[0-9,.]+')
    prices = price_regex.findall(soup.get_text())
    data["prices"] = list(set(prices))  # deduplicate

    # Image URLs (absolute)
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src and not src.startswith("data:image"):
            full_url = urljoin(url, src)
            data["images"].append(full_url)

    # List items
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if text and len(text.split()) > 2:
            data["list_items"].append(text)

    return data

# Streamlit UI
st.set_page_config(page_title="🌐 Universal Web Scraper", layout="centered")
st.title("🕵️ Universal Web Scraper")

st.markdown("This tool uses Selenium + BeautifulSoup to scrape structured data from **any** public webpage.")

url = st.text_input("Enter a URL to scrape", placeholder="https://example.com")

if st.button("Scrape"):
    if not url.startswith("http"):
        st.error("Please enter a valid URL starting with http or https.")
    else:
        try:
            with st.spinner("Scraping the webpage..."):
                html = get_page_source(url)
                structured_data = clean_and_structure_data(html, url)

            st.success("✅ Scraping successful! Here's the structured data:")
            st.json(structured_data)

            st.download_button(
                label="📥 Download JSON",
                data=json.dumps(structured_data, indent=2),
                file_name="scraped_data.json",
                mime="application/json"
            )
        except Exception as e:
            st.error(f"❌ Failed to scrape: {e}")
