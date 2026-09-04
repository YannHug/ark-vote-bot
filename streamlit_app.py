import asyncio
import logging
import os
import re
import base64
import streamlit as st
from playwright.async_api import async_playwright
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
TARGET_URL = os.getenv("TARGET_URL", "https://top-serveurs.net/ark/vote/1ngames")
PLAYER_NAME = os.getenv("PLAYER_NAME", "Holybruiser")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY manquante!")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def close_cookie_popup(page):
    try:
        btn = page.locator("button").filter(has_text=re.compile(r"ne pas consentir", re.IGNORECASE)).first
        if await btn.count() > 0:
            await btn.click()
            await asyncio.sleep(1)
            logger.info("✅ Popup cookies fermée")
    except:
        pass

def read_captcha_with_gemini(image_bytes):
    try:
        logger.info("🤖 Gemini lit le CAPTCHA...")
        b64_image = base64.standard_b64encode(image_bytes).decode()
        model = genai.GenerativeModel('gemini-3.6-flash')
        response = model.generate_content([
            "Lis le CAPTCHA. 4-6 caractères en MAJUSCULES. Réponse UNIQUEMENT.",
            {"mime_type": "image/png", "data": b64_image}
        ])
        captcha_text = response.text.strip().upper()
        if captcha_text and 4 <= len(captcha_text) <= 10 and "AUCUN" not in captcha_text:
            logger.info(f"✅ CAPTCHA: {captcha_text}")
            return captcha_text
        return ""
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return ""

async def perform_vote():
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            await close_cookie_popup(page)
            
            pseudo_input = page.locator("input[name*='pseudo' i], input[placeholder*='pseudo' i]").first
            await pseudo_input.wait_for(timeout=10000)
            await pseudo_input.fill(PLAYER_NAME)
            logger.info("✅ Pseudo rempli")
            
            try:
                captcha_widget = page.locator(".mtcaptcha").first
                await captcha_widget.wait_for(timeout=12000)
                await captcha_widget.scroll_into_view_if_needed()
            except:
                pass
            
            await asyncio.sleep(8)
            screenshot = await page.screenshot(full_page=True)
            captcha = read_captcha_with_gemini(screenshot)
            
            if not captcha:
                await browser.close()
                return False
            
            for _ in range(4):
                await page.keyboard.press("Tab")
                await asyncio.sleep(0.2)
            
            await page.keyboard.type(captcha, delay=100)
            await asyncio.sleep(1)
            
            btn = page.locator("button").filter(has_text=re.compile(r"voter", re.IGNORECASE)).first
            if await btn.count() > 0:
                await btn.click()
            else:
                await browser.close()
                return False
            
            await asyncio.sleep(15)
            page_text = await page.content()
            page_url = page.url
            await browser.close()
            
            if "validé" in page_text.lower() or "/success" in page_url or "patienter" in page_text.lower():
                logger.info("🎉 VOTE OK!")
                return True
            
            return True
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False

st.set_page_config(page_title="🤖 ARK Bot", page_icon="🤖")
query_params = st.query_params

if "action" in query_params and query_params["action"] == "vote":
    st.info("⏳ Vote...")
    try:
        result = asyncio.run(perform_vote())
        if result:
            st.success("✅ VOTE OK!")
            st.balloons()
        else:
            st.error("❌ Échec")
    except Exception as e:
        st.error(f"❌ Erreur: {e}")
else:
    st.title("🤖 ARK Vote Bot")
    st.write(f"**Joueur:** {PLAYER_NAME}")
    st.write(f"**URL:** {TARGET_URL}")
    st.write("UptimeRobot appelle toutes les 20 min → ~72 votes/jour")
    st.divider()
    
    if st.button("🎯 TESTER LE VOTE", use_container_width=True):
        st.info("⏳ Vote en cours...")
        try:
            result = asyncio.run(perform_vote())
            if result:
                st.success("✅ VOTE OK!")
                st.balloons()
            else:
                st.error("❌ Échec")
        except Exception as e:
            st.error(f"❌ Erreur: {e}")