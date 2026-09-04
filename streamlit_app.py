import asyncio
import logging
import os
import re
import shutil

import streamlit as st
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from google import genai
from google.genai import types

# ============================================================================
# CONFIGURATION
# ============================================================================

TARGET_URL = os.getenv("TARGET_URL", "https://top-serveurs.net/ark/vote/1ngames")
PLAYER_NAME = os.getenv("PLAYER_NAME", "Holybruiser")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.6-flash"  # modèle multimodal actuel (confirmé par l'API Google)

# Proxy maison (via Tailscale Funnel) pour sortir par une IP résidentielle
PROXY_SERVER = os.getenv("PROXY_SERVER")  # ex: https://desktop-hle4ud6.tailccd8fe.ts.net
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY manquante dans les secrets Streamlit !")
    st.stop()

client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# LOCALISATION DU CHROMIUM SYSTÈME (installé via apt / packages.txt)
# ============================================================================


@st.cache_resource
def find_chromium_binary():
    """Le binaire Chromium est installé par apt (voir packages.txt) plutôt que
    téléchargé par Playwright, pour éviter les conflits de dépendances
    système. On le localise une seule fois par conteneur."""
    candidates = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            logger.info(f"✅ Chromium trouvé: {path}")
            return path
    logger.error("❌ Aucun binaire Chromium trouvé sur le système")
    return None


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


async def perform_vote(chromium_path: str) -> bool:
    try:
        async with async_playwright() as p:
            launch_kwargs = {
                "executable_path": chromium_path,
                "headless": True,
                "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            }
            if PROXY_SERVER:
                launch_kwargs["proxy"] = {
                    "server": PROXY_SERVER,
                    "username": PROXY_USERNAME,
                    "password": PROXY_PASSWORD,
                }
                logger.info(f"🌍 Utilisation du proxy maison: {PROXY_SERVER}")
            else:
                logger.warning("⚠️ Aucun proxy configuré — connexion directe depuis Streamlit Cloud")

            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page()

            logger.info("🌐 Navigation vers le site...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

            await close_cookie_popup(page)

            logger.info("📝 Remplissage du pseudo...")
            pseudo_input = page.locator(
                "input[name='playername'], input[placeholder*='seudo' i]"
            ).first
            await pseudo_input.wait_for(timeout=15000)
            await pseudo_input.fill(PLAYER_NAME)

            logger.info("🧩 Attente du widget CAPTCHA (iframe MTCaptcha)...")
            captcha_iframe_el = page.locator("#mtcaptcha-iframe-1, iframe[title='MTCaptcha']").first
            await captcha_iframe_el.wait_for(state="visible", timeout=20000)
            await asyncio.sleep(5)  # laisser l'image du CAPTCHA finir de se dessiner (latence proxy)

            logger.info("📸 Capture de l'image du CAPTCHA...")
            screenshot = await captcha_iframe_el.screenshot()
            captcha = read_captcha_with_gemini(screenshot)

            if not captcha:
                logger.info("🔁 Nouvelle tentative de capture après un délai supplémentaire...")
                await asyncio.sleep(4)
                screenshot = await captcha_iframe_el.screenshot()
                captcha = read_captcha_with_gemini(screenshot)

            if not captcha:
                await browser.close()
                return False

            logger.info(f"⌨️ Saisie du CAPTCHA dans le champ dédié: {captcha}")
            captcha_input = page.frame_locator(
                "#mtcaptcha-iframe-1, iframe[title='MTCaptcha']"
            ).locator("input[type='text']").first
            await captcha_input.click()
            await captcha_input.press_sequentially(captcha, delay=120)
            await captcha_input.press("Tab")  # déclenche la validation côté MTCaptcha

            logger.info("⏳ Attente de l'activation du bouton VOTER (validation CAPTCHA)...")
            try:
                await page.wait_for_function(
                    """() => {
                        const b = document.querySelector('#btnSubmitVote');
                        return b && !b.disabled;
                    }""",
                    timeout=15000,
                )
                logger.info("✅ CAPTCHA validé, bouton VOTER activé")
            except PlaywrightTimeoutError:
                logger.warning("⚠️ Bouton VOTER toujours désactivé après le CAPTCHA")
                await browser.close()
                return False

            logger.info("🖱️ Clic du bouton VOTER...")
            vote_btn = page.locator("#btnSubmitVote, button[type='submit']").filter(
                has_text=re.compile(r"voter", re.IGNORECASE)
            ).first

            if await vote_btn.count() > 0:
                await vote_btn.click()
            else:
                logger.error("❌ Bouton VOTER non trouvé")
                await browser.close()
                return False

            logger.info("⏳ Attente de la validation serveur...")
            await asyncio.sleep(8)

            final_url = page.url
            final_text = (await page.content()).lower()
            logger.info(f"🔎 URL finale: {final_url}")

            success_markers = ["merci d'avoir voté", "vote enregistré", "vote pris en compte", "/success"]
            cooldown_markers = ["déjà voté", "patienter", "revenez dans", "prochain vote"]

            if any(m in final_text for m in success_markers) or "/success" in final_url:
                logger.info("🎉 Le site confirme le vote (message de succès détecté)")
                await browser.close()
                return True

            if any(m in final_text for m in cooldown_markers):
                logger.info("🎉 Le site indique un cooldown de vote actif : la tentative a bien été comptabilisée")
                await browser.close()
                return True

            logger.warning(
                "⚠️ Aucun message de confirmation NI de cooldown détecté après le clic — "
                "statut réellement incertain (le vote a peut-être été silencieusement rejeté)"
            )
            await browser.close()
            return False

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False


# ============================================================================
# UI STREAMLIT
# ============================================================================

st.set_page_config(page_title="ARK Bot", page_icon="🤖")

CHROMIUM_PATH = find_chromium_binary()

if not CHROMIUM_PATH:
    st.error(
        "❌ Chromium introuvable sur le système. Vérifie que packages.txt "
        "(contenant juste 'chromium') est bien présent à la racine du repo, "
        "et regarde les logs de build pour une erreur d'installation apt."
    )
    st.stop()

params = st.query_params  # nécessite streamlit >= 1.30.0 (voir requirements.txt)

if params.get("action") == "vote":
    st.info("Vote en cours...")
    result = asyncio.run(perform_vote(CHROMIUM_PATH))
    if result:
        st.success("✅ VOTE OK")
    else:
        st.error("❌ FAILED")
else:
    st.title("🤖 ARK Vote Bot")
    st.write(f"Player: {PLAYER_NAME}")
    if st.button("TEST VOTE"):
        result = asyncio.run(perform_vote(CHROMIUM_PATH))
        if result:
            st.success("✅ OK")
        else:
            st.error("❌ FAIL")
