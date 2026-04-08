"""
📚 La Première Phrase — version Streamlit
Scores stockés dans GitHub (joueurs.csv)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARAMÈTRES À PERSONNALISER PAR VERSION (lignes 20-30)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Copiez ce fichier dans chaque dépôt GitHub et changez
uniquement le bloc CONFIG VERSION ci-dessous.

Secrets Streamlit Cloud à configurer dans chaque app :
  [github]
  token        = "ghp_xxxxxxxxxxxx"   ← dépôt courant (questions)
  repo         = "votre-pseudo/depot-litterature"
  branch       = "main"

  [scores]
  token        = "ghp_xxxxxxxxxxxx"   ← même token ou dédié
  repo         = "votre-pseudo/depot-scores"
  branch       = "main"
"""

import random
import hashlib
import base64
import json
import requests
import pandas as pd
import streamlit as st
from io import StringIO
from datetime import datetime

# ══════════════════════════════════════════════════════
# CONFIG VERSION — seule section à modifier par dépôt
# ══════════════════════════════════════════════════════

TITRE_JEU      = "📚 La Première Phrase"   # affiché en haut
SOUS_TITRE     = "Retrouvez le livre à partir de son incipit"
QUESTION_LABEL = "Quel est ce livre ?"     # question posée à l'élève
LIVRES_PATH    = "livres.xlsx"             # fichier de questions dans CE dépôt
PAGE_ICON      = "📚"

# ══════════════════════════════════════════════════════
# Fichiers dans le DÉPÔT COMMUN (scores)
# ══════════════════════════════════════════════════════

JOUEURS_PATH = "joueurs.csv"   # comptes communs à toutes les versions
SCORES_PATH  = "scores.csv"    # classement commun à toutes les versions


# ── Accès GitHub ─────────────────────────────────────────────────────

def cfg(key: str) -> str:
    """Secrets du dépôt courant (questions)."""
    return st.secrets["github"][key]

def cfg_scores(key: str) -> str:
    """Secrets du dépôt commun (scores)."""
    return st.secrets["scores"][key]

def gh_headers(token: str) -> dict:
    return {"Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"}

def gh_url(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{path}"


# ── Lecture / écriture CSV ───────────────────────────────────────────

def gh_lire_csv(path: str, cols: list, depot: str = "scores") -> pd.DataFrame:
    """Lit un CSV depuis le dépôt commun (scores) ou courant."""
    if depot == "scores":
        token, repo, branch = cfg_scores("token"), cfg_scores("repo"), cfg_scores("branch")
    else:
        token, repo, branch = cfg("token"), cfg("repo"), cfg("branch")
    r = requests.get(gh_url(repo, path), headers=gh_headers(token),
                     params={"ref": branch})
    if r.status_code == 404:
        return pd.DataFrame(columns=cols)
    r.raise_for_status()
    contenu = base64.b64decode(r.json()["content"]).decode("utf-8")
    df = pd.read_csv(StringIO(contenu), dtype=str)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df

def gh_ecrire_csv(path: str, df: pd.DataFrame, message: str, depot: str = "scores"):
    """Écrit un CSV dans le dépôt commun ou courant."""
    if depot == "scores":
        token, repo, branch = cfg_scores("token"), cfg_scores("repo"), cfg_scores("branch")
    else:
        token, repo, branch = cfg("token"), cfg("repo"), cfg("branch")
    contenu_b64 = base64.b64encode(df.to_csv(index=False).encode()).decode()
    r = requests.get(gh_url(repo, path), headers=gh_headers(token),
                     params={"ref": branch})
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {"message": message, "content": contenu_b64, "branch": branch}
    if sha:
        payload["sha"] = sha
    requests.put(gh_url(repo, path), headers=gh_headers(token),
                 data=json.dumps(payload)).raise_for_status()


@st.cache_data(ttl=30)
def gh_lire_livres() -> list:
    """Lit livres.xlsx depuis le dépôt courant (mis en cache 30 s)."""
    import io
    token, repo, branch = cfg("token"), cfg("repo"), cfg("branch")
    r = requests.get(gh_url(repo, LIVRES_PATH), headers=gh_headers(token),
                     params={"ref": branch})
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(base64.b64decode(r.json()["content"])))
    donnees = []
    for _, row in df.iterrows():
        p   = str(row.iloc[0]).strip()
        rep = str(row.iloc[1]).strip()
        if p and rep and p != "nan" and rep != "nan":
            donnees.append({"phrase": p, "reponse": rep})
    return donnees


