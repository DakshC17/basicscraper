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

# Clean and extract content from various websites
def extract_content(html, content_type="auto"):
    soup = BeautifulSoup(html, "html.parser")
    extracted_data = []

    # Remove unnecessary tags
    for tag in soup(["script", "style", "noscript", "footer", "nav", "aside", "form", "input"]):
        tag.decompose()
    
    # Automatically detect content type if not specified
    if content_type == "auto":
        # Check for common e-commerce patterns
        price_elements = soup.find_all(string=re.compile(r'[\₹\$\€]\s?[0-9,.]+'))
        product_elements = soup.find_all(["div", "li"], class_=lambda c: c and ("product" in c.lower() if c else False))
        
        # Check for news article patterns
        article_elements = soup.find_all(["article", "div"], class_=lambda c: c and any(x in c.lower() for x in ["article", "post", "story", "news"]) if c else False)
        published_elements = soup.find_all(string=re.compile(r'published|posted on|date:', re.I))
        
        if (len(price_elements) > 2 or len(product_elements) > 2):
            content_type = "product"
        elif len(article_elements) > 0 or len(published_elements) > 0:
            content_type = "article"
        else:
            content_type = "generic"
    
    # Process based on content type
    if content_type == "product":
        extracted_data = extract_products(soup)
    elif content_type == "article":
        extracted_data = extract_articles(soup)
    else:  # generic content
        extracted_data = extract_generic(soup)
    
    return extracted_data

# Extract product information from e-commerce sites
def extract_products(soup):
    product_data = []
    price_regex = re.compile(r'[\₹\$\€]\s?[0-9,.]+')
    
    # Try multiple container selectors common in e-commerce sites
    containers = []
    
    # Method 1: Class-based detection
    for class_hint in ["product", "item", "card", "goods", "sku"]:
        containers.extend(soup.find_all(["div", "li", "article"], 
                                      class_=lambda c: c and class_hint in c.lower() if c else False))
    
    # Method 2: Schema.org structured data
    product_schema = soup.find_all(itemtype=re.compile(r'schema.org/Product'))
    if product_schema:
        containers.extend(product_schema)
    
    # Method 3: HTML5 structural elements
    if not containers:
        containers = soup.find_all(["article", "section", "div"], 
                                 class_=lambda c: c and len(c.split()) < 3 if c else True)
        # Filter to keep only those with prices or titles
        containers = [c for c in containers if 
                     (c.find(string=price_regex) or 
                      c.find(["h1", "h2", "h3", "h4"]) or
                      c.find(class_=lambda c: c and "title" in c.lower() if c else False))]
    
    # Process each container
    for c in containers:
        text = c.get_text(separator=" ", strip=True)
        
        # Skip containers with very little content
        if len(text.split()) < 5:
            continue
            
        product = {
            "title": "",
            "brand": "",
            "price": "",
            "quantity": "",
            "description": "",
            "url": "",
            "image_url": ""
        }
        
        # Title detection
        title_element = c.find(["h1", "h2", "h3", "h4", "strong"]) or c.find(class_=lambda c: c and "title" in c.lower() if c else False)
        if title_element:
            product["title"] = title_element.get_text(strip=True)
        
        # Brand detection
        brand_element = c.find(string=re.compile(r'Brand[:\s]', re.I))
        if brand_element:
            brand_match = re.search(r'Brand[:\s]\s*([^\n\r]+)', brand_element, re.I)
            if brand_match:
                product["brand"] = brand_match.group(1).strip()
        
        # Price detection
        found_price = price_regex.findall(c.get_text())
        if found_price:
            product["price"] = found_price[0]
        
        # Quantity detection
        quantity_match = re.search(r'(\d+\s?(g|ml|kg|pack|pcs|piece|tablet|capsule))', text, re.I)
        if quantity_match:
            product["quantity"] = quantity_match.group(1)
        
        # Description detection
        description_element = c.find(["p", "div"], class_=lambda c: c and "desc" in c.lower() if c else False)
        if description_element:
            product["description"] = description_element.get_text(strip=True)
        else:
            for p in c.find_all("p"):
                p_text = p.get_text(strip=True)
                if len(p_text.split()) > 5:
                    product["description"] = p_text
                    break
        
        # Image URL detection
        img = c.find("img")
        if img and img.get("src"):
            product["image_url"] = img["src"]
        
        # Product URL detection
        a = c.find("a")
        if a and a.get("href"):
            product["url"] = a["href"]
        
        # Add the product only if at least title or price is found
        if product["title"] or product["price"]:
            product_data.append(product)
    
    return product_data

