# ⚡ CyCode - Guide d'Installation PowerShell

Bienvenue dans le guide de déploiement de CyCode. Ce document contient les commandes nécessaires pour installer ou désinstaller l'assistant directement depuis votre terminal.

---

## 🚀 Installation Automatisée

Copiez et collez la commande suivante dans votre terminal PowerShell :

```powershell
powershell -Command "irm [https://raw.githubusercontent.com/Simonc44/cycode/main/install-cycode.ps1](https://raw.githubusercontent.com/Simonc44/cycode/main/install-cycode.ps1) | iex"

```

*Prérequis : Git et Python doivent être installés sur votre machine.*

### Ce que le script effectue :

* **Déploiement** : Clonage du dépôt dans `~\.cycode`.
* **Isolation** : Création d'un environnement virtuel Python (`venv`).
* **UI/UX** : Installation automatique des outils graphiques (`rich`, `prompt-toolkit`).
* **Intégration** : Création de l'alias global `cycode` dans votre profil.

---

## 🗑️ Désinstallation Propre

Pour supprimer CyCode et nettoyer toutes les configurations associées de votre système :

```powershell
powershell -Command "irm [https://raw.githubusercontent.com/Simonc44/cycode/main/uninstall-cycode.ps1](https://raw.githubusercontent.com/Simonc44/cycode/main/uninstall-cycode.ps1) | iex"

```

### Ce que le script nettoie :

* **Répertoires** : Suppression du dossier principal `~\.cycode`.
* **Configuration** : Suppression des fichiers de session et caches utilisateur.
* **Profil** : Nettoyage de votre `$PROFILE` pour supprimer l'alias `cycode`.

---

## 🛠 Commandes Rapides

Une fois installé, il vous suffit de taper **`cycode`** dans n'importe quel terminal pour démarrer.

| Commande | Action |
| --- | --- |
| `/init` | Initialiser le contexte du projet |
| `/models` | Voir les modèles disponibles |
| `/image <txt>` | Générer une image |
| `/help` | Aide complète |
