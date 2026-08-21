import asyncio
import logging
import os
import re
import base64
from playwright.async_api import async_playwright
import google.generativeai as genai
from dotenv import load_dotenv

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()
TARGET_URL = os.getenv("TARGET_URL", "https://top-serveurs.net/ark/vote/1ngames")
PLAYER_NAME = os.getenv("PLAYER_NAME", "Holybruiser")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY manquante dans .env!")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# FONCTIONS
# ============================================================================


async def close_cookie_popup(page):
    """Ferme la popup de consentement cookies"""
    try:
        btn = (
            page.locator("button")
            .filter(has_text=re.compile(r"ne pas consentir", re.IGNORECASE))
            .first
        )
        if await btn.count() > 0:
            await btn.click()
            await asyncio.sleep(1)
            logger.info("✅ Popup cookies fermée")
    except:
        pass


def read_captcha_with_gemini(image_bytes):
    """Envoie l'image à Gemini pour lire le CAPTCHA"""
    try:
        logger.info("🤖 Gemini lit le CAPTCHA...")
        b64_image = base64.standard_b64encode(image_bytes).decode()

        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(
            [
                "Lis le CAPTCHA dans cette image. C'est du texte avec des chiffres et des lettres (4-6 caractères). Réponds UNIQUEMENT avec les caractères visibles en MAJUSCULES. Exemple: AB12C3 ou 3DMWb",
                {"mime_type": "image/png", "data": b64_image},
            ]
        )

        captcha_text = response.text.strip().upper()

        # Vérifier que ce n'est pas un message d'erreur
        if (
            captcha_text
            and len(captcha_text) >= 4
            and len(captcha_text) <= 10
            and "AUCUN" not in captcha_text
            and "VIDE" not in captcha_text
            and "BLANC" not in captcha_text
        ):
            logger.info(f"✅ CAPTCHA lu: {captcha_text}")
            return captcha_text
        else:
            logger.warning(f"⚠️ CAPTCHA non lisible: '{captcha_text}'")
            return ""
    except Exception as e:
        logger.error(f"❌ Erreur Gemini: {e}")
        return ""


async def perform_vote(page):
    """Effectue UN vote complet"""
    try:
        logger.info(f"🌐 Navigation vers le site...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        # Fermer les cookies
        await close_cookie_popup(page)

        # Remplir le pseudo
        logger.info(f"📝 Remplissage du pseudo...")
        pseudo_input = page.locator(
            "input[name*='pseudo' i], input[placeholder*='pseudo' i]"
        ).first
        await pseudo_input.wait_for(timeout=10000)
        await pseudo_input.fill(PLAYER_NAME)
        logger.info("✅ Pseudo rempli")

        # Attendre et scroller vers le CAPTCHA
        logger.info("⏳ Attente du CAPTCHA...")
        try:
            captcha_widget = page.locator(".mtcaptcha").first
            await captcha_widget.wait_for(timeout=12000)
            logger.info("✅ Widget CAPTCHA détecté")

            # Scroller vers le CAPTCHA pour s'assurer qu'il est visible
            await captcha_widget.scroll_into_view_if_needed()
            logger.info("✅ CAPTCHA visible à l'écran")

        except Exception as e:
            logger.warning(f"⚠️ Widget CAPTCHA pas détecté: {e}")

        # TRÈS IMPORTANT: Attendre que l'image du CAPTCHA se génère
        # Le widget se charge rapidement mais l'image prend du temps
        logger.info("⏳ Attente de la génération de l'image CAPTCHA (8 secondes)...")
        await asyncio.sleep(8)

        # Prendre la screenshot
        logger.info("📸 Capture d'écran...")
        screenshot = await page.screenshot(full_page=True)

        # Lire le CAPTCHA avec Gemini
        captcha = read_captcha_with_gemini(screenshot)
        if not captcha:
            logger.error("❌ CAPTCHA non lisible, abandon")
            return False, 120

        # Naviguer au champ CAPTCHA et le remplir
        logger.info("⌨️ Navigation au champ CAPTCHA (4 x Tab)...")
        for _ in range(4):
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.2)

        logger.info(f"📝 Saisie du CAPTCHA: {captcha}")
        await page.keyboard.type(captcha, delay=100)
        logger.info(f"✅ CAPTCHA saisi")

        # Attendre un peu avant de cliquer
        await asyncio.sleep(1)

        # Cliquer le bouton VOTER
        logger.info("🖱️ Clic du bouton VOTER...")
        btn = (
            page.locator("button")
            .filter(has_text=re.compile(r"voter", re.IGNORECASE))
            .first
        )

        if await btn.count() > 0:
            await btn.click()
            logger.info("✅ Bouton VOTER cliqué")
        else:
            logger.error("❌ Bouton VOTER non trouvé")
            return False, 120

        # Attendre la réponse du serveur
        logger.info("⏳ Attente de la validation du serveur (15 secondes)...")
        await asyncio.sleep(15)

        # Vérifier le résultat
        page_text = await page.content()
        page_url = page.url

        if "validé" in page_text.lower() or "/success" in page_url:
            logger.info("🎉 VOTE RÉUSSI!")
            return True, 7200

        if "patienter" in page_text.lower() or "déjà voté" in page_text.lower():
            logger.info("⏰ Vote accepté (cooldown actif)")
            return True, 7200

        logger.info("✅ Vote envoyé (validation en cours)")
        return True, 7200

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False, 120


# ============================================================================
# BOUCLE PRINCIPALE
# ============================================================================


async def main():
    """Boucle infinie de votes"""
    async with async_playwright() as playwright:
        logger.info("")
        logger.info("🚀 ═══════════════════════════════════════════")
        logger.info("🚀 DÉMARRAGE DU BOT ARK")
        logger.info("🚀 ═══════════════════════════════════════════")
        logger.info(f"   Joueur: {PLAYER_NAME}")
        logger.info(f"   URL: {TARGET_URL}")
        logger.info(f"   Gemini: ✅ Connecté")
        logger.info("🚀 ═══════════════════════════════════════════")
        logger.info("")

        # Lancer Chromium VISIBLE (headless=False)
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()

        cycle = 1
        while True:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"CYCLE {cycle}")
            logger.info(f"{'=' * 60}")

            success, wait_seconds = await perform_vote(page)

            logger.info(f"")
            logger.info(f"Résultat: {'✅ SUCCÈS' if success else '❌ ÉCHEC'}")
            logger.info(f"Attente: {wait_seconds // 60}m {wait_seconds % 60}s")
            logger.info(f"")

            # Countdown avec affichage
            for remaining in range(wait_seconds, 0, -1):
                m, s = divmod(remaining, 60)
                print(f"\r⏳ Prochain vote: {m:02d}m {s:02d}s", end="", flush=True)
                await asyncio.sleep(1)
            print()

            cycle += 1


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⛔ Bot arrêté par l'utilisateur")
        exit(0)
