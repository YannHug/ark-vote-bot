import asyncio
import logging
import os
import re
import base64
import streamlit as st
from playwright.async_api import async_playwright
import google.generativeai as genai

# CONFIG
TARGET_URL = os.getenv("TARGET_URL", "https://top-serveurs.net/ark/vote/1ngames")
PLAYER_NAME = os.getenv("PLAYER_NAME", "Holybruiser")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY manquante!")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FONCTIONS
async def close_cookie_popup(page):
    try:
        btn = page.locator("button").filter(has_text=re.compile(r"ne pas consentir", re.IGNORECASE)).first
        if await btn.count() > 0:
            await btn.click()
            await asyncio.sleep(1)
    except:
        pass

def read_captcha_with_gemini(image_bytes):
    try:
        b64_image = base64.standard_b64encode(image_bytes).decode()
        model = genai.GenerativeModel('gemini-3.6-flash')
        response = model.generate_content([
            "Lis CAPTCHA 4-6 chars MAJUSCULES uniquement",
            {"mime_type": "image/png", "data": b64_image}
        ])
        captcha = response.text.strip().upper()
        if captcha and 4 <= len(captcha) <= 10:
            return captcha
        return ""
    except:
        return ""

async def perform_vote():
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True)
            pg = await b.new_page()
            await pg.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            await close_cookie_popup(pg)
            
            inp = pg.locator("input[name*='pseudo' i]").first
            await inp.wait_for(timeout=10000)
            await inp.fill(PLAYER_NAME)
            
            try:
                w = pg.locator(".mtcaptcha").first
                await w.wait_for(timeout=10000)
            except:
                pass
            
            await asyncio.sleep(8)
            ss = await pg.screenshot(full_page=True)
            cap = read_captcha_with_gemini(ss)
            
            if not cap:
                await b.close()
                return False
            
            for _ in range(4):
                await pg.keyboard.press("Tab")
                await asyncio.sleep(0.1)
            
            await pg.keyboard.type(cap, delay=50)
            await asyncio.sleep(1)
            
            btn = pg.locator("button").filter(has_text=re.compile(r"voter", re.IGNORECASE)).first
            if await btn.count() > 0:
                await btn.click()
            else:
                await b.close()
                return False
            
            await asyncio.sleep(15)
            await b.close()
            return True
    except Exception as e:
        logger.error(f"Erreur: {e}")
        return False

# UI
st.set_page_config(page_title="ARK Bot", page_icon="🤖")
params = st.query_params

if params.get("action") == "vote":
    st.info("Vote...")
    result = asyncio.run(perform_vote())
    if result:
        st.success("✅ VOTE OK")
    else:
        st.error("❌ FAILED")
else:
    st.title("🤖 ARK Vote Bot")
    st.write(f"Player: {PLAYER_NAME}")
    if st.button("TEST VOTE"):
        result = asyncio.run(perform_vote())
        st.success("✅ OK") if result else st.error("❌ FAIL")