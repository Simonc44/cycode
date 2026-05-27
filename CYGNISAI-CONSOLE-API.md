# CygnisAI Enterprise API v3 — Référence Développeur

**Base URL :** `https://needlessly-faithful-gopher.ngrok-free.app`  
**Version :** 3.0.0  
**Contact :** support@cygnisai.com

---

## Authentification

L'API utilise deux méthodes d'authentification selon la route :

**Bearer Token** — header HTTP standard :
```
Authorization: Bearer cygnis-VOTRE_API_KEY
```

**API Key Header** — pour certaines routes admin/avancées :
```
X-API-Key: cygnis-VOTRE_API_KEY
```

> L'Admin API Key est générée automatiquement au démarrage du serveur et affichée dans la console. Elle doit être conservée précieusement.

---

## 1. System

Routes publiques pour vérifier l'état du serveur et lister les modèles disponibles.

---

### `GET /v3/`
Point d'entrée principal. Retourne les informations générales du serveur.

```bash
curl https://BASE_URL/v3/
```

---

### `GET /v3/health`
Vérifie que le serveur est opérationnel. Utile pour les health checks et monitoring.

```bash
curl https://BASE_URL/v3/health
```

---

### `GET /v3/models`
Liste tous les modèles d'IA disponibles sur la plateforme.

```bash
curl https://BASE_URL/v3/models
```

---

### `GET /v3/models/{model_id}`
Retourne les détails d'un modèle spécifique (capacités, paramètres, disponibilité).

```bash
curl https://BASE_URL/v3/models/cygnis-alpha-v2
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model_id` | string (path) | Identifiant du modèle |

---

### `POST /v3/loadtest/run`
Lance un test de charge sur le serveur.

```bash
curl -X POST https://BASE_URL/v3/loadtest/run
```

---

### `GET /v3/loadtest/status`
Retourne le statut du dernier test de charge en cours ou terminé.

```bash
curl https://BASE_URL/v3/loadtest/status
```

---

## 2. Auth

Gestion des clés API, permissions et authentification OAuth.

---

### `GET /v3/auth/status`
Vérifie la validité du token courant et retourne les informations associées (tier, scopes).

```bash
curl https://BASE_URL/v3/auth/status \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `POST /v3/auth/keys?label={label}`
Crée une nouvelle clé API avec un label personnalisé. Nécessite des droits admin.

```bash
curl -X POST "https://BASE_URL/v3/auth/keys?label=mon-app" \
  -H "Authorization: Bearer cygnis-ADMIN_KEY"
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `label` | string (query) | Nom identifiant la clé |

---

### `GET /v3/auth/keys`
Liste toutes les clés API actives associées au compte.

```bash
curl https://BASE_URL/v3/auth/keys \
  -H "Authorization: Bearer cygnis-ADMIN_KEY"
```

---

### `DELETE /v3/auth/keys/{label}`
Révoque une clé API. L'action est immédiate et irréversible.

```bash
curl -X DELETE https://BASE_URL/v3/auth/keys/mon-app \
  -H "Authorization: Bearer cygnis-ADMIN_KEY"
```

---

### `POST /v3/auth/rbac`
Assigne un rôle et des permissions à un utilisateur (Role-Based Access Control).

```bash
curl -X POST https://BASE_URL/v3/auth/rbac \
  -H "Authorization: Bearer cygnis-ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "role": "developer",
    "permissions": ["chat:write", "image:generate", "code:execute"]
  }'
```

| Champ | Type | Description |
|-------|------|-------------|
| `user_id` | string | Identifiant de l'utilisateur |
| `role` | string | Rôle à assigner (ex: `admin`, `developer`, `viewer`) |
| `permissions` | array | Liste des scopes autorisés |

---

### `POST /v3/auth/oauth`
Échange un token OAuth externe contre un token CygnisAI.

---

### `POST /v3/auth/refresh`
Renouvelle un token expiré.

---

## 3. Inference

Le cœur de l'API — envoi de prompts et réception de réponses IA.

---

### `POST /v3/chat`
Envoie un message à un modèle IA et reçoit une réponse complète.

```bash
curl -X POST https://BASE_URL/v3/chat \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explique le machine learning en 3 phrases.",
    "target": "auto",
    "max_new_tokens": 512,
    "use_memory": true
  }'
```

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `prompt` | string | — | (**requis**) Le message à envoyer |
| `target` | string | `"auto"` | Modèle cible (`"auto"`, `"cygnis-alpha-v1"`, etc.) |
| `max_new_tokens` | integer | `512` | Longueur maximale de la réponse |
| `session_id` | string\|null | `null` | ID de session pour maintenir le contexte |
| `messages` | array\|null | `null` | Historique de conversation (objets `{role, content}`) |
| `stream` | boolean | `false` | Activer le streaming SSE |
| `use_memory` | boolean | `true` | Utiliser la mémoire vectorielle (ChromaDB) |

