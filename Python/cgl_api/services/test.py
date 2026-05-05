import re
import numpy as np
import networkx as nx

from dataclasses import dataclass
from typing import List, Dict, Tuple

from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer


# ----------------------------
# 1) Weak-signal feature extraction
# ----------------------------

MONEY_RE = re.compile(r"(\$\s?\d[\d,]*)|(\d[\d,]*\s?(usd|dollars?))|(million|thousand|k\b)", re.I)
NUMBER_RE = re.compile(r"\b\d[\d,]*\b")
VS_RE = re.compile(r"\b(vs\.?|versus)\b", re.I)
QUESTION_START_RE = re.compile(r"^\s*(would|can|could|should|why|how|what|who|is|are|do|does|did)\b", re.I)

REWARD_WORDS = {"win", "wins", "prize", "keep", "get", "reward", "paid", "pay", "giving", "gave", "gift", "gifts"}
RISK_WORDS = {"risk", "dying", "die", "survive", "trapped", "lava", "danger", "deadly"}
TIME_WORDS = {"day", "days", "hour", "hours", "week", "weeks", "minute", "minutes", "year", "years"}
FIRST_PERSON = {"i", "i'm", "im", "me", "my", "mine", "we", "our", "us"}
CHALLENGE_WORDS = {"first", "to", "answer", "call", "jump", "beat", "stop", "fight", "pull", "hold", "race", "raced"}

IMPERATIVE_HINT_VERBS = {
    "answer", "call", "find", "survive", "jump", "hit", "keep", "flip", "beat", "stop", "race", "pull", "give", "save",
}

