# 🎮 ARK Server Vote Bot - Automatiseur de Votes

Automatise les votes sur **top-serveurs.net** pour booster le serveur ARK **"1nGames"**.

![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Prérequis

- **Python 3.9+** ([télécharger](https://www.python.org/downloads/))
- **Tesseract OCR** (dépendance système)
- **pip** (inclus avec Python)

---

## ⚡ Installation RAPIDE (3 étapes)

### 1️⃣ Cloner/télécharger le projet

```bash
# Via Git
git clone https://github.com/...ark-vote-bot.git
cd ark-vote-bot

# OU télécharge et décompresse le ZIP
```

### 2️⃣ Installer Tesseract OCR

**🪟 WINDOWS:**
1. Télécharge: https://github.com/UB-Mannheim/tesseract/wiki
2. Lance le `.exe`
3. Accepte les chemins par défaut
4. ✅ Tesseract est installé!

**🍎 macOS:**
```bash
brew install tesseract
```

**🐧 LINUX (Debian/Ubuntu):**
```bash
sudo apt-get install tesseract-ocr
```

### 3️⃣ Installer les dépendances Python

```bash
# Installer les packages Python
pip install -r requirements.txt

# Installer le navigateur Chromium pour Playwright
playwright install chromium
```

### 4️⃣ Configurer le `.env`

```bash
# Copier le fichier exemple
cp .env.example .env

# Éditer .env avec tes paramètres
# (optionnel: personnalise PLAYER_NAME si tu veux)
```

✅ **C'est prêt!**

---

## 🚀 Utilisation

### Mode normal (sans fenêtre, arrière-plan)

```bash
python bot.py --headless
```

**Résultat:**
- Vote automatiquement toutes les 2 heures
- Affiche les logs dans le terminal
- Sauvegarde dans `vote_bot.log`

### Mode DEBUG (voir le navigateur en action)

```bash
python bot.py --debug
```

**Résultat:**
- Ouvre une fenêtre Chrome
- Tu vois chaque action
- Parfait pour troubleshoot

### Tester les sélecteurs (si ça ne marche pas)

```bash
python bot.py --test-selectors --debug
```

**Résultat:**
- Valide que les sélecteurs existent
- Affiche ✅ ou ❌ pour chaque élément
- Utile si top-serveurs.net a changé

### Personnaliser (URL ou pseudo)

```bash
python bot.py --url https://... --pseudo MonPseudo --debug
```

---

## 📊 Logs & Monitoring

### Voir les logs en direct

```bash
# Option 1: Lire le fichier
cat vote_bot.log

# Option 2: Suivi en continu (live)
tail -f vote_bot.log

# Option 3: Chercher un pattern
grep "VOTE" vote_bot.log
```

### Historique des votes réussis

```bash
grep "🎉 VOTE RÉUSSI" vote_bot.log
```

### Voir toutes les erreurs

```bash
grep "❌" vote_bot.log
```

---

## 📁 Structure du projet

```
ark-vote-bot/
├── bot.py                    # ← Le script principal
├── requirements.txt          # Dépendances Python
├── .env.example              # Exemple de config
├── .env                      # Configuration (à créer)
├── .gitignore                # Fichiers à ignorer
├── README.md                 # Cette doc
├── screenshots/              # Captures (créé auto)
│   ├── 01_page_load.png      # Page d'accueil
│   ├── 02_captcha.png        # CAPTCHA lu
│   ├── 03_success.png        # Vote réussi
│   ├── 04_cooldown.png       # Cooldown détecté
│   └── 05_error_*.png        # Erreurs
└── vote_bot.log              # Logs (créé auto)
```

---

## 🆘 Troubleshooting

### ❌ "pytesseract.TesseractNotFoundError"

**Cause:** Tesseract n'est pas installé

**Solution:**
Voir section "Installer Tesseract OCR" ci-dessus

---

### ❌ "ModuleNotFoundError: No module named 'playwright'"

**Cause:** Les dépendances ne sont pas installées

**Solution:**
```bash
pip install -r requirements.txt
playwright install chromium
```

---

### ❌ "Impossible de trouver le bouton VOTER"

**Cause:** Les sélecteurs CSS ne correspondent plus (le site a changé)

**Solution:**
```bash
# 1. Lance en mode test
python bot.py --test-selectors --debug

# 2. Ouvre l'inspecteur (F12) dans Chrome
# 3. Cherche les éléments qui ne sont pas trouvés
# 4. Mets à jour les SELECTORS dans bot.py

# Exemple:
# Avant: "input[name*='pseudo' i]"
# Après: "input#pseudo" (si tu as trouvé un id)
```

---

### ❌ Le CAPTCHA n'est pas reconnu

**Cause:** OCR faible (parfois normal, le CAPTCHA est difficile)

**Solution:**
1. Regarde l'image dans `screenshots/02_captcha.png`
2. C'est peu lisible? → Tesseract ne peut pas le lire (limitation)
3. Le bot réessayera après le cooldown

---

### ❌ Le script crash après quelques votes

**Cause:** Problème réseau / serveur

**Solution:**
Le bot redémarre automatiquement après le cooldown. C'est normal!

---

## 🎯 Cas d'usage

### 👤 Votant unique

```bash
# Tu veux voter pour UN serveur avec TON pseudo
TARGET_URL=https://top-serveurs.net/ark/vote/1ngames
PLAYER_NAME=MonPseudo
python bot.py --headless
```

### 🖥️ Serveur de jeu

```bash
# Tu veux que le script tourne H24 sur un serveur VPS
python bot.py --headless > bot.log 2>&1 &  # Lance en arrière-plan
# ou avec screen/tmux pour plus de contrôle
```

### 🧪 Development/Test

```bash
# Tu développes et tu veux voir ce qui se passe
python bot.py --test-selectors --debug
# ou
python bot.py --debug  # Voir un cycle complet
```

---

## 📝 Configuration avancée

### Personnaliser les cooldowns

Édite `bot.py` et change ces valeurs:
```python
COOLDOWN_SUCCESS = 7200          # Changé à 3600 = 1h
COOLDOWN_CAPTCHA_ERROR = 120     # Changé à 300 = 5 min
COOLDOWN_NETWORK_ERROR = 5       # Changé à 10 = 10 sec
```

### Changer l'User-Agent

Édite la ligne dans `bot.py`:
```python
user_agent="Mozilla/5.0..."  # Remplace par un autre UA
```

### Ajouter une Discord Webhook (notifications)

Viens bientôt! 🚧

---

## 📜 License

MIT - Libre d'utilisation

---

## 🤝 Contribution

Des bugs? Des idées? Ouvre une issue!

---

## ⚠️ Disclaimer

**Ce script:**
- ✅ Automatise les votes (accepté par top-serveurs.net)
- ✅ Respecte les cooldowns imposés
- ✅ Ne fait pas de spam ou de force brute

**Utilise-le responsablement!**

---

## 📞 Support

Si ça ne marche pas:
1. Regarde les logs: `cat vote_bot.log`
2. Lance en `--debug` pour voir le navigateur
3. Lance `--test-selectors` pour valider les éléments
4. Ouvre une issue sur GitHub

---

**Made with ❤️ for ARK Players**