# Extract information from news/article sites
def extract_articles(soup):
    article_data = []
    
    # Try to find the main article container
    main_article = soup.find("article") or soup.find(class_=lambda c: c and "article" in c.lower() if c else False)
    
    if main_article:
        # Single article page
        article = {
            "title": "",
            "author": "",
            "published_date": "",
            "content": "",
            "summary": "",
            "image_url": ""
        }
        
        # Title
        title_element = main_article.find(["h1", "h2"]) or soup.find(["h1", "h2"])
        if title_element:
            article["title"] = title_element.get_text(strip=True)
        
        # Author
        author_element = soup.find(string=re.compile(r'by|author[:\s]', re.I)) or \
                         soup.find(["span", "div", "p"], class_=lambda c: c and "author" in c.lower() if c else False)
        if author_element:
            author_text = author_element.get_text(strip=True)
            author_match = re.search(r'(?:by|author[:\s])\s*([^\n\r|]+)', author_text, re.I)
            if author_match:
                article["author"] = author_match.group(1).strip()
            else:
                article["author"] = author_text
        
        # Published date
        date_element = soup.find(string=re.compile(r'published|posted on|date:', re.I)) or \
                      soup.find(["span", "div", "time"], class_=lambda c: c and any(x in c.lower() for x in ["date", "time", "published"]) if c else False)
        if date_element:
            article["published_date"] = date_element.get_text(strip=True)
        
        # Content
        content_elements = main_article.find_all("p")
        if content_elements:
            article["content"] = " ".join([p.get_text(strip=True) for p in content_elements if len(p.get_text(strip=True)) > 0])
            if article["content"] and not article["summary"] and len(article["content"]) > 150:
                article["summary"] = article["content"][:147] + "..."
        
        # Image
        img = main_article.find("img") or soup.find("img")
        if img and img.get("src"):
            article["image_url"] = img["src"]
        
        article_data.append(article)
    else:
        # Multiple articles listing page
        article_containers = soup.find_all(["article", "div", "section"], 
                                          class_=lambda c: c and any(x in c.lower() for x in ["article", "post", "story", "news-item"]) if c else False)
        
        if not article_containers:
            # Fallback to find elements with headlines
            article_containers = soup.find_all(lambda tag: tag.name in ["div", "li"] and tag.find(["h2", "h3", "h4"]))
        
        for container in article_containers:
            article = {
                "title": "",
                "author": "",
                "published_date": "",
                "summary": "",
                "url": "",
                "image_url": ""
            }
            
            # Title
            title_element = container.find(["h1", "h2", "h3", "h4"])
            if title_element:
                article["title"] = title_element.get_text(strip=True)
            
            # Summary
            summary_element = container.find("p")
            if summary_element:
                article["summary"] = summary_element.get_text(strip=True)
            
            # URL
            a = container.find("a")
            if a and a.get("href"):
                article["url"] = a["href"]
            
            # Image
            img = container.find("img")
            if img and img.get("src"):
                article["image_url"] = img["src"]
            
            if article["title"]:
                article_data.append(article)
    
    return article_data

