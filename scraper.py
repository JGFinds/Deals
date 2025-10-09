#!/usr/bin/env python3
"""
scraper.py
Generates deals-feed.json by scraping a list of retail + secondary marketplace sources,
filtering by discount thresholds, and saving normalized JSON.

Notes:
 - This is designed for GitHub Actions execution.
 - Some site selectors are placeholders and may require tuning.
 - Optional: enable SELENIUM_MODE = True to use Selenium for JS-heavy sites.
"""

import os
import json
import time
import math
import random
from datetime import datetime
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

# Optional: selenium support for dynamic sites
SELENIUM_MODE = os.getenv("SELENIUM_MODE", "false").lower() == "true"

if SELENIUM_MODE:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

# ------------ Config ------------
OUTFILE = "deals-feed.json"
NOW_TS = int(time.time())

# Brand lists (for search queries / filtering)
BRANDS_SHOES = ["Nike","On Cloud","Hoka","Adidas","Vans","Converse","Doc Marten","Red Wing","Timberland","New Balance","Saucony","Asics","Salomon","Keen","Chacos"]
BRANDS_MENS = ["Levi's","Carhartt","Patagonia","The North Face","Orvis","Brooks Brothers","Simms","Smartwool"]
BRANDS_WOMENS = BRANDS_MENS + ["Miss Me","Rock Revival","True Religion"]

# Sites to scrape (example entry format)
RETAIL_SITES = [
    # Format { "name": "Nike", "type": "shoes", "url": "https://www.nike.com/w/sale-3yaepz" }
    {"name":"Nike","type":"shoes","url":"https://www.nike.com/w/mens-sale-3yaepznik1"},
    {"name":"Adidas","type":"shoes","url":"https://www.adidas.com/us/men-sale"},
    {"name":"Levis","type":"mens_clothing","url":"https://www.levi.com/US/en_US/men/jeans/501"},
    {"name":"Patagonia","type":"mens_clothing","url":"https://www.patagonia.com/shop/mens-sale"},
    {"name":"PatagoniaW","type":"womens_clothing","url":"https://www.patagonia.com/shop/womens-sale"},
    {"name":"TheNorthFace","type":"mens_clothing","url":"https://www.thenorthface.com/shop/mens-sale"},
    {"name":"Carhartt","type":"mens_clothing","url":"https://www.carhartt.com/womens-sale"},
    {"name":"Vans","type":"shoes","url":"https://www.vans.com/shop/sale"},
    # Add more brand store sale pages as desired...
]

# Secondary marketplace search base URLs (we will build a search URL)
MARKETPLACES = {
    "Poshmark": {"base":"https://poshmark.com/search?query="},
    "Grailed": {"base":"https://www.grailed.com/shop?query="},
    "eBay": {"base":"https://www.ebay.com/sch/i.html?_nkw="},
    "Mercari": {"base":"https://www.mercari.com/us/search/?keyword="},
    "Facebook": {"base":"https://www.facebook.com/marketplace/geo_search/?query="}  # FB may require Selenium + login in some cases
}

# Scrape settings
MIN_DISCOUNT_MAIN = 50   # include >=50% as main deals
MIN_DISCOUNT_HOT = 70    # include >=70% as hot deals

# User-Agent header
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DealsBot/1.0; +https://example.com)"
}

# ------------ Helpers ------------
def safe_float(s):
    try:
        return float(s.replace('$','').replace(',','').strip())
    except Exception:
        return None

def pct_from_prices(orig, price):
    try:
        if not orig or orig <= 0:
            return 0
        return int(round((orig - price) / orig * 100))
    except Exception:
        return 0

def norm_item(name, brand, price, original_price=None, image=None, link=None, categories=None, ts=None, item_type=None):
    return {
        "name": name,
        "brand": brand,
        "price": float(price) if price is not None else None,
        "original_price": float(original_price) if original_price is not None else None,
        "discount": pct_from_prices(original_price if original_price else price, price) if price is not None else 0,
        "image": image or "",
        "link": link or "",
        "timestamp": int(ts or NOW_TS),
        "categories": categories or [],
        "type": item_type or ""
    }

# ------------ Scrapers for simple retail pages (requests + BeautifulSoup) ------------
def scrape_generic_sale_page(site):
    """
    Attempt to scrape common sale page structures for price + name + original.
    This uses heuristics and will not be perfect for every site; customize selectors per-site for reliability.
    """
    url = site["url"]
    typ = site["type"]
    brand = site["name"]
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Heuristic: find product cards
        candidates = soup.select(".product, .product-card, .product-tile, .product-grid__item")
        if not candidates:
            # fallback: look for link tags that contain price
            candidates = soup.select("a")
        for c in candidates[:60]:
            try:
                # name heuristics
                name_tag = c.select_one(".product-title, .product-name, .title, h3, h2")
                name = name_tag.get_text(strip=True) if name_tag else (c.get("aria-label") or c.get("title") or "")
                # price heuristics
                price_tag = c.select_one(".product-price, .price, .sale-price, .price-current, .price-amount")
                price = None
                if price_tag:
                    price = safe_float(price_tag.get_text())
                else:
                    # look for $ in text
                    txt = c.get_text(" ", strip=True)
                    import re
                    m = re.search(r"\$\s?([0-9\.,]{2,})", txt)
                    if m:
                        price = safe_float(m.group(0))
                # original price / struckthrough
                orig_tag = c.select_one(".was, .original-price, .price-old, .price-previous, .product-price__strikethrough")
                orig = safe_float(orig_tag.get_text()) if orig_tag else None

                # image
                img_tag = c.select_one("img")
                img = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

                # link
                a = c.select_one("a")
                link = a.get("href") if a else url

                if price is None:
                    continue

                # compute discount
                discount = pct_from_prices(orig if orig else price, price)
                if discount >= MIN_DISCOUNT_MAIN:
                    item = norm_item(name=name or brand, brand=brand, price=price, original_price=orig, image=img, link=link, categories=[typ], ts=NOW_TS, item_type=typ)
                    items.append(item)
            except Exception:
                continue
    except Exception as e:
        print("Error scraping", url, e)
    return items

