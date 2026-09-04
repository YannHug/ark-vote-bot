import asyncio
import logging
import os
import re
import subprocess
import sys

import streamlit as st
from playwright.async_api import async_playwright
from google import genai
from google.genai import types

# ============================================================================
# CONFIGURATION
# ============================================================================

TARGET_URL = os.getenv("TARGET_URL", "https://top-serveurs.net/ark/vote/1ngames")
PLAYER_NAME = os.getenv("PLAYER_NAME", "Holybruiser")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"  # modèle multimodal stable pour lire le CAPTCHA

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY manquante dans les secrets Streamlit !")
    st.stop()

client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# INSTALLATION DE CHROMIUM (une seule fois par conteneur)
# ============================================================================


@st.cache_resource
def install_playwright_browsers():
    """Télécharge le binaire Chromium requis par Playwright.
    Les dépendances système (libs) doivent être listées dans packages.txt
    (voir fichier fourni), car elles nécessitent les droits root disponibles
    uniquement au moment du build."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("✅ Chromium installé\n%s", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("❌ Échec installation Chromium: %s", e.stderr)
        return False


# ============================================================================
# FONCTIONS
# ============================================================================


async def close_cookie_popup(page):
    try:
        btn = page.locator("button").filter(
            has_text=re.compile(r"ne pas consentir", re.IGNORECASE)
        ).first
        if await btn.count() > 0:
            await btn.click()
            await asyncio.sleep(1)
    except Exception:
        pass


def read_captcha_with_gemini(image_bytes: bytes) -> str:
    """Envoie l'image à Gemini pour lire le CAPTCHA (nouveau SDK google-genai)."""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                "Lis le CAPTCHA dans cette image. C'est du texte avec des chiffres et "
                "des lettres (4-6 caractères). Réponds UNIQUEMENT avec les caractères "
                "visibles, en MAJUSCULES, sans aucun autre mot. Exemple: AB12C3",
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            ],
        )
        captcha = (response.text or "").strip().upper()
        if captcha and 4 <= len(captcha) <= 10:
            logger.info(f"✅ CAPTCHA lu: {captcha}")
            return captcha
        logger.warning(f"⚠️ CAPTCHA non lisible: '{captcha}'")
        return ""
    except Exception as e:
        logger.error(f"❌ Erreur Gemini: {e}")
        return ""


async def perform_vote() -> bool:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            logger.info("🌐 Navigation vers le site...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

            await close_cookie_popup(page)

            logger.info("📝 Remplissage du pseudo...")
            pseudo_input = page.locator("input[name*='pseudo' i]").first
            await pseudo_input.wait_for(timeout=10000)
            await pseudo_input.fill(PLAYER_NAME)

            try:
                widget = page.locator(".mtcaptcha").first
                await widget.wait_for(timeout=10000)
                await widget.scroll_into_view_if_needed()
            except Exception:
                logger.warning("⚠️ Widget CAPTCHA pas détecté")

            logger.info("⏳ Attente de la génération de l'image CAPTCHA...")
            await asyncio.sleep(8)

            screenshot = await page.screenshot(full_page=True)
            captcha = read_captcha_with_gemini(screenshot)

            if not captcha:
                await browser.close()
                return False

            logger.info("⌨️ Navigation au champ CAPTCHA...")
            for _ in range(4):
                await page.keyboard.press("Tab")
                await asyncio.sleep(0.2)

            await page.keyboard.type(captcha, delay=100)
            await asyncio.sleep(1)

            logger.info("🖱️ Clic du bouton VOTER...")
            vote_btn = page.locator("button").filter(
                has_text=re.compile(r"voter", re.IGNORECASE)
            ).first

            if await vote_btn.count() > 0:
                await vote_btn.click()
            else:
                logger.error("❌ Bouton VOTER non trouvé")
                await browser.close()
                return False

            logger.info("⏳ Attente de la validation serveur...")
            await asyncio.sleep(15)

            await browser.close()
            return True

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False


# ============================================================================
# UI STREAMLIT
# ============================================================================

st.set_page_config(page_title="ARK Bot", page_icon="🤖")

if not install_playwright_browsers():
    st.error(
        "❌ Impossible d'installer Chromium. Vérifie que packages.txt est bien "
        "présent à la racine du repo et regarde les logs de build."
    )
    st.stop()

params = st.query_params  # nécessite streamlit >= 1.30.0 (voir requirements.txt)

if params.get("action") == "vote":
    st.info("Vote en cours...")
    result = asyncio.run(perform_vote())
    st.success("✅ VOTE OK") if result else st.error("❌ FAILED")
else:
    st.title("🤖 ARK Vote Bot")
    st.write(f"Player: {PLAYER_NAME}")
    if st.button("TEST VOTE"):
        result = asyncio.run(perform_vote())
        st.success("✅ OK") if result else st.error("❌ FAIL")