def tokenize_simple(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+|\d[\d,]*|\$|\?", text.lower())

def extract_weak_features(text: str) -> Dict[str, float]:
    t = text.strip()
    tokens = tokenize_simple(t)

    has_money = 1.0 if MONEY_RE.search(t) else 0.0
    has_number = 1.0 if NUMBER_RE.search(t) else 0.0
    has_vs = 1.0 if VS_RE.search(t) else 0.0
    has_qmark = 1.0 if "?" in t else 0.0
    question_start = 1.0 if QUESTION_START_RE.search(t) else 0.0

    reward_hits = sum(1 for w in tokens if w in REWARD_WORDS)
    risk_hits = sum(1 for w in tokens if w in RISK_WORDS)
    time_hits = sum(1 for w in tokens if w in TIME_WORDS)
    fp_hits = sum(1 for w in tokens if w in FIRST_PERSON)
    chall_hits = sum(1 for w in tokens if w in CHALLENGE_WORDS)

    imperative = 1.0 if (len(tokens) > 0 and tokens[0] in IMPERATIVE_HINT_VERBS) else 0.0

    length_tokens = float(len(tokens))
    commas = float(t.count(","))
    excls = float(t.count("!"))
    caps_ratio = (sum(1 for c in t if c.isupper()) / max(1, sum(1 for c in t if c.isalpha())))

    def norm_count(x):
        return min(1.0, x / 3.0)

    return {
        "has_money": has_money,
        "has_number": has_number,
        "has_vs": has_vs,
        "has_qmark": has_qmark,
        "question_start": question_start,
        "imperative_start": imperative,

        "reward_lex": norm_count(reward_hits),
        "risk_lex": norm_count(risk_hits),
        "time_lex": norm_count(time_hits),
        "first_person_lex": norm_count(fp_hits),
        "challenge_lex": norm_count(chall_hits),

        "len_tokens": min(1.0, length_tokens / 20.0),
        "commas": min(1.0, commas / 2.0),
        "excls": min(1.0, excls / 2.0),
        "caps_ratio": float(caps_ratio),
    }

def build_feature_matrix(sentences: List[str]) -> Tuple[np.ndarray, List[str]]:
    feat_dicts = [extract_weak_features(s) for s in sentences]
    keys = sorted(feat_dicts[0].keys())
    X = np.array([[fd[k] for k in keys] for fd in feat_dicts], dtype=np.float32)
    return X, keys


# ----------------------------
# 2) Representation for pattern discovery: TF-IDF + Weak features (NON-NEGATIVE)
# ----------------------------

@dataclass
class JointConfig:
    model_name: str = "all-MiniLM-L6-v2"
    tfidf_dim: int = 256
    tfidf_weight: float = 0.60
    feat_weight: float = 0.40

def build_pattern_matrix(sentences: List[str], cfg: JointConfig) -> Tuple[np.ndarray, Dict]:
    vectorizer = TfidfVectorizer(
        max_features=cfg.tfidf_dim,
        ngram_range=(1, 2),
        lowercase=True,
        stop_words="english"
    )
    T = vectorizer.fit_transform(sentences).toarray().astype(np.float32)
    T = normalize(T)  # non-negative, but normalize may introduce tiny float noise

    F, feat_names = build_feature_matrix(sentences)
    F = normalize(F)

    Tw = T * cfg.tfidf_weight
    Fw = F * cfg.feat_weight

    X = np.concatenate([Tw, Fw], axis=1).astype(np.float32)

    # Guard against tiny numerical negatives (e.g., -1e-12)
    X[X < 0] = 0.0

    meta = {
        "vectorizer": vectorizer,
        "feat_names": feat_names,
        "T_dim": T.shape[1],
        "F_dim": F.shape[1],
    }
    return X, meta


# ----------------------------
# 3) Unsupervised pattern discovery using NMF
# ----------------------------

@dataclass
class PatternConfig:
    n_patterns: int = 6
    top_sentences: int = 7
    top_features: int = 10

def discover_patterns_nmf(X: np.ndarray, meta: Dict, pcfg: PatternConfig):
    nmf = NMF(
        n_components=pcfg.n_patterns,
        init="nndsvda",
        random_state=42,
        max_iter=1000
    )
    W = nmf.fit_transform(X)
    H = nmf.components_

    T_dim, F_dim = meta["T_dim"], meta["F_dim"]
    tfidf_vocab = meta["vectorizer"].get_feature_names_out().tolist()
    feat_names = meta["feat_names"]

    def top_contributors_for_pattern(k: int):
        hk = H[k]

        hk_tfidf = hk[:T_dim]
        hk_feats = hk[T_dim:T_dim + F_dim]

        top_tfidf_idx = np.argsort(hk_tfidf)[::-1][: pcfg.top_features]
        top_feat_idx = np.argsort(hk_feats)[::-1][: pcfg.top_features]

        tfidf_terms = [(tfidf_vocab[i], float(hk_tfidf[i])) for i in top_tfidf_idx]
        weak_feats = [(feat_names[i], float(hk_feats[i])) for i in top_feat_idx]
        return tfidf_terms, weak_feats

    return W, H, top_contributors_for_pattern


# ----------------------------
# 4) Optional: semantic subclustering inside each discovered pattern (kNN graph on embeddings)
# ----------------------------

def knn_graph_clusters(emb: np.ndarray, k: int = 6, sim_threshold: float = 0.55):
    n = emb.shape[0]
    sims = emb @ emb.T
    np.fill_diagonal(sims, -1.0)

    G = nx.Graph()
    G.add_nodes_from(range(n))

    for i in range(n):
        nbrs = np.argsort(sims[i])[::-1][:k]
        for j in nbrs:
            if sims[i, j] >= sim_threshold:
                G.add_edge(i, j, weight=float(sims[i, j]))

    comps = list(nx.connected_components(G))
    comps = sorted(comps, key=lambda c: len(c), reverse=True)
    return comps


# ----------------------------
# 5) Main
# ----------------------------

def run_pattern_discovery(sentences: List[str]):
    cfg = JointConfig()
    X, meta = build_pattern_matrix(sentences, cfg)

    pcfg = PatternConfig(n_patterns=6, top_sentences=6, top_features=8)
    W, H, top_contrib = discover_patterns_nmf(X, meta, pcfg)

    print("\n=== DISCOVERED PATTERNS (NMF FACTORS) ===")
    for k in range(pcfg.n_patterns):
        idx = np.argsort(W[:, k])[::-1][: pcfg.top_sentences]
        strength = W[idx, k]

        tfidf_terms, weak_feats = top_contrib(k)

        print(f"\nPATTERN #{k+1}")
        print("  Top contributing TF-IDF terms:")
        print("   ", ", ".join([f"{t}" for t, _ in tfidf_terms[:6]]))

        print("  Top contributing weak features:")
        print("   ", ", ".join([f"{f}" for f, _ in weak_feats[:6]]))

        print("  Top sentences:")
        for i, sc in zip(idx, strength):
            print(f"   - ({sc:.3f}) {sentences[i]}")

    # Optional semantic refinement
    model = SentenceTransformer(cfg.model_name)
    E = model.encode(sentences, normalize_embeddings=True)

    assign = np.argmax(W, axis=1)

    print("\n=== WITHIN-PATTERN SEMANTIC SUBCLUSTERS (kNN components) ===")
    for k in range(pcfg.n_patterns):
        members = np.where(assign == k)[0]
        if len(members) < 3:
            continue

        subE = E[members]
        comps = knn_graph_clusters(subE, k=5, sim_threshold=0.55)

        if len(comps) <= 1:
            continue

        print(f"\nPATTERN #{k+1} has {len(members)} items → {len(comps)} subclusters")
        for ci, comp in enumerate(comps[:4], start=1):
            if len(comp) < 2:
                continue
            print(f"  Subcluster {ci} ({len(comp)} items):")
            for local_idx in comp:
                original_idx = members[local_idx]
                print(f"    - {sentences[original_idx]}")


if __name__ == "__main__":
    sentences = [
        "Giving Away $1,000,000 in Gifts To My Subscribers",
        "Survive 30 Days Trapped In The Sky, Win $250,000",
        "Find The Real Celebrity, Win $10,000",
        "Would You Date Him for $10,000?",
        "How Many People to Pull a Plane?",
        "100 Pilots Fight For A Private Jet",
        "Hit The Target, Keep The Prize",
        "Whatever You Hold Onto, You Keep",
        "Flip a Coin, I’ll Pay For Your College",
        "World's Fastest Man Vs Robot!",
        "I Surprised 50 Make-A-Wish Kids With Disneyland",
        "Can I Beat An F1 Driver?",
        "I Raced Noah Lyles",
        "100 People Vs World’s Biggest Trap!",
        "First to Answer the Phone, Wins $10,000",
        "Answer The Door, Win $10,000",
        "Call Your Ex, Win $10,000",
        "Would You Risk Dying For $500,000?",
        "Would Your Grandma Go Skydiving?",
    ]

    run_pattern_discovery(sentences)