# ------------ Marketplace scrapers (simple search-based) ------------
def scrape_marketplace_search(market_name, query_terms: List[str], limit_per_brand=10, selenium_driver=None):
    """
    For each query term, build a search URL and attempt to parse results.
    This is best-effort; many marketplaces require more robust selectors or Selenium.
    """
    base = MARKETPLACES.get(market_name, {}).get("base")
    if not base:
        return []
    results = []
    for q in query_terms:
        url = base + requests.utils.requote_uri(q)
        try:
            if selenium_driver:
                selenium_driver.get(url)
                time.sleep(2 + random.random()*2)
                page_html = selenium_driver.page_source
                soup = BeautifulSoup(page_html, "html.parser")
            else:
                r = requests.get(url, headers=HEADERS, timeout=15)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")

            # marketplace-specific heuristics (eBay example)
            if market_name == "eBay":
                items = soup.select(".s-item")
                for it in items[:limit_per_brand]:
                    title = it.select_one(".s-item__title")
                    price_el = it.select_one(".s-item__price")
                    link_el = it.select_one(".s-item__link")
                    img_el = it.select_one(".s-item__image-img")
                    if not price_el or not title:
                        continue
                    price = safe_float(price_el.get_text())
                    if price is None:
                        continue
                    # We don't know original price for marketplace; treat discount as 0
                    item = norm_item(name=title.get_text(strip=True), brand=q, price=price, original_price=None, image=(img_el.get("src") if img_el else ""), link=(link_el.get("href") if link_el else url), categories=["Marketplace","Used"], ts=NOW_TS, item_type="shoes" if any(b.lower() in title.get_text(strip=True).lower() for b in BRANDS_SHOES) else "mens_clothing")
                    results.append(item)
            else:
                # Generic marketplace attempt: find price-like nodes
                entries = soup.select("article, .tile, .search-result, .searchResult, .item")
                for e in entries[:limit_per_brand]:
                    text = e.get_text(" ", strip=True)
                    import re
                    m = re.search(r"\$\s?([0-9\.,]{2,})", text)
                    if not m:
                        continue
                    price = safe_float(m.group(0))
                    title_tag = e.select_one("h2, h3, .title, .item-title, .search-result-title")
                    title = title_tag.get_text(strip=True) if title_tag else q
                    link_tag = e.select_one("a")
                    link = link_tag.get("href") if link_tag else url
                    img_tag = e.select_one("img")
                    img = img_tag.get("src") if img_tag else None
                    item = norm_item(name=title, brand=q, price=price, original_price=None, image=img, link=link, categories=["Marketplace"], ts=NOW_TS, item_type="shoes" if any(b.lower() in title.lower() for b in BRANDS_SHOES) else "mens_clothing")
                    results.append(item)
        except Exception as e:
            print("Marketplace scrape error", market_name, q, e)
            continue
    return results

# ------------ Selenium helper ------------
def init_selenium_driver():
    if not SELENIUM_MODE:
        return None
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1200")
    driver = webdriver.Chrome(options=opts)
    return driver

# ------------ Main flow ------------
def build_feed():
    feed = {"hot_deals": [], "shoes": [], "mens_clothing": [], "womens_clothing": [], "flash_sales": []}
    driver = None
    try:
        if SELENIUM_MODE:
            driver = init_selenium_driver()

        # Retail sites (requests + heuristics)
        for site in RETAIL_SITES:
            print("Scraping retail:", site["name"])
            items = scrape_generic_sale_page(site)
            for it in items:
                # categorize into hot vs main
                if it["discount"] >= MIN_DISCOUNT_HOT:
                    feed["hot_deals"].append(it)
                    feed["flash_sales"].append({"name":it["name"], "brand":it["brand"], "price":it["price"], "discount":it["discount"]})
                else:
                    feed[site["type"]].append(it)

        # Marketplace scrapes (for brand list)
        # Build query list: brands + common keywords
        queries = list(set(BRANDS_SHOES + BRANDS_MENS + BRANDS_WOMENS + ["Levi's 501","Y2K jeans","True Religion","Rock Revival","Miss Me"]))
        for market in MARKETPLACES.keys():
            print("Searching marketplace:", market)
            items = scrape_marketplace_search(market, queries, limit_per_brand=6, selenium_driver=driver)
            for it in items:
                # no discount info for marketplace by default
                # treat items priced well (heuristic): if price < 40% of average retail? (skip heuristic here)
                # just append to appropriate bucket
                if it["type"] == "womens_clothing":
                    feed["womens_clothing"].append(it)
                elif it["type"] == "mens_clothing":
                    feed["mens_clothing"].append(it)
                else:
                    feed["shoes"].append(it)

        # Final dedupe (by link/name)
        def dedupe_list(lst):
            seen = set()
            out = []
            for x in lst:
                key = (x.get("link") or "") + "|" + (x.get("name") or "")
                if key in seen:
                    continue
                seen.add(key)
                out.append(x)
            return out

        for k in list(feed.keys()):
            feed[k] = dedupe_list(feed[k])

        # Write file
        with open(OUTFILE, "w") as f:
            json.dump(feed, f, indent=2)
        print("Wrote", OUTFILE)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    build_feed()