# Extract generic content from any website
def extract_generic(soup):
    generic_data = [{
        "title": "",
        "content_blocks": [],
        "images": []
    }]
    
    # Title
    title_element = soup.find("h1") or soup.find("title")
    if title_element:
        generic_data[0]["title"] = title_element.get_text(strip=True)
    
    # Main content blocks
    main_container = soup.find(["main", "article", "div"], id=lambda i: i and i.lower() in ["main", "content", "page"] if i else False) or \
                    soup.find(["main", "article", "div"], class_=lambda c: c and any(x in c.lower() for x in ["main", "content", "page"]) if c else False) or \
                    soup
    
    # Extract paragraphs
    paragraphs = main_container.find_all(["p", "div", "section"], recursive=False)
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) > 30:  # Only meaningful paragraphs
            generic_data[0]["content_blocks"].append(text)
    
    # If no blocks found, try a different approach
    if not generic_data[0]["content_blocks"]:
        all_paragraphs = soup.find_all("p")
        for p in all_paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 30:
                generic_data[0]["content_blocks"].append(text)
    
    # Extract images
    images = main_container.find_all("img")
    for img in images:
        if img.get("src") and not img.get("src").endswith((".ico", ".svg")):
            generic_data[0]["images"].append(img["src"])
    
    return generic_data

# Streamlit UI
st.set_page_config(page_title="🌐 Universal Web Scraper", layout="centered")
st.title("🌐 Universal Web Scraper")

st.markdown("Scrape structured data from any website: e-commerce products, news articles, and more.")

url = st.text_input("Enter website URL", placeholder="https://example.com")

content_type = st.radio(
    "Content type (Auto will try to detect automatically)",
    ["auto", "product", "article", "generic"]
)

if st.button("Scrape Website"):
    if not url.startswith("http"):
        st.error("Please enter a valid URL starting with http or https.")
    else:
        try:
            with st.spinner("Scraping... Please wait"):
                html = get_dynamic_page(url)
                extracted_data = extract_content(html, content_type)

            if not extracted_data:
                st.warning("No relevant content was extracted. The site may use anti-bot techniques or custom JS.")
            else:
                st.success(f"✅ Found {len(extracted_data)} items.")
                
                # Display based on detected/selected content type
                if content_type == "product" or (content_type == "auto" and "price" in extracted_data[0]):
                    for i, item in enumerate(extracted_data):
                        st.subheader(f"🛍️ Product {i+1}")
                        st.text(f"Title: {item.get('title', 'N/A')}")
                        st.text(f"Brand: {item.get('brand', 'N/A')}")
                        st.text(f"Price: {item.get('price', 'N/A')}")
                        st.text(f"Quantity: {item.get('quantity', 'N/A')}")
                        if item.get('image_url'):
                            st.image(item['image_url'], width=150)
                        st.text(f"Description: {item.get('description', 'N/A')}")
                
                elif content_type == "article" or (content_type == "auto" and "author" in extracted_data[0]):
                    for i, item in enumerate(extracted_data):
                        st.subheader(f"📰 Article {i+1}")
                        st.text(f"Title: {item.get('title', 'N/A')}")
                        st.text(f"Author: {item.get('author', 'N/A')}")
                        st.text(f"Published: {item.get('published_date', 'N/A')}")
                        if item.get('image_url'):
                            st.image(item['image_url'], width=150)
                        st.text(f"Summary: {item.get('summary', 'N/A')}")
                        st.text(f"URL: {item.get('url', 'N/A')}")
                
                else:  # generic content
                    for i, item in enumerate(extracted_data):
                        st.subheader(f"📄 Content {i+1}")
                        st.text(f"Title: {item.get('title', 'N/A')}")
                        
                        if item.get('images'):
                            st.image(item['images'][0], width=150)
                            
                        st.text("Content:")
                        for j, block in enumerate(item.get('content_blocks', [])):
                            if j < 3:  # Limit displayed blocks
                                st.text(f"{block[:150]}..." if len(block) > 150 else block)
                            else:
                                st.text(f"+ {len(item['content_blocks']) - 3} more blocks")
                                break

            # Download JSON
            st.download_button(
                label="📥 Download All as JSON",
                data=json.dumps(extracted_data, indent=2),
                file_name="scraped_data.json",
                mime="application/json"
            )
        except Exception as e:
            st.error(f"❌ Failed to scrape: {e}")