---

### `POST /v3/chat/stream`
Identique à `/v3/chat` mais retourne la réponse en streaming (Server-Sent Events).

```bash
curl -X POST https://BASE_URL/v3/chat/stream \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Écris un poème sur l'\''IA.",
    "stream": true
  }'
```

> Les tokens arrivent au fur et à mesure. Idéal pour les interfaces conversationnelles.

---

### `GET /v3/chat/history`
Retourne l'historique complet des conversations associées à la clé API.

```bash
curl https://BASE_URL/v3/chat/history \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `GET /v3/chat/history/{id}`
Retourne une conversation spécifique par son identifiant.

```bash
curl https://BASE_URL/v3/chat/history/conv_abc123 \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

## 4. Sessions

Gestion des sessions conversationnelles pour maintenir le contexte entre plusieurs appels.

---

### `POST /v3/session`
Crée une nouvelle session. Retourne un `session_id` à réutiliser dans `/v3/chat`.

```bash
curl -X POST https://BASE_URL/v3/session \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `GET /v3/session`
Liste toutes les sessions actives associées à la clé.

```bash
curl https://BASE_URL/v3/session \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `GET /v3/session/{id}`
Retourne les détails et l'historique d'une session.

```bash
curl https://BASE_URL/v3/session/sess_xyz789 \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `POST /v3/session/{id}/messages`
Ajoute manuellement un message à une session existante.

```bash
curl -X POST https://BASE_URL/v3/session/sess_xyz789/messages \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Rappelle-toi que je préfère les réponses courtes."
  }'
```

| Champ | Type | Description |
|-------|------|-------------|
| `role` | string | `"user"`, `"assistant"` ou `"system"` |
| `content` | string | Contenu du message |

---

## 5. Queue

Système de file d'attente pour les tâches asynchrones longues.

---

### `POST /v3/queue`
Soumet un job asynchrone à la file d'attente.

```bash
curl -X POST https://BASE_URL/v3/queue \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "analyze_document", "file_id": "doc_123"}'
```

---

### `GET /v3/queue`
Liste tous les jobs en attente ou en cours.

```bash
curl https://BASE_URL/v3/queue \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `GET /v3/queue/{job_id}`
Vérifie le statut d'un job spécifique.

```bash
curl https://BASE_URL/v3/queue/job_456 \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `DELETE /v3/queue/{job_id}`
Annule un job en attente.

```bash
curl -X DELETE https://BASE_URL/v3/queue/job_456 \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

---

### `GET /v3/queue/stats`
Retourne des statistiques sur la file (jobs en attente, en cours, terminés).

---

### `DELETE /v3/queue/clear`
Vide entièrement la file d'attente. Action irréversible.

---

### `POST /v3/long-task?prompt={prompt}&callback_url={url}`
Démarre une tâche longue en arrière-plan. Peut notifier via webhook à la fin.

```bash
curl -X POST "https://BASE_URL/v3/long-task?prompt=Analyse+ce+corpus&callback_url=https://mon-app.com/webhook" \
  -H "Authorization: Bearer cygnis-VOTRE_KEY"
```

Retourne un `task_id` (UUID) à utiliser pour suivre la progression.

---

### `GET /v3/long-task/{task_id}`
Récupère le statut d'une tâche longue.

```bash
curl https://BASE_URL/v3/long-task/550e8400-e29b-41d4-a716-446655440000
```

---

## 6. CyVision — Vision par Ordinateur

---

### `POST /v3/image/generate`
Génère une image à partir d'un prompt texte (SDXL Turbo).

```bash
curl -X POST https://BASE_URL/v3/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Un chat astronaute sur la lune, style cyberpunk",
    "quality": "standard"
  }'
```

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `prompt` | string | — | (**requis**) Description de l'image |
| `quality` | string | `"standard"` | Qualité de génération |

---

### `POST /v3/image/edit`
Modifie une image existante selon un prompt. Envoi en `multipart/form-data`.

```bash
curl -X POST https://BASE_URL/v3/image/edit \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -F "image=@photo.jpg" \
  -F "prompt=Ajoute un arc-en-ciel dans le ciel"
```

---

### `POST /v3/image/analyze`
Analyse le contenu d'une image et retourne une description détaillée.

```bash
curl -X POST https://BASE_URL/v3/image/analyze \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -F "image=@screenshot.png"
```