# ── Sécurité ─────────────────────────────────────────────────────────

def hasher(mdp: str) -> str:
    return hashlib.sha256(mdp.encode()).hexdigest()


# ── Gestion joueurs (dépôt commun) ───────────────────────────────────

COLS_JOUEURS = ["pseudo", "mot_de_passe"]
COLS_SCORES  = ["pseudo", "meilleur_score", "nb_parties", "derniere_partie", "version"]

def inscrire(pseudo: str, mdp: str) -> tuple:
    pseudo = pseudo.strip()
    if len(pseudo) < 2:
        return False, "Le pseudo doit faire au moins 2 caractères."
    if len(mdp) < 3:
        return False, "Le mot de passe doit faire au moins 3 caractères."
    df = gh_lire_csv(JOUEURS_PATH, COLS_JOUEURS)
    if pseudo.lower() in df["pseudo"].str.lower().values:
        return False, "Ce pseudo est déjà utilisé."
    df = pd.concat([df, pd.DataFrame([{"pseudo": pseudo,
                                        "mot_de_passe": hasher(mdp)}])],
                   ignore_index=True)
    gh_ecrire_csv(JOUEURS_PATH, df, f"Inscription : {pseudo}")
    return True, pseudo

def connecter(pseudo: str, mdp: str) -> tuple:
    df = gh_lire_csv(JOUEURS_PATH, COLS_JOUEURS)
    mask = df["pseudo"].str.lower() == pseudo.strip().lower()
    if not mask.any():
        return False, "Pseudo inconnu."
    j = df[mask].iloc[0]
    if j["mot_de_passe"] != hasher(mdp):
        return False, "Mot de passe incorrect."
    return True, j["pseudo"]

def mettre_a_jour_score(pseudo: str, score_pct: float):
    """Met à jour le score dans le dépôt commun."""
    df   = gh_lire_csv(SCORES_PATH, COLS_SCORES)
    mask = df["pseudo"].str.lower() == pseudo.lower()
    if mask.any():
        idx    = df[mask].index[0]
        ancien = float(df.at[idx, "meilleur_score"] or 0)
        if score_pct > ancien:
            df.at[idx, "meilleur_score"] = f"{score_pct:.1f}"
        df.at[idx, "nb_parties"]     = str(int(df.at[idx, "nb_parties"] or 0) + 1)
        df.at[idx, "derniere_partie"] = datetime.now().strftime("%d/%m/%Y")
        df.at[idx, "version"]         = TITRE_JEU
    else:
        df = pd.concat([df, pd.DataFrame([{
            "pseudo":          pseudo,
            "meilleur_score":  f"{score_pct:.1f}",
            "nb_parties":      "1",
            "derniere_partie": datetime.now().strftime("%d/%m/%Y"),
            "version":         TITRE_JEU,
        }])], ignore_index=True)
    gh_ecrire_csv(SCORES_PATH, df, f"Score : {pseudo} → {score_pct:.0f}% ({TITRE_JEU})")

def classement(top: int = 20) -> pd.DataFrame:
    df = gh_lire_csv(SCORES_PATH, COLS_SCORES)
    df["meilleur_score"] = pd.to_numeric(df["meilleur_score"], errors="coerce").fillna(0)
    df["nb_parties"]     = pd.to_numeric(df["nb_parties"],     errors="coerce").fillna(0).astype(int)
    return df.sort_values("meilleur_score", ascending=False).head(top).reset_index(drop=True)

