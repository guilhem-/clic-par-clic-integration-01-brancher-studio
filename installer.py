"""Brancher le studio 3D de l'organisation à Open WebUI, par l'API d'Open WebUI.

Crée (ou remplace) ce que le module 1 de la série « Intégrations IA » fait à l'écran :
  1. le groupe d'utilisateurs autorisés (GROUPE, créé vide s'il n'existe pas) ;
  2. la connexion MCP « Studio 3D » (open-webui/connexion-studio.json) : jeton, en-tête
     d'identité, outils autorisés, droits réservés au groupe ;
  3. le modèle « Studio 3D » (open-webui/modele-studio3d.json), avec les consignes de
     open-webui/consignes-modele.txt.

Usage :
  python installer.py              # installe (ou met à jour)
  python installer.py --retirer    # retire la connexion et le modèle (le groupe reste)
  python installer.py --outils     # écrit open-webui/outils-mcp.yaml : ce que le modèle reçoit du studio

Réglages : fichier .env (voir .env.example) ; les variables d'environnement l'emportent.
Aucune dépendance : Python 3.10 ou plus récent, bibliothèque standard seulement.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ICI = pathlib.Path(__file__).resolve().parent
OWUI = ICI / "open-webui"


def reglages() -> dict:
    """Lit .env (clé=valeur), puis l'environnement, qui l'emporte."""
    r = {}
    env = ICI / ".env"
    if env.exists():
        for ligne in env.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                r[cle.strip()] = valeur.strip()
    for cle in ("OWUI_URL", "OWUI_JETON", "STUDIO_URL", "STUDIO_JETON", "MODELE_BASE", "GROUPE"):
        if os.environ.get(cle):
            r[cle] = os.environ[cle]
    return r


R = reglages()


def requete(methode: str, url: str, corps=None, entetes=None):
    donnees = None if corps is None else json.dumps(corps).encode()
    req = urllib.request.Request(url, data=donnees, method=methode,
                                 headers={"Content-Type": "application/json", **(entetes or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as rep:
            texte = rep.read().decode()
    except urllib.error.HTTPError as e:
        sys.exit(f"{methode} {url} : {e.code} {e.read().decode()[:300]}")
    return texte


def api(methode: str, chemin: str, corps=None):
    """Appel de l'API d'Open WebUI avec le jeton administrateur."""
    texte = requete(methode, R["OWUI_URL"].rstrip("/") + chemin, corps,
                    {"Authorization": f"Bearer {R['OWUI_JETON']}"})
    return json.loads(texte) if texte else None


def remplir(texte: str, valeurs: dict) -> str:
    """Remplace les ${VARIABLE} d'un gabarit ; les {{USER_…}} restent pour Open WebUI."""
    for cle, valeur in valeurs.items():
        texte = texte.replace("${" + cle + "}", json.dumps(valeur)[1:-1])
    return texte


def groupe() -> str:
    """Identifiant du groupe GROUPE, créé s'il n'existe pas."""
    nom = R.get("GROUPE", "Graphistes")
    for g in api("GET", "/api/v1/groups/") or []:
        if g["name"] == nom:
            return g["id"]
    g = api("POST", "/api/v1/groups/create", {"name": nom, "description": "Utilisateurs du studio 3D"})
    print(f"groupe « {nom} » créé : ajoutez-y ses membres (Panneau d'administration › Utilisateurs › Groupes)")
    return g["id"]


def retirer() -> None:
    conf = api("GET", "/api/v1/configs/tool_servers")
    autres = [c for c in conf["TOOL_SERVER_CONNECTIONS"] if c.get("info", {}).get("id") != "studio"]
    api("POST", "/api/v1/configs/tool_servers", {"TOOL_SERVER_CONNECTIONS": autres})
    modeles = (api("GET", "/api/v1/models/list?page=1") or {}).get("items", [])
    for m in modeles:
        if m["id"] == "studio-3d":
            api("POST", "/api/v1/models/model/delete", {"id": m["id"]})
    print("connexion et modèle « Studio 3D » retirés")


def installer() -> None:
    for cle in ("OWUI_URL", "OWUI_JETON", "STUDIO_URL", "STUDIO_JETON", "MODELE_BASE"):
        if not R.get(cle):
            sys.exit(f"réglage manquant : {cle} (voir .env.example)")
    valeurs = {"STUDIO_JETON": R["STUDIO_JETON"], "GROUPE_ID": groupe(), "MODELE_BASE": R["MODELE_BASE"]}
    # 1. La connexion : même contenu que le formulaire « Ajouter une connexion ».
    connexion = json.loads(remplir((OWUI / "connexion-studio.json").read_text(encoding="utf-8"), valeurs))
    connexion["url"] = R["STUDIO_URL"]
    retirer()
    conf = api("GET", "/api/v1/configs/tool_servers")
    api("POST", "/api/v1/configs/tool_servers",
        {"TOOL_SERVER_CONNECTIONS": conf["TOOL_SERVER_CONNECTIONS"] + [connexion]})
    # 2. Le modèle : consignes lues dans leur fichier, une phrase par ligne.
    modele = json.loads(remplir((OWUI / "modele-studio3d.json").read_text(encoding="utf-8"), valeurs))
    modele["params"]["system"] = (OWUI / "consignes-modele.txt").read_text(encoding="utf-8").strip()
    api("POST", "/api/v1/models/create", modele)
    print("connexion et modèle « Studio 3D » installés, réservés au groupe", R.get("GROUPE", "Graphistes"))


# ---------------------------------------------------------------- Ce que reçoit le modèle

def _schema(nom: str, s: dict, retrait: str) -> list[str]:
    """Une propriété du schéma d'arguments, sur une ligne lisible."""
    if "anyOf" in s:
        genre = " | ".join(x.get("type", "?") for x in s["anyOf"])
    else:
        genre = s.get("type", "?")
    defaut = f", default: {json.dumps(s['default'])}" if "default" in s else ""
    return [f"{retrait}{nom}: {{ type: {genre}{defaut} }}"]


def outils() -> None:
    """Appelle tools/list sur le studio (comme Open WebUI) et écrit open-webui/outils-mcp.yaml."""
    rep = requete("POST", R["STUDIO_URL"], {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                  {"Accept": "application/json, text/event-stream", "Authorization": f"Bearer {R['STUDIO_JETON']}"})
    donnees = "".join(l[5:] for l in rep.splitlines() if l.startswith("data:")) or rep
    lignes = ["# Réponse du studio à tools/list : ce que le modèle reçoit, outil par outil.",
              "# Écrit par « python installer.py --outils » (descriptions telles quelles)."]
    for o in json.loads(donnees)["result"]["tools"]:
        lignes += [f"- name: {o['name']}", "  description: |"]
        lignes += [f"    {l.strip()}" if l.strip() else "" for l in o.get("description", "").strip().splitlines()]
        schema = o.get("inputSchema", {})
        lignes.append("  inputSchema:")
        if schema.get("required"):
            lignes.append(f"    required: [{', '.join(schema['required'])}]")
        proprietes = schema.get("properties", {})
        lignes.append("    properties:" + ("" if proprietes else " {}"))
        for nom, s in proprietes.items():
            lignes += _schema(nom, s, "      ")
    (OWUI / "outils-mcp.yaml").write_text("\n".join(lignes) + "\n", encoding="utf-8", newline="\n")
    print(f"{OWUI / 'outils-mcp.yaml'} écrit")


if __name__ == "__main__":
    if "--outils" in sys.argv:
        outils()
    elif "--retirer" in sys.argv:
        retirer()
    else:
        installer()
