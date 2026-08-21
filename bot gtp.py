import argparse
import asyncio
import logging
import os
import re
import time
import base64
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser(description="🎮 Bot de vote ARK avec OpenAI Vision")
parser.add_argument("--url", type=str, default=os.getenv("TARGET_URL"), help="URL du vote")
parser.add_argument("--pseudo", type=str, default=os.getenv("PLAYER_NAME", "Holybruiser"), help="Pseudo")
parser.add_argument("--debug", action="store_true", help="Voir le navigateur")
args = parser.parse_args()

TARGET_URL = args.url
PLAYER_NAME = args.pseudo
HEADLESS_MODE = not args.debug

if not TARGET_URL:
    print("❌ Pas d'URL! Ajoute TARGET_URL dans .env")
    exit(1)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("❌ CLÉ API OPENAI MANQUANTE!")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

COOLDOWN_SUCCESS = 7200
COOLDOWN_CAPTCHA_ERROR = 120
COOLDOWN_NETWORK_ERROR = 5
SCREENSHOT_DIR = "screenshots"
LOG_FILE = "vote_bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

SELECTORS = {
    "pseudo": "input[name*='pseudo' i], input[name*='player' i], input[placeholder*='pseudo' i]",
}

async def close_cookie_popup(page: Page) -> None:
    """Ferme la popup de consentement cookies"""
    try:
        logger.info("🍪 Vérification de la popup cookies...")
        
        decline_button = page.locator("button, [role='button']").filter(
            has_text=re.compile(r"ne pas consentir|decline", re.IGNORECASE)
        ).first
        
        if await decline_button.count() > 0:
            logger.info("🍪 Popup cookies trouvée - Clic sur 'Ne pas consentir'...")
            await decline_button.click()
            await asyncio.sleep(1)
            logger.info("✅ Popup cookies fermée")
        else:
            logger.info("✅ Pas de popup cookies détectée")
            
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la fermeture des cookies: {e}")

def solve_captcha_with_openai(image_bytes: bytes) -> str:
    """Envoie la screenshot à OpenAI/ChatGPT pour lire le CAPTCHA"""
    try:
        logger.info("🤖 ChatGPT lit le CAPTCHA...")
        base64_image = base64.standard_b64encode(image_bytes).decode("utf-8")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Regarde cette screenshot de page web.

Tu dois TROUVER et LIRE le CAPTCHA (image avec texte).

Le CAPTCHA a probablement 4-6 caractères.

Réponds UNIQUEMENT avec les caractères visibles.
RIEN D'AUTRE.