---

## 7. Tools — Outils

---

### `POST /v3/code/execute`
Exécute du code dans un sandbox sécurisé.

```bash
curl -X POST https://BASE_URL/v3/code/execute \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "print(sum(range(100)))",
    "timeout": 30
  }'
```

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `language` | string | `"python"` | Langage (`"python"`, `"javascript"`, etc.) |
| `code` | string | — | (**requis**) Le code à exécuter |
| `timeout` | integer | `30` | Délai max en secondes |

---

### `POST /v3/code/analyze`
Analyse du code et retourne un rapport (qualité, bugs potentiels, suggestions).

```bash
curl -X POST https://BASE_URL/v3/code/analyze \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '"def add(a,b): return a+b"'
```

---

### `POST /v3/code/refactor`
Propose une version refactorisée et améliorée du code fourni.

```bash
curl -X POST https://BASE_URL/v3/code/refactor \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '"def add(a,b): return a+b"'
```

---

### `POST /v3/pdf/extract`
Extrait le texte et les données d'un fichier PDF.

```bash
curl -X POST https://BASE_URL/v3/pdf/extract \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -F "file=@document.pdf"
```

---

### `POST /v3/pdf/chat`
Pose une question sur le contenu d'un PDF précédemment chargé.

```bash
curl -X POST https://BASE_URL/v3/pdf/chat \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -d "question=Quel est le résumé du chapitre 2 ?"
```

---

### `POST /v3/archive/analyze`
Analyse le contenu d'une archive (ZIP, TAR…) et retourne un rapport de structure.

```bash
curl -X POST https://BASE_URL/v3/archive/analyze \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -F "file=@projet.zip"
```

---

## 8. Agents

Orchestration d'agents IA autonomes capables d'enchaîner des actions.

---

### `POST /v3/agents/task`
Lance un agent avec un objectif. L'agent planifie et exécute automatiquement les étapes.

```bash
curl -X POST https://BASE_URL/v3/agents/task \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Recherche les 5 meilleures librairies Python pour le NLP et compare-les",
    "tools_allowed": ["web_search", "code_exec"],
    "max_iterations": 5
  }'
```

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `goal` | string | — | (**requis**) Objectif de l'agent |
| `tools_allowed` | array | `["web_search","code_exec"]` | Outils autorisés |
| `max_iterations` | integer | `5` | Nombre max d'étapes |

---

### `GET /v3/agents`
Liste tous les agents actifs.

---

### `GET /v3/agents/{id}`
Retourne l'état et les logs d'un agent spécifique.

---

### `PATCH /v3/agents/{id}`
Met à jour les paramètres d'un agent en cours d'exécution.

```bash
curl -X PATCH https://BASE_URL/v3/agents/ag_789 \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"max_iterations": 10}'
```

---

### `POST /v3/agents/delegate`
Délègue une tâche à un agent existant.

```bash
curl -X POST https://BASE_URL/v3/agents/delegate \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "ag_789",
    "task": "Résume les résultats trouvés en JSON"
  }'
```

---

## 8. Browser — Automatisation Web

---

### `POST /v3/browser/action`
Exécute une action dans une session de navigateur (clic, saisie, navigation).

```bash
curl -X POST https://BASE_URL/v3/browser/action \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "br_sess_123",
    "action": "navigate:https://example.com"
  }'
```

---

### `POST /v3/browser/parse`
Analyse et extrait le contenu structuré de la page courante d'une session.

```bash
curl -X POST https://BASE_URL/v3/browser/parse \
  -H "Authorization: Bearer cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "br_sess_123"}'
```

---

### `GET /v3/browser/session`
Liste toutes les sessions de navigateur actives.

---

### `GET /v3/browser/session/{id}`
Retourne l'état d'une session de navigateur.

---

### `DELETE /v3/browser/session/{id}`
Ferme et supprime une session de navigateur.

---

## 9. Ops — Observabilité & Billing

---

### `GET /v3/logs`
Retourne les logs applicatifs récents.

```bash
curl https://BASE_URL/v3/logs \
  -H "Authorization: Bearer cygnis-ADMIN_KEY"
```

---

### `POST /v3/logs/export`
Exporte les logs dans un format structuré (JSON/CSV).

---

### `GET /v3/metrics/usage`
Statistiques d'utilisation (nombre de requêtes, tokens consommés).

---

### `GET /v3/metrics/latency`
Métriques de latence par endpoint et par modèle.

---

### `GET /v3/metrics/errors`
Taux et détails des erreurs récentes.

---