def infos_joueur(pseudo: str) -> dict:
    df   = gh_lire_csv(SCORES_PATH, COLS_SCORES)
    mask = df["pseudo"].str.lower() == pseudo.lower()
    if not mask.any():
        return {"meilleur_score": 0, "nb_parties": 0}
    j = df[mask].iloc[0]
    return {"meilleur_score": float(j["meilleur_score"] or 0),
            "nb_parties":     int(j["nb_parties"] or 0)}


# ── CSS personnalisé ─────────────────────────────────────────────────

def injecter_css():
    st.markdown("""
       <style>
    @import url('https://fonts.googleapis.com/css2?family=Georgia&family=Helvetica&display=swap');

    /* Fond général */
    .stApp { background-color: #1A1A2E; color: #EAEAEA; }

    /* Masquer le menu hamburger et footer */
    #MainMenu, footer { visibility: hidden; }

    /* Titre principal */
    .titre-jeu {
        font-family: Georgia, serif;
        font-size: 2.4em;
        font-weight: bold;
        color: #EAEAEA;
        text-align: center;
        margin-bottom: 0.2em;
    }
    .sous-titre {
        font-family: Georgia, serif;
        font-style: italic;
        font-size: 1.1em;
        color: #aec1e4;
        text-align: center;
        margin-bottom: 1.2em;
    }

    /* Carte phrase */
    .carte-phrase {
        background: #0F3460;
        border-left: 5px solid #E94560;
        border-radius: 8px;
        padding: 1.4em 1.8em;
        font-family: Georgia, serif;
        font-style: italic;
        font-size: 1.15em;
        color: #EAEAEA;
        margin: 1em 0 1.4em 0;
        line-height: 1.6;
    }

    /* Barre de progression */
    .barre-prog {
        background: #3451a1;
        border-radius: 4px;
        height: 10px;
        margin-bottom: 1em;
    }
    .barre-prog-fill {
        background: #E94560;
        border-radius: 4px;
        height: 10px;
        transition: width 0.4s;
    }

    /* Feedback bonne/mauvaise réponse */
    .feedback-ok  { color: #2ECC71; font-weight: bold; font-size: 1.1em; }
    .feedback-ko  { color: #E74C3C; font-weight: bold; font-size: 1.1em; }

    /* Score final */
    .score-final {
        background: #16213E;
        border-radius: 12px;
        padding: 1.6em;
        text-align: center;
    }
    .score-gros {
        font-size: 3em;
        font-weight: bold;
        color: #EAEAEA;
    }
    .score-pct { color: #8892A4; font-size: 1.1em; }

    /* Info utilisateur */
    .user-badge {
        background: #16213E;
        border-radius: 20px;
        padding: 4px 14px;
        color: #F5A623;
        font-size: 0.95em;
        display: inline-block;
    }

    /* Boutons onglets connexion/inscription — forcer une seule ligne */
    .stButton > button {
        white-space: nowrap !important;
        background-color: #E94560 !important;
        color: #2ECC71 !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5em 2em !important;
    }
    .stButton > button:hover {
        background-color: #c73652 !important;
        color: #2ECC71 !important;
    }

    /* Inputs */
    .stTextInput > div > div > input {
        background-color: #0F3460 !important;
        color: #EAEAEA !important;
        border: 1px solid #8892A4 !important;
        border-radius: 6px !important;
    }

    /* Légendes des zones de saisie */
    .stTextInput label {
        color: #F5A623 !important;
        font-weight: bold !important;
    }

    /* Étiquette du slider */
    .stSlider label {
        color: #F5A623 !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Initialisation session ───────────────────────────────────────────

def init_session():
    defaults = {
        "page":        "login",
        "mode_login":  "connexion",
        "joueur":      None,
        "livres":      None,
        "questions":   [],
        "index":       0,
        "score":       0,
        "nb_questions": 10,
        "repondu":     False,
        "correct":     None,
        "bonne_rep":   None,
        "choix":       [],
        "choix_fait":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Pages ────────────────────────────────────────────────────────────

def page_login():
    st.markdown(f'<div class="titre-jeu">{TITRE_JEU}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sous-titre">{SOUS_TITRE}</div>', unsafe_allow_html=True)
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        mode = st.session_state.mode_login
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔑 Se connecter", use_container_width=True):
                st.session_state.mode_login = "connexion"
                st.rerun()
        with c2:
            if st.button("✏️ S'inscrire", use_container_width=True):
                st.session_state.mode_login = "inscription"
                st.rerun()

        st.markdown("")
        with st.container(border=True):
            pseudo = st.text_input("Pseudo", key="inp_pseudo", placeholder="Votre pseudo...")
            mdp    = st.text_input("Mot de passe", type="password", key="inp_mdp",
                                   placeholder="Votre mot de passe...")

            if mode == "connexion":
                if st.button("  CONNEXION  ", use_container_width=True):
                    ok, msg = connecter(pseudo, mdp)
                    if ok:
                        st.session_state.joueur = msg
                        st.session_state.page   = "accueil"
                        st.rerun()
                    else:
                        st.error(f"⚠️ {msg}")
            else:
                if st.button("  CRÉER MON COMPTE  ", use_container_width=True):
                    ok, msg = inscrire(pseudo, mdp)
                    if ok:
                        st.session_state.joueur = msg
                        st.session_state.page   = "accueil"
                        st.rerun()
                    else:
                        st.error(f"⚠️ {msg}")

        st.markdown("<div style='text-align:center;color:#8892A4'>── ou ──</div>",
                    unsafe_allow_html=True)
        if st.button("Jouer en mode invité (sans enregistrement du score)",
                     use_container_width=True):
            st.session_state.joueur = None
            st.session_state.page   = "accueil"
            st.rerun()


def page_accueil():
    nom = st.session_state.joueur or "Invité"
    col_u, col_c = st.columns([3, 1])
    with col_u:
        st.markdown(f'<span class="user-badge">👤 {nom}</span>', unsafe_allow_html=True)
    with col_c:
        if st.button("Changer d'utilisateur"):
            st.session_state.page = "login"
            st.rerun()

    st.markdown(f'<div class="titre-jeu">{TITRE_JEU}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sous-titre">{SOUS_TITRE}</div>', unsafe_allow_html=True)
    st.markdown("---")

    if st.session_state.livres is None:
        with st.spinner("Chargement des livres…"):
            st.session_state.livres = gh_lire_livres()

    nb_livres = len(st.session_state.livres)
    st.markdown(f"<div style='text-align:center;color:#8892A4'>{nb_livres} livres disponibles dans la bibliothèque</div>",
                unsafe_allow_html=True)

    if st.session_state.joueur:
        infos = infos_joueur(st.session_state.joueur)
        if infos["nb_parties"] > 0:
            st.markdown(
                f"<div style='text-align:center;color:#F5A623;margin:0.4em 0'>"
                f"🏅 Votre meilleur score : {infos['meilleur_score']:.0f} % "
                f"· {infos['nb_parties']} partie(s) jouée(s)</div>",
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        nb = st.slider("Nombre de questions", 1, min(20, nb_livres), 10)
        st.session_state.nb_questions = nb

        c1, c2 = st.columns(2)
        with c1:
            if st.button("  🎮 JOUER  ", use_container_width=True):
                st.session_state.questions  = random.sample(st.session_state.livres, nb)
                st.session_state.index      = 0
                st.session_state.score      = 0
                st.session_state.repondu    = False
                st.session_state.choix      = []
                st.session_state.page       = "jeu"
                st.rerun()
        with c2:
            if st.button("  🏆 CLASSEMENT  ", use_container_width=True):
                st.session_state.page = "classement"
                st.rerun()

    st.markdown("<div style='text-align:center;color:#8892A4;margin-top:2em;font-size:0.9em'>"
                "Règle : choisissez parmi 4 propositions · Pas de limite de temps</div>",
                unsafe_allow_html=True)


def page_jeu():
    questions = st.session_state.questions
    idx       = st.session_state.index
    tot       = len(questions)
    q         = questions[idx]

    pct_prog = int(idx / tot * 100)
    st.markdown(
        f'<div class="barre-prog"><div class="barre-prog-fill" style="width:{pct_prog}%"></div></div>',
        unsafe_allow_html=True)

    col_q, col_s = st.columns([3, 1])
    with col_q:
        st.markdown(f"**Question {idx+1} / {tot}**  ·  "
                    f"<span style='color:#8892A4'>👤 {st.session_state.joueur or 'Invité'}</span>",
                    unsafe_allow_html=True)
    with col_s:
        st.markdown(f"<div style='text-align:right;color:#F5A623'>✦ Score : "
                    f"{st.session_state.score} / {idx}</div>", unsafe_allow_html=True)

    st.markdown(f'<div class="carte-phrase">« {q["phrase"]} »</div>', unsafe_allow_html=True)

    if not st.session_state.repondu and not st.session_state.choix:
        toutes = [d["reponse"] for d in st.session_state.livres]
        autres = [r for r in toutes if r != q["reponse"]]
        choix  = random.sample(autres, min(3, len(autres))) + [q["reponse"]]
        random.shuffle(choix)
        st.session_state.choix = choix

    choix = st.session_state.choix
    st.markdown(f"**{QUESTION_LABEL}**")

    if not st.session_state.repondu:
        for i, c in enumerate(choix):
            if st.button(f"{chr(65+i)}.  {c}", key=f"choix_{i}", use_container_width=True):
                correct = (c == q["reponse"])
                if correct:
                    st.session_state.score += 1
                st.session_state.repondu    = True
                st.session_state.correct    = correct
                st.session_state.bonne_rep  = q["reponse"]
                st.session_state.choix_fait = c
                st.rerun()
    else:
        for i, c in enumerate(choix):
            if c == st.session_state.bonne_rep:
                st.markdown(f"<div style='background:#16213E;border-left:4px solid #2ECC71;"
                            f"padding:10px 16px;border-radius:6px;margin:4px 0;"
                            f"color:#2ECC71;font-weight:bold'>{chr(65+i)}.  {c}</div>",
                            unsafe_allow_html=True)
            elif c == st.session_state.choix_fait and not st.session_state.correct:
                st.markdown(f"<div style='background:#16213E;border-left:4px solid #3498DB;"
                            f"padding:10px 16px;border-radius:6px;margin:4px 0;"
                            f"color:#3498DB;font-weight:bold'>{chr(65+i)}.  {c}</div>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background:#16213E;padding:10px 16px;"
                            f"border-radius:6px;margin:4px 0;color:#8892A4'>"
                            f"{chr(65+i)}.  {c}</div>", unsafe_allow_html=True)

        if st.session_state.correct:
            st.markdown('<div class="feedback-ok">✅ Bonne réponse !</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="feedback-ko">❌ La bonne réponse était : '
                        f'{st.session_state.bonne_rep}</div>', unsafe_allow_html=True)

        label_btn = "Question suivante →" if idx + 1 < tot else "Voir les résultats →"
        if st.button(f"  {label_btn}  ", use_container_width=False):
            st.session_state.index     += 1
            st.session_state.repondu   = False
            st.session_state.choix     = []
            st.session_state.choix_fait = None
            if st.session_state.index >= tot:
                score_pct = (st.session_state.score / tot) * 100
                if st.session_state.joueur:
                    mettre_a_jour_score(st.session_state.joueur, score_pct)
                st.session_state.page = "resultat"
            st.rerun()


def page_resultat():
    total = len(st.session_state.questions)
    score = st.session_state.score
    pct   = (score / total) * 100

    if pct == 100:   emoji, mention, couleur = "🏆", "Parfait !",         "#F5A623"
    elif pct >= 80:  emoji, mention, couleur = "🥇", "Excellent !",        "#F5A623"
    elif pct >= 60:  emoji, mention, couleur = "🥈", "Bien joué !",        "#2ECC71"
    elif pct >= 40:  emoji, mention, couleur = "🥉", "Pas mal !",          "#F5A623"
    else:            emoji, mention, couleur = "📚", "Continuez à lire !", "#8892A4"

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f'<div class="score-final">'
            f'<div style="font-size:3.5em">{emoji}</div>'
            f'<div style="font-size:1.8em;font-weight:bold;color:{couleur}">{mention}</div>'
            f'<div class="score-gros" style="color:{couleur}">{score} / {total}</div>'
            f'<div class="score-pct">{pct:.0f} % de bonnes réponses</div>'
            f'</div>', unsafe_allow_html=True)

        if st.session_state.joueur:
            infos = infos_joueur(st.session_state.joueur)
            st.markdown(
                f"<div style='text-align:center;color:#F5A623;margin-top:0.8em'>"
                f"🏅 Votre record : {infos['meilleur_score']:.0f} %</div>",
                unsafe_allow_html=True)

        st.markdown("")
        if st.button("🎮 Rejouer", use_container_width=True):
            st.session_state.page = "accueil"
            st.rerun()
        if st.button("🏆 Classement", use_container_width=True):
            st.session_state.page = "classement"
            st.rerun()
        if st.button("👤 Déconnexion", use_container_width=True):
            st.session_state.joueur = None
            st.session_state.page   = "login"
            st.rerun()

    with col2:
        st.markdown("### 🏆 Classement")
        df = classement(8)
        if df.empty:
            st.info("Aucun score enregistré.")
        else:
            medailles = {0: "🥇", 1: "🥈", 2: "🥉"}
            for i, row in df.iterrows():
                rang    = medailles.get(i, f"{i+1}.")
                est_moi = row["pseudo"].lower() == (st.session_state.joueur or "").lower()
                style   = "color:#F5A623;font-weight:bold" if est_moi else "color:#EAEAEA"
                st.markdown(
                    f'<div style="background:#16213E;padding:6px 12px;border-radius:6px;'
                    f'margin:3px 0;{style}">'
                    f'{rang}  {row["pseudo"]}  —  {float(row["meilleur_score"]):.0f} %'
                    f'</div>', unsafe_allow_html=True)


def page_classement():
    col_t, col_b = st.columns([3, 1])
    with col_t:
        st.markdown("## 🏆 Classement général")
    with col_b:
        if st.button("← Retour"):
            st.session_state.page = "accueil"
            st.rerun()

    df = classement(20)
    if df.empty:
        st.info("Aucun joueur enregistré pour l'instant.")
        return

    medailles = {0: "🥇", 1: "🥈", 2: "🥉"}
    header_cols = st.columns([1, 3, 2, 2, 2])
    for col, txt in zip(header_cols, ["Rang", "Pseudo", "Meilleur score", "Parties", "Dernière partie"]):
        col.markdown(f"**{txt}**")

    st.markdown("<hr style='margin:4px 0;border-color:#0F3460'>", unsafe_allow_html=True)

    for i, row in df.iterrows():
        rang    = medailles.get(i, f"{i+1}.")
        est_moi = row["pseudo"].lower() == (st.session_state.joueur or "").lower()
        style   = "color:#F5A623;font-weight:bold" if est_moi else "color:#EAEAEA"
        cols = st.columns([1, 3, 2, 2, 2])
        vals = [rang, row["pseudo"],
                f"{float(row['meilleur_score']):.0f} %",
                str(int(row["nb_parties"])),
                str(row.get("derniere_partie", "—") or "—")]
        for col, val in zip(cols, vals):
            col.markdown(f'<span style="{style}">{val}</span>', unsafe_allow_html=True)


# ── Point d'entrée ───────────────────────────────────────────────────

def main():
    st.set_page_config(page_title=TITRE_JEU, page_icon=PAGE_ICON, layout="centered")
    injecter_css()
    init_session()

    page = st.session_state.page
    if page == "login":
        page_login()
    elif page == "accueil":
        page_accueil()
    elif page == "jeu":
        page_jeu()
    elif page == "resultat":
        page_resultat()
    elif page == "classement":
        page_classement()


if __name__ == "__main__":
    main()