Exemples:
- ABCD
- HG93F
- ABC12"""
                        }
                    ],
                }
            ],
        )
        
        clean_text = response.choices[0].message.content.text.strip().upper()
        
        if clean_text and len(clean_text) >= 4:
            logger.info(f"✅ CAPTCHA lu par ChatGPT: {clean_text}")
            return clean_text
        else:
            logger.warning(f"⚠️ Réponse invalide: '{clean_text}'")
            return ""
        
    except Exception as e:
        logger.error(f"❌ Erreur OpenAI: {e}")
        return ""

async def click_vote_button(page: Page) -> bool:
    """Clique sur le bouton VOTER"""
    logger.info("🔍 Recherche du bouton VOTER...")
    try:
        button = page.get_by_role("button", name=re.compile(r"voter", re.IGNORECASE)).first
        if await button.count() > 0:
            await button.click()
            logger.info("✅ Bouton VOTER cliqué")
            return True
    except:
        pass
    
    try:
        buttons = page.locator("button, input[type='submit']")
        count = await buttons.count()
        for i in range(count):
            btn = buttons.nth(i)
            txt = (await btn.inner_text()).upper()
            if "VOTER" in txt:
                await btn.click()
                logger.info("✅ Bouton VOTER trouvé et cliqué")
                return True
    except:
        pass
    
    logger.error("❌ Bouton VOTER non trouvé")
    return False

async def perform_vote(page: Page) -> tuple[bool, int]:
    """Effectue UN VOTE COMPLET"""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    try:
        logger.info(f"🌐 Navigation vers: {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        
        # Étape 0: Fermer la popup cookies
        await close_cookie_popup(page)
        
        # Étape 1: Remplir le pseudo
        logger.info(f"📝 Insertion du pseudo: {PLAYER_NAME}")
        pseudo_input = page.locator(SELECTORS["pseudo"]).first
        await pseudo_input.wait_for(state="visible", timeout=10000)
        await pseudo_input.click()
        await page.keyboard.press("Control+A")
        await pseudo_input.fill(PLAYER_NAME)
        logger.info("✅ Pseudo inséré")

        # Étape 2: Screenshot COMPLÈTE de la page
        logger.info("📸 Screenshot complète de la page...")
        await asyncio.sleep(1)
        page_screenshot = await page.screenshot(full_page=True)
        screenshot_path = f"{SCREENSHOT_DIR}/captcha_page.png"
        with open(screenshot_path, "wb") as f:
            f.write(page_screenshot)
        logger.info(f"📸 Screenshot sauvegardée: {screenshot_path}")
        
        # Étape 3: ChatGPT lit le CAPTCHA
        logger.info("🤖 Appel à OpenAI Vision...")
        captcha_text = solve_captcha_with_openai(page_screenshot)
        
        if not captcha_text:
            logger.error("❌ CAPTCHA non lisible par ChatGPT")
            return False, COOLDOWN_CAPTCHA_ERROR
        
        logger.info(f"✅ CAPTCHA lu: {captcha_text}")

        # Étape 4: Naviguer à l'input CAPTCHA avec Tab
        logger.info("⌨️ Navigation au CAPTCHA (4 x Tab)...")
        for i in range(4):
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3)
        logger.info("✅ Focus sur l'input CAPTCHA")

        # Étape 5: Saisir les lettres du CAPTCHA
        logger.info(f"📝 Saisie du CAPTCHA: {captcha_text}")
        await page.keyboard.type(captcha_text, delay=100)
        logger.info(f"✅ CAPTCHA saisi: {captcha_text}")

        # Étape 6: Cliquer sur VOTER
        logger.info("🖱️ Clic VOTER...")
        clicked = await click_vote_button(page)
        if not clicked:
            return False, COOLDOWN_NETWORK_ERROR

        # Étape 7: Attendre la validation du vote
        logger.info("⏳ Attente de la validation...")
        await asyncio.sleep(5)
        
        logger.info("✅ Vote envoyé au serveur")

        # Attendre la réponse du serveur
        logger.info("⏳ Attente de la réponse finale...")
        await asyncio.sleep(10)
        
        result_screenshot = await page.screenshot()
        with open(f"{SCREENSHOT_DIR}/result.png", "wb") as f:
            f.write(result_screenshot)
        
        # Vérifier le résultat
        page_text = await page.content()
        
        if "/success" in page.url or "validé" in page_text.lower():
            logger.info("🎉 VOTE RÉUSSI!")
            return True, COOLDOWN_SUCCESS

        if "patienter" in page_text.lower() or "déjà voté" in page_text.lower():
            logger.warning("⏰ Cooldown actif - vote probablement accepté")
            return False, COOLDOWN_SUCCESS

        logger.info("✅ Vote semble accepté (validation serveur)")
        return True, COOLDOWN_SUCCESS

    except PlaywrightTimeoutError as e:
        logger.error(f"⏱️ TIMEOUT: {e}")
        return False, COOLDOWN_NETWORK_ERROR
    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        return False, COOLDOWN_NETWORK_ERROR

async def main():
    """Boucle infinie de votes"""
    async with async_playwright() as p:
        logger.info("🚀 Lancement du bot")
        logger.info(f"   URL: {TARGET_URL}")
        logger.info(f"   Pseudo: {PLAYER_NAME}")
        logger.info(f"   API: OpenAI/ChatGPT (gpt-4o)")
        
        browser = await p.chromium.launch(headless=HEADLESS_MODE)
        context = await browser.new_context(viewport={"width": 1366, "height": 768})
        page = await context.new_page()

        cycle = 1
        while True:
            logger.info(f"\n{'='*60}")
            logger.info(f"CYCLE {cycle} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            success, wait_time = await perform_vote(page)
            
            logger.info(f"Résultat: {'✅ SUCCÈS' if success else '❌ ÉCHEC'}")
            logger.info(f"Attente: {wait_time // 60}m {wait_time % 60}s")
            
            for remaining in range(wait_time, 0, -1):
                mins, secs = divmod(remaining, 60)
                print(f"\r⏳ Prochain vote: {mins:02d}m {secs:02d}s", end="", flush=True)
                await asyncio.sleep(1)
            print()
            
            cycle += 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⛔ Arrêt")
        exit(0)