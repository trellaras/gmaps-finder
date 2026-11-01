import sys
import subprocess
import os
import pandas as pd
import streamlit as st
from playwright.sync_api import sync_playwright

# Αυτόματη εγκατάσταση του Chromium στο περιβάλλον του Streamlit Cloud
@st.cache_resource
def install_playwright_browser():
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

install_playwright_browser()

# Λογική Scraping
def scrape_restaurants(location: str):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        query = f"εστιατόρια σε {location}"
        url = f"https://www.google.com/maps/search/{query}"
        page.goto(url, timeout=60000)
        
        # Αποδοχή cookies
        try:
            page.click("button[aria-label='Αποδοχή όλων']", timeout=3000)
        except Exception:
            pass

        try:
            page.wait_for_selector("div[role='feed']", timeout=10000)
            feed = page.locator("div[role='feed']")
            
            # Scrolling για φόρτωση
            for _ in range(3):
                feed.evaluate("el => el.scrollTop += 1000")
                page.wait_for_timeout(1000)

            items = page.locator("div[role='article']").all()

            for item in items[:10]:
                try:
                    title = item.locator("div.qBF1Pd").text_content() or "Άγνωστο"
                    
                    rating_text = "0.0"
                    rating_el = item.locator("span.MW4etd")
                    if rating_el.count() > 0:
                        rating_text = rating_el.text_content().replace(",", ".")
                    
                    rating = float(rating_text) if rating_text else 0.0

                    link_el = item.locator("a.hf53P")
                    link = link_el.get_attribute("href") if link_el.count() > 0 else ""

                    results.append({
                        "Όνομα": title,
                        "Βαθμολογία": rating,
                        "Σύνδεσμος": link
                    })
                except Exception:
                    continue
        except Exception:
            pass

        browser.close()
    return results


# Streamlit UI
st.set_page_config(page_title="Google Maps Restaurant Finder", layout="wide")
st.title("📍 Αναζήτηση Εστιατορίων μέσω Google Maps")

location = st.text_input("Περιοχή (π.χ. Σύνταγμα, Αθήνα):", "")

col1, col2 = st.columns([1, 2])
with col1:
    sort_option = st.selectbox("Ταξινόμηση κατά:", ["Βαθμολογία (Φθίνουσα)", "Όνομα (Α-Ω)"])

if st.button("Αναζήτηση"):
    if not location.strip():
        st.warning("Παρακαλώ εισάγετε περιοχή.")
    else:
        with st.spinner("Συλλογή δεδομένων από το Google Maps..."):
            data = scrape_restaurants(location)
            
        if not data:
            st.error("Δεν βρέθηκαν αποτελέσματα ή προέκυψε σφάλμα κατά τη συλλογή.")
        else:
            df = pd.DataFrame(data)
            
            if sort_option == "Βαθμολογία (Φθίνουσα)":
                df = df.sort_values(by="Βαθμολογία", ascending=False)
            elif sort_option == "Όνομα (Α-Ω)":
                df = df.sort_values(by="Όνομα", ascending=True)

            st.subheader(f"Αποτελέσματα για: {location}")
            
            for _, row in df.iterrows():
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### {row['Όνομα']} — ★ {row['Βαθμολογία']}")
                    with c2:
                        if row["Σύνδεσμος"]:
                            st.link_button("Προβολή στο Maps", row["Σύνδεσμος"])
                    st.divider()