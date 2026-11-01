import sys
import subprocess
import re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from playwright.sync_api import sync_playwright

# Εγκατάσταση Chromium στο Streamlit Cloud
@st.cache_resource
def install_playwright_browser():
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

install_playwright_browser()

# Εξαγωγή συντεταγμένων από σύνδεσμο Google Maps
def extract_lat_lng(link: str):
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', link)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None

# Scraping
def scrape_places(search_query: str):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        url = f"https://www.google.com/maps/search/{search_query}"
        page.goto(url, timeout=60000)
        
        # Αποδοχή cookies
        try:
            page.click("button[aria-label='Αποδοχή όλων']", timeout=3000)
        except Exception:
            pass

        try:
            page.wait_for_selector("div[role='feed']", timeout=10000)
            feed = page.locator("div[role='feed']")
            
            for _ in range(3):
                feed.evaluate("el => el.scrollTop += 1000")
                page.wait_for_timeout(1000)

            items = page.locator("div[role='article']").all()

            for item in items[:15]:
                try:
                    title = item.locator("div.qBF1Pd").text_content() or "Άγνωστο"
                    
                    rating_text = "0.0"
                    rating_el = item.locator("span.MW4etd")
                    if rating_el.count() > 0:
                        rating_text = rating_el.text_content().replace(",", ".")
                    rating = float(rating_text) if rating_text else 0.0

                    link_el = item.locator("a.hf53P")
                    raw_link = link_el.get_attribute("href") if link_el.count() > 0 else ""
                    
                    # Διόρθωση συνδέσμου
                    full_link = ""
                    if raw_link:
                        full_link = raw_link if raw_link.startswith("http") else f"https://www.google.com{raw_link}"

                    lat, lng = extract_lat_lng(full_link)

                    results.append({
                        "Όνομα": title,
                        "Βαθμολογία": rating,
                        "Σύνδεσμος": full_link,
                        "lat": lat,
                        "lng": lng
                    })
                except Exception:
                    continue
        except Exception:
            pass

        browser.close()
    return results


# Streamlit UI
st.set_page_config(page_title="Google Maps Place Finder", layout="wide")
st.title("📍 Αναζήτηση Σημείων Ενδιαφέροντος μέσω Google Maps")

col_search1, col_search2 = st.columns([2, 1])

with col_search1:
    location_input = st.text_input("Περιοχή / Τοποθεσία:", "Άγιος Πρόδρομος Χαλκιδικής")

with col_search2:
    category_option = st.selectbox(
        "Κατηγορία αναζήτησης:",
        ["Εστιατόρια", "Μπαρ", "Καφέ", "Μουσεία", "Παραλίες", "Ξενοδοχεία", "Ελεύθερη αναζήτηση..."]
    )

if category_option == "Ελεύθερη αναζήτηση...":
    custom_category = st.text_input("Πληκτρολογήστε αυτό που ψάχνετε (π.χ. φαρμακεία, βενζινάδικα):", "")
    search_term = custom_category
else:
    search_term = category_option

sort_option = st.selectbox("Ταξινόμηση κατά:", ["Βαθμολογία (Φθίνουσα)", "Όνομα (Α-Ω)"])

if st.button("Αναζήτηση"):
    if not location_input.strip() or not search_term.strip():
        st.warning("Παρακαλώ συμπληρώστε τοποθεσία και όρο αναζήτησης.")
    else:
        full_query = f"{search_term} σε {location_input}"
        with st.spinner(f"Αναζήτηση για '{full_query}'..."):
            data = scrape_places(full_query)
            
        if not data:
            st.error("Δεν βρέθηκαν αποτελέσματα ή προέκυψε σφάλμα.")
        else:
            df = pd.DataFrame(data)
            
            if sort_option == "Βαθμολογία (Φθίνουσα)":
                df = df.sort_values(by="Βαθμολογία", ascending=False)
            elif sort_option == "Όνομα (Α-Ω)":
                df = df.sort_values(by="Όνομα", ascending=True)

            st.subheader(f"Αποτελέσματα: {full_query}")

            # Προβολή σε Χάρτη (αν υπάρχουν συντεταγμένες)
            df_coords = df.dropna(subset=["lat", "lng"])
            if not df_coords.empty:
                avg_lat = df_coords["lat"].mean()
                avg_lng = df_coords["lng"].mean()
                
                m = folium.Map(location=[avg_lat, avg_lng], zoom_start=13)
                
                for _, row in df_coords.iterrows():
                    popup_html = f"<b>{row['Όνομα']}</b><br>Βαθμολογία: ★ {row['Βαθμολογία']}<br><a href='{row['Σύνδεσμος']}' target='_blank'>Άνοιγμα στο Google Maps</a>"
                    folium.Marker(
                        location=[row["lat"], row["lng"]],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=row["Όνομα"]
                    ).add_to(m)
                
                st_folium(m, width=1000, height=400)

            # Λίστα Αποτελεσμάτων
            for _, row in df.iterrows():
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### {row['Όνομα']} — ★ {row['Βαθμολογία']}")
                    with c2:
                        if row["Σύνδεσμος"]:
                            st.markdown(f"[🔗 Προβολή στο Maps]({row['Σύνδεσμος']})")
                    st.divider()