### `POST /v3/billing/quotas?uid={uid}&limit={limit}`
Met à jour le quota de requêtes d'un utilisateur. Réservé aux admins.

```bash
curl -X POST "https://BASE_URL/v3/billing/quotas?uid=user_123&limit=10000" \
  -H "Authorization: Bearer cygnis-ADMIN_KEY"
```

---

## 10. Advanced — Fonctionnalités Avancées

---

### MoE — Mixture of Experts

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/moe/route` | GET | Voir la stratégie de routage actuelle |
| `/v3/moe/experts` | GET | Lister les experts disponibles |
| `/v3/moe/assign` | POST | Assigner manuellement un expert à une requête |

---

### Shadow Mode — A/B Testing

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/shadow/status` | GET | Statut du shadow mode |
| `/v3/shadow/toggle` | POST | Activer/désactiver le shadow mode |
| `/v3/shadow/results` | GET | Comparer les résultats des deux modèles |

---

### Cache

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/cache/stats` | GET | Statistiques du cache (hit rate, taille) |
| `/v3/cache/clear` | POST | Vider le cache |

---

### Load Balancer

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/lb/status` | GET | État du load balancer |
| `/v3/lb/nodes` | GET | Liste des nœuds actifs |
| `/v3/lb/check` | POST | Forcer un health check des nœuds |

---

### Webhooks

Recevez des notifications en temps réel sur vos endpoints.

#### `POST /v3/webhooks`
Enregistre un webhook. Authentification via `X-API-Key`.

```bash
curl -X POST https://BASE_URL/v3/webhooks \
  -H "X-API-Key: cygnis-VOTRE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "task.completed",
    "callback_url": "https://mon-app.com/webhooks/cygnis",
    "secret": "mon_secret_hmac"
  }'
```

| Champ | Type | Description |
|-------|------|-------------|
| `event_type` | string | Type d'événement à écouter |
| `callback_url` | string (URI) | URL de destination |
| `secret` | string\|null | Secret HMAC pour valider les appels entrants |

#### `GET /v3/webhooks`
Liste les webhooks enregistrés.

#### `DELETE /v3/webhooks/{id}`
Supprime un webhook.

---

### RAG — Retrieval-Augmented Generation

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/rag/collections` | GET | Lister les collections vectorielles |
| `/v3/rag/collections` | POST | Créer une nouvelle collection |

---

### Fine-Tuning & Batch

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/fine-tuning/jobs` | POST | Lancer un job de fine-tuning |
| `/v3/batch` | POST | Soumettre un traitement batch |

---

### Support

| Route | Méthode | Description |
|-------|---------|-------------|
| `/v3/support/tickets` | GET | Lister les tickets de support |
| `/v3/support/tickets` | POST | Ouvrir un ticket |
| `/v3/support/tickets/{id}` | GET | Consulter un ticket |

---

## Rate Limiting

Certains endpoints sont soumis à une limite de débit. Par exemple, `/v3/limited-resource` accepte **5 requêtes toutes les 10 secondes**.

En cas de dépassement, l'API retourne `429 Too Many Requests`.

---

## Pages Web intégrées

| Route | Description |
|-------|-------------|
| `GET /` | Page d'accueil du dashboard |
| `GET /home` | Interface principale |
| `GET /home/models` | Catalogue des modèles |
| `GET /developers/sdk` | Guide d'intégration et exemples de code SDK |
| `GET /docs` | Swagger UI interactif |
| `GET /redoc` | Documentation ReDoc |

---

## Exemple d'intégration complète (Python)

```python
import requests

BASE_URL = "https://needlessly-faithful-gopher.ngrok-free.app"
API_KEY  = "cygnis-VOTRE_KEY"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Créer une session
session = requests.post(f"{BASE_URL}/v3/session", headers=headers).json()
session_id = session["id"]

# 2. Envoyer un message
response = requests.post(f"{BASE_URL}/v3/chat", headers=headers, json={
    "prompt": "Bonjour, qui es-tu ?",
    "session_id": session_id,
    "use_memory": True
}).json()

print(response["answer"])

# 3. Générer une image
image = requests.post(f"{BASE_URL}/v3/image/generate", headers=headers, json={
    "prompt": "Logo minimaliste pour une startup IA",
    "quality": "standard"
}).json()

print(image["url"])
```

---

## Codes d'erreur

| Code | Description |
|------|-------------|
| `200` | Succès |
| `401` | Token manquant ou invalide |
| `403` | Permission insuffisante (scope manquant) |
| `422` | Paramètres invalides (Validation Error) |
| `429` | Trop de requêtes (rate limit atteint) |
| `500` | Erreur interne du serveur |