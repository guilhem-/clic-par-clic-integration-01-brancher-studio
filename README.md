# Brancher le studio 3D de l'organisation à Open WebUI — connexion MCP, outils, consignes, droits

Configuration de la démonstration du module 1 de la série « Clic par clic » **Intégrations IA**
(Open WebUI relié au studio 3D de l'organisation).

Vidéo : {{video}}

## But

Votre organisation dispose d'un **studio 3D** : un service d'intelligence artificielle qui calcule
des images avec Blender, déployé dans un cluster Kubernetes et publié comme **serveur MCP**. Ce dépôt
contient tout ce que l'**administrateur d'Open WebUI** règle pour le mettre à la disposition des
utilisateurs, à l'état montré en fin de vidéo :

- **une connexion MCP** (`open-webui/connexion-studio.json`) : adresse interne du service, **jeton
  porteur** lu dans une variable (jamais écrit dans un fichier), **en-tête d'identité**
  `X-Utilisateur-Email: {{USER_EMAIL}}` qu'Open WebUI remplit à chaque appel, **liste des outils
  autorisés** (`soumettre_rendu, etat_rendu, mes_rendus, lister_assets` : un outil ajouté plus tard
  par l'équipe du studio n'apparaît pas sans votre accord), droits réservés à un **groupe** ;
- **un modèle dédié** « Studio 3D » (`open-webui/modele-studio3d.json`) : appel de fonction natif,
  outils intégrés désactivés, même groupe ;
- **ses consignes** (`open-webui/consignes-modele.txt`), une phrase par ligne, avec les pièges
  évités : décor nommé « Decor… » (exclu de l'objet 3D), couleur réglée sur l'entrée « Base Color »
  (sinon grise au rendu), pas de profondeur de champ (images floues), script court et à plat (un
  modèle de langage indente parfois mal), mention visible seulement sur demande, liens recopiés
  **tels quels** (reformulé, un lien signé ne fonctionne plus) ;
- **ce que reçoit le modèle** (`open-webui/outils-mcp.yaml`) : la réponse du studio à `tools/list`,
  description et paramètres de chaque outil, écrite par `python installer.py --outils`.

Le service lui-même n'est pas ici : il est construit pas à pas dans la série **« Créer un service
d'IA compatible agentique : le studio 3D »**, un dépôt par module :

| Module | Dépôt |
|---|---|
| 1. Un studio 3D pour toute l'organisation (serveur MCP) | [clic-par-clic-studio3d-01-studio-mcp](https://github.com/guilhem-/clic-par-clic-studio3d-01-studio-mcp) |
| 2. Passer le studio à l'échelle | [clic-par-clic-studio3d-02-echelle](https://github.com/guilhem-/clic-par-clic-studio3d-02-echelle) |
| 3. Observer le studio avec Grafana | [clic-par-clic-studio3d-03-grafana](https://github.com/guilhem-/clic-par-clic-studio3d-03-grafana) |
| 4. Marquer les rendus générés par IA | [clic-par-clic-studio3d-04-marquage](https://github.com/guilhem-/clic-par-clic-studio3d-04-marquage) |
| 5. Une bibliothèque d'assets pour tous les rendus | [clic-par-clic-studio3d-05-assets](https://github.com/guilhem-/clic-par-clic-studio3d-05-assets) |
| 6. Télécharger la scène Blender (stockage S3) | [clic-par-clic-studio3d-06-stockage-s3](https://github.com/guilhem-/clic-par-clic-studio3d-06-stockage-s3) |

Ce module se branche sur le studio du **module 6** (image `studio3d:5`, bibliothèque d'assets,
stockage S3 branché).

## Prérequis

- Open WebUI 0.11 (tourné sur 0.11.3), un compte **administrateur** et son jeton (Réglages ›
  Compte › Clés API, ou jeton de session).
- Le studio 3D déployé dans le même cluster qu'Open WebUI (dépôt du module 6 de la série Studio 3D),
  et son jeton (secret Kubernetes `studio`, clé `jeton`).
- Un modèle de langage qui sait appeler des outils, déclaré dans Open WebUI.
- Python 3.10 ou plus récent (bibliothèque standard seulement).

## Installation pas à pas

### À la main, comme dans la vidéo

1. **Réglages d'administration › Intégrations › External Tool Servers › +** : type « MCP Streamable
   HTTP », URL `http://studio.studio3d.svc.cluster.local:8000/mcp` (adresse interne : Open WebUI joint
   le studio par son nom de service).
2. **Auth** : « Bearer », collez le jeton du studio (le champ le masque). Nom « Studio 3D », ID
   `studio`.
3. **Avancé › En-têtes HTTP** : `{"X-Utilisateur-Email": "{{USER_EMAIL}}"}`. Open WebUI remplace
   aussi `{{USER_ID}}`, `{{USER_NAME}}`, `{{USER_ROLE}}`, `{{USER_GROUPS}}` (le module 2 ajoute
   `X-Utilisateur-Id: {{USER_ID}}`, voir le dépôt
   [clic-par-clic-integration-02-notifications](https://github.com/guilhem-/clic-par-clic-integration-02-notifications)).
4. **Liste de filtrage des fonctions par nom** : `soumettre_rendu, etat_rendu, mes_rendus,
   lister_assets` (des noms sans « ! » forment une liste d'autorisation).
5. **Contrôle d'accès › Ajouter un accès** : le groupe « Graphistes ». **Vérifier la connexion**,
   puis **Enregistrer**.
6. **Espace de travail › Modèles › +** : nom « Studio 3D », un modèle de base, le prompt système de
   `open-webui/consignes-modele.txt` ; **Outils** : « Studio 3D » ; **Réglages avancés › Appel de
   fonction** : natif ; outils intégrés décochés ; **Accès** : le groupe « Graphistes » ;
   **Enregistrer & Créer**.

### Par l'API d'Open WebUI

```bash
cp .env.example .env          # OWUI_URL, OWUI_JETON, STUDIO_URL, STUDIO_JETON, MODELE_BASE, GROUPE
python installer.py           # groupe (créé s'il manque), connexion et modèle « Studio 3D »
python installer.py --retirer # retire la connexion et le modèle (le groupe reste)
```

Le groupe est créé vide : ajoutez-y ses membres (Panneau d'administration › Utilisateurs ›
Groupes).

Pour régénérer `open-webui/outils-mcp.yaml` depuis le poste, ouvrez un accès local au studio
(`kubectl port-forward -n studio3d svc/studio 18000:8000`), puis :

```bash
STUDIO_URL=http://127.0.0.1:18000/mcp python installer.py --outils
```

## Essai

Avec un compte membre du groupe, choisissez le modèle « Studio 3D » :

1. « Quels meubles et quels éclairages sont disponibles ? » : l'assistant appelle `lister_assets`
   et affiche les vignettes.
2. « Crée une scène de salon avec le fauteuil et le vase en céramique de la bibliothèque, sous
   l'éclairage salon bois. » : demande numéro 1.
3. « Fais-en une seconde version, identique, avec la mention visible, pour la publier. » : demande
   numéro 2, `marquage_visible: true`.
4. « Montre-moi le rendu numéro 1. » : image, objet 3D en artefact, lien « Télécharger la scène
   Blender ». Puis « Et le rendu numéro 2 ? » : la même image, avec le bandeau.

Un compte hors du groupe ne voit ni le modèle ni la connexion.

## Sécurité

- Le jeton du studio ne quitte jamais le serveur Open WebUI : ni l'utilisateur ni le modèle ne le
  voient. Il n'est écrit dans aucun fichier de ce dépôt (`.env` est ignoré par git).
- Le code écrit par le modèle s'exécute dans le studio, isolé et sans réseau, jamais dans Open WebUI.
- Chaque utilisateur ne voit que ses rendus : le studio range chaque demande au nom de l'adresse
  transmise par l'en-tête d'identité.

## Série

- Module suivant : **Prévenir l'utilisateur quand son rendu est prêt** (message direct d'un compte
  robot, en-tête `{{USER_ID}}`) —
  [clic-par-clic-integration-02-notifications](https://github.com/guilhem-/clic-par-clic-integration-02-notifications).
- Construire le studio : série « Créer un service d'IA compatible agentique : le studio 3D » (dépôts
  ci-dessus).

## Licence

MIT (voir `LICENSE`). Assets de la bibliothèque du studio : Poly Haven, CC0.
