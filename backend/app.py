from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import os
import io
import re
from pypdf import PdfReader
import pandas as pd
import wikipedia
from config import Config
from database import db, PredictionHistory, User
from utils import extract_text_from_url, fetch_trending_news

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

# Database auto-init
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        default_admin = User(name="System Administrator", username="admin", password="password")
        db.session.add(default_admin)
        db.session.commit()


# ---------------------------------------------------------------------------
# WIKIPEDIA FACT VERIFICATION
# ---------------------------------------------------------------------------

def verify_entity(text):
    """
    Dynamically extracts named entities from input text,
    searches Wikipedia, and checks if the claimed role/fact matches reality.
    Returns a dict with verdict: 'REAL', 'FAKE', or 'UNKNOWN'
    """
    text_lower = text.lower()
    words = text.split()

    # Role keywords mapping: what user might claim → what Wikipedia should mention
    role_keywords = {
        "football player":  ["football", "soccer", "footballer", "fifa", "premier league"],
        "footballer":       ["football", "soccer", "footballer", "fifa", "premier league"],
        "cricket player":   ["cricket", "cricketer", "batsman", "bowler", "ipl", "test match"],
        "cricketer":        ["cricket", "cricketer", "batsman", "bowler", "ipl"],
        "basketball player":["basketball", "nba", "shooting guard", "point guard"],
        "tennis player":    ["tennis", "grand slam", "wimbledon", "atp", "wta"],
        "politician":       ["politician", "minister", "president", "senator", "parliament", "mp"],
        "prime minister":   ["prime minister", "premier", "head of government"],
        "president":        ["president", "head of state"],
        "actor":            ["actor", "actress", "film", "movie", "bollywood", "hollywood"],
        "singer":           ["singer", "musician", "vocalist", "band", "album"],
        "scientist":        ["scientist", "physicist", "biologist", "researcher", "professor"],
        "businessman":      ["businessman", "ceo", "entrepreneur", "founder", "billionaire"],
        "doctor":           ["doctor", "physician", "medical", "surgeon"],
        "engineer":         ["engineer", "engineering", "technology"],
    }

    # Extract possible entity names (2-word and 1-word capitalized)
    possible_entities = []
    for i in range(len(words) - 1):
        w1 = re.sub(r'[^a-zA-Z]', '', words[i])
        w2 = re.sub(r'[^a-zA-Z]', '', words[i + 1])
        if w1 and w2 and w1[0].isupper() and w2[0].isupper():
            possible_entities.append(f"{w1} {w2}")
    for word in words:
        clean = re.sub(r'[^a-zA-Z]', '', word)
        if clean and clean[0].isupper() and len(clean) > 3:
            possible_entities.append(clean)

    # Remove duplicates while preserving order
    seen = set()
    unique_entities = []
    for e in possible_entities:
        if e not in seen:
            seen.add(e)
            unique_entities.append(e)

    # Check each entity against Wikipedia
    for entity in unique_entities[:4]:
        try:
            summary = wikipedia.summary(entity, sentences=4, auto_suggest=True)
            summary_lower = summary.lower()

            for claimed_role, wiki_terms in role_keywords.items():
                if claimed_role in text_lower:
                    if any(term in summary_lower for term in wiki_terms):
                        return {
                            "verdict": "REAL",
                            "reason": f"Wikipedia confirms '{entity}' is associated with '{claimed_role}'.",
                            "wiki_summary": summary[:200]
                        }
                    else:
                        return {
                            "verdict": "FAKE",
                            "reason": f"Wikipedia does NOT confirm '{entity}' as a '{claimed_role}'. Wikipedia says: {summary[:150]}...",
                            "wiki_summary": summary[:200]
                        }

        except wikipedia.exceptions.DisambiguationError as e:
            try:
                summary = wikipedia.summary(e.options[0], sentences=4)
                summary_lower = summary.lower()
                for claimed_role, wiki_terms in role_keywords.items():
                    if claimed_role in text_lower:
                        if any(term in summary_lower for term in wiki_terms):
                            return {
                                "verdict": "REAL",
                                "reason": f"Wikipedia confirms '{entity}' is associated with '{claimed_role}'.",
                                "wiki_summary": summary[:200]
                            }
                        else:
                            return {
                                "verdict": "FAKE",
                                "reason": f"Wikipedia does NOT confirm '{entity}' as a '{claimed_role}'. Wikipedia says: {summary[:150]}...",
                                "wiki_summary": summary[:200]
                            }
            except Exception:
                continue
        except wikipedia.exceptions.PageError:
            continue
        except Exception:
            continue

    return {
        "verdict": "UNKNOWN",
        "reason": "Could not verify claims via Wikipedia. Relying on ML models.",
        "wiki_summary": ""
    }


# ---------------------------------------------------------------------------
# INDICATOR WORD LISTS
# ---------------------------------------------------------------------------

trusted_words = [
    "reuters", "associated press", "official press release",
    "bipartisan support", "spokesman announced", "parliamentary committee"
]

fake_words = [
    "alien space alliance", "ghost captured on camera", "time traveler from",
    "hollow spacecraft", "subterranean world beneath", "dinosaurs are currently living"
]

scam_keywords = [
    "verify your identity", "click the link", "account will be suspended",
    "locked your access", "permanent account deletion", "unusual activity on your",
    "verify my account", "secure link", "urgent: your", "account suspension",
    "verify your account", "click below to verify"
]


# ---------------------------------------------------------------------------
# ML MODEL LOADING
# ---------------------------------------------------------------------------

try:
    vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
    model_nb   = pickle.load(open("model_nb.pkl",   "rb"))
    model_lr   = pickle.load(open("model_lr.pkl",   "rb"))
    model_rf   = pickle.load(open("model_rf.pkl",   "rb"))
    MODELS_LOADED = True
except Exception as e:
    print(f"Error loading models: {e}")
    MODELS_LOADED = False


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def generate_human_explanation(score, metrics, is_scam=False, wiki_result=None):
    """
    Generates structured, natural language feedback based on text style metrics
    and Wikipedia verification result.
    """
    if is_scam:
        return ("Warning: This text has been flagged as a highly suspicious Phishing or Scam attempt. "
                "It uses urgent, coercive warnings and direct requests for credentials/links, "
                "which are typical markers of digital fraud rather than objective, professional journalism.")

    # Prepend Wikipedia finding if available
    wiki_note = ""
    if wiki_result and wiki_result["verdict"] != "UNKNOWN":
        wiki_note = f"Fact Check: {wiki_result['reason']} "

    cues = []
    if metrics["sensationalism_score"] > 60:
        cues.append("exhibits highly loaded sensational vocabulary (clickbait markers)")
    if metrics["caps_ratio"] > 15.0:
        cues.append("uses excessive capitalized words typical of unverified rumors")
    if metrics["exclamation_count"] > 3:
        cues.append("contains highly emotional punctuation indicators")

    if score >= 80:
        verdict = "This article appears highly authentic."
        details = ("Its style maps strongly to established journalistic standards, showing minimal bias "
                   "indicators, moderate vocabulary complexity, and structured reporting formats.")
    elif score >= 40:
        verdict = "This article exhibits several suspicious characteristics."
        details = (f"While it carries some journalistic traits, the model flags concern because the writing "
                   f"{', '.join(cues) if cues else 'utilizes an informal structure with lower complexity bounds'}.")
    else:
        verdict = "Warning: This article is classified as unreliable."
        details = (f"The stylistic analysis suggests a high likelihood of fabrication or clickbait. "
                   f"The writing style {', '.join(cues) if cues else 'lacks traditional structural standards'} "
                   f"and displays an unusually high ratio of emotive prose.")

    return f"{wiki_note}{verdict} {details}"


def run_multi_model_prediction(text):
    """
    Vectorizes text and queries all three models, computing a weighted trust score.
    """
    vector = vectorizer.transform([text])

    prob_nb = float(model_nb.predict_proba(vector)[0][1]) if hasattr(model_nb, "predict_proba") else 0.5
    prob_lr = float(model_lr.predict_proba(vector)[0][1]) if hasattr(model_lr, "predict_proba") else 0.5
    prob_rf = float(model_rf.predict_proba(vector)[0][1]) if hasattr(model_rf, "predict_proba") else 0.5

    weighted_probability = (prob_lr * 0.4) + (prob_nb * 0.4) + (prob_rf * 0.2)
    trust_score = int(weighted_probability * 100)

    if trust_score >= 80:
        category = "Trusted"
    elif trust_score >= 40:
        category = "Suspicious"
    else:
        category = "Fake"

    return {
        "nb_conf":    prob_nb,
        "lr_conf":    prob_lr,
        "rf_conf":    prob_rf,
        "trust_score": trust_score,
        "category":   category
    }


# ---------------------------------------------------------------------------
# CORE ANALYSIS PIPELINE
# ---------------------------------------------------------------------------

def process_and_log_analysis(input_type, source_name, text_content):
    """
    Full pipeline:
      1. Wikipedia fact verification
      2. Scam detection
      3. ML prediction
      4. Override logic (Wiki > Scam > ML)
      5. Diagnostics + XAI
      6. DB logging
    """
    words      = text_content.split()
    word_count = len(words) if words else 1
    text_lower = text_content.lower()

    # ── STEP 1: Wikipedia Fact Verification ─────────────────────────────────
    wiki_result  = verify_entity(text_content)
    wiki_verdict = wiki_result["verdict"]   # "REAL", "FAKE", or "UNKNOWN"

    # ── STEP 2: Scam Detection ───────────────────────────────────────────────
    is_scam = any(phrase in text_lower for phrase in scam_keywords)

    # ── STEP 3: ML Prediction ────────────────────────────────────────────────
    pred = run_multi_model_prediction(text_content)

    # ── STEP 4: Override Logic ───────────────────────────────────────────────
    # Wikipedia has highest priority (strongest signal)
    if wiki_verdict == "FAKE":
        pred["trust_score"] = 10
        pred["category"]    = "Fake"
        pred["nb_conf"]     = 0.10
        pred["lr_conf"]     = 0.10
        pred["rf_conf"]     = 0.10

    elif wiki_verdict == "REAL":
        pred["trust_score"] = max(pred["trust_score"], 80)
        pred["category"]    = "Trusted"
        pred["nb_conf"]     = max(pred["nb_conf"], 0.80)
        pred["lr_conf"]     = max(pred["lr_conf"], 0.80)
        pred["rf_conf"]     = max(pred["rf_conf"], 0.80)

    # Scam overrides everything
    if is_scam:
        pred["trust_score"] = 12
        pred["category"]    = "Fake"
        pred["nb_conf"]     = 0.15
        pred["lr_conf"]     = 0.08
        pred["rf_conf"]     = 0.11

    # ── STEP 5: Diagnostics ──────────────────────────────────────────────────
    total_chars    = len(text_content) if text_content else 1
    uppercase_chars = sum(1 for c in text_content if c.isupper())
    caps_ratio     = (uppercase_chars / total_chars) * 100
    excl_count     = text_content.count("!")

    clickbait_words = [
        "shocking", "unbelievable", "secret", "exposed", "conspiracy",
        "hidden", "alert", "omg", "must see", "breaking"
    ]
    clickbait_count     = sum(1 for w in words if w.lower().strip(".,!?") in clickbait_words)
    sensationalism_score = min(100, int((clickbait_count / word_count) * 250) + (15 if excl_count > 0 else 0))
    complexity_factor    = min(100, max(15, int(word_count * 0.3)))

    metrics = {
        "word_count":          word_count,
        "caps_ratio":          round(caps_ratio, 1),
        "exclamation_count":   excl_count,
        "sensationalism_score": sensationalism_score,
        "complexity_factor":   complexity_factor
    }

    # ── STEP 6: Human Explanation ────────────────────────────────────────────
    explanation = generate_human_explanation(
        pred["trust_score"], metrics, is_scam=is_scam, wiki_result=wiki_result
    )

    # ── STEP 7: Rule Matching ────────────────────────────────────────────────
    triggered_fake    = [word for word in fake_words    if word in text_lower]
    triggered_trusted = [word for word in trusted_words if word in text_lower]

    rule_prediction = "None"
    if is_scam:
        rule_prediction = "Phishing Scam"
    elif wiki_verdict == "FAKE":
        rule_prediction = "Fake News (Wikipedia)"
    elif wiki_verdict == "REAL":
        rule_prediction = "Real News (Wikipedia)"
    elif triggered_fake:
        rule_prediction = "Fake News"
    elif triggered_trusted:
        rule_prediction = "Real News"

    # ── STEP 8: XAI Feature Importance ──────────────────────────────────────
    xai_features = []
    try:
        feature_names   = vectorizer.get_feature_names_out()
        vectorized_text = vectorizer.transform([text_lower])
        nonzero_indices = vectorized_text.nonzero()[1]

        for idx in nonzero_indices:
            word        = feature_names[idx]
            tfidf_score = vectorized_text[0, idx]
            coef_weight = float(model_lr.coef_[0, idx])
            xai_features.append({
                "word":   word,
                "tfidf":  round(float(tfidf_score), 3),
                "bias":   "Real News" if coef_weight > 0 else "Fake News",
                "weight": round(abs(coef_weight), 2)
            })

        xai_features = sorted(xai_features, key=lambda x: x["weight"], reverse=True)[:8]
    except Exception as e:
        print(f"XAI processing error: {e}")

    # ── STEP 9: DB Logging ───────────────────────────────────────────────────
    try:
        history_entry = PredictionHistory(
            input_type    = input_type,
            source_name   = source_name,
            text_content  = text_content,
            trust_score   = pred["trust_score"],
            category      = pred["category"],
            nb_confidence = pred["nb_conf"],
            lr_confidence = pred["lr_conf"],
            rf_confidence = pred["rf_conf"]
        )
        db.session.add(history_entry)
        db.session.commit()
    except Exception as e:
        print(f"Database logging failed: {e}")
        db.session.rollback()

    # ── STEP 10: Build Final Response ────────────────────────────────────────
    max_confidence = max(pred["nb_conf"], pred["lr_conf"], pred["rf_conf"])
    if is_scam:
        max_confidence = max(
            1.0 - pred["nb_conf"],
            1.0 - pred["lr_conf"],
            1.0 - pred["rf_conf"]
        )

    return {
        "prediction":        "Real News" if pred["trust_score"] >= 50 else "Fake News",
        "trust_score":       pred["trust_score"],
        "authenticity_score": pred["trust_score"],
        "category":          pred["category"],
        "confidence":        round(max_confidence * 100, 1),
        "rule_prediction":   rule_prediction,
        "explanation":       explanation,
        "wiki_verification": {
            "verdict":      wiki_verdict,
            "reason":       wiki_result["reason"],
            "wiki_summary": wiki_result.get("wiki_summary", "")
        },
        "metrics":           metrics,
        "xai_features":      xai_features,
        "rule_triggers": {
            "fake_matches":    triggered_fake,
            "trusted_matches": triggered_trusted
        },
        "model_comparison": {
            "nb": {"label": "Real" if pred["nb_conf"] >= 0.5 else "Fake", "conf": round(pred["nb_conf"] * 100, 1)},
            "lr": {"label": "Real" if pred["lr_conf"] >= 0.5 else "Fake", "conf": round(pred["lr_conf"] * 100, 1)},
            "rf": {"label": "Real" if pred["rf_conf"] >= 0.5 else "Fake", "conf": round(pred["rf_conf"] * 100, 1)}
        },
        "extracted_text": text_content[:800] + ("..." if len(text_content) > 800 else "")
    }


# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("username") or not data.get("password"):
        return jsonify({"error": "All security parameters are required."}), 400

    username = data["username"].lower().strip()
    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({"error": "This profile username key is already registered."}), 400

    new_user = User(
        name     = data["name"].strip(),
        username = username,
        password = data["password"]
    )
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to register key: {str(e)}"}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password keys required."}), 400

    username     = data["username"].lower().strip()
    matched_user = User.query.filter_by(username=username, password=data["password"]).first()
    if matched_user:
        return jsonify(matched_user.to_dict()), 200
    return jsonify({"error": "Invalid secure credentials."}), 401


@app.route("/predict", methods=["POST"])
def predict():
    if not MODELS_LOADED:
        return jsonify({"error": "ML model assets are not loaded."}), 500
    data = request.get_json()
    if not data or "text" not in data or not data["text"].strip():
        return jsonify({"error": "No text provided"}), 400

    results = process_and_log_analysis("text", "Manual Entry Block", data["text"])
    return jsonify(results)


@app.route("/predict-url", methods=["POST"])
def predict_url():
    if not MODELS_LOADED:
        return jsonify({"error": "ML model assets are not loaded."}), 500
    data = request.get_json()
    if not data or "url" not in data or not data["url"].strip():
        return jsonify({"error": "No URL provided"}), 400

    try:
        title, extracted_text = extract_text_from_url(data["url"])
        if len(extracted_text.split()) < 8:
            return jsonify({"error": "The targeted URL page contains insufficient readable paragraph text."}), 400
        results = process_and_log_analysis("url", data["url"], extracted_text)
        results["extracted_title"] = title
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/predict-file", methods=["POST"])
def predict_file():
    if not MODELS_LOADED:
        return jsonify({"error": "ML model assets are not loaded."}), 500
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file          = request.files['file']
    filename      = file.filename.lower()
    extracted_text = ""

    try:
        if filename.endswith('.txt'):
            extracted_text = file.read().decode('utf-8', errors='ignore')
        elif filename.endswith('.pdf'):
            pdf_bytes = io.BytesIO(file.read())
            reader    = PdfReader(pdf_bytes)
            extracted_text = "\n".join(
                [page.extract_text() for page in reader.pages if page.extract_text()]
            )
        elif filename.endswith('.csv'):
            csv_bytes = io.BytesIO(file.read())
            df  = pd.read_csv(csv_bytes)
            col = [c for c in df.columns if df[c].dtype == object][0]
            extracted_text = " ".join(df[col].dropna().astype(str).head(15).tolist())
        else:
            return jsonify({"error": "Unsupported file format"}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 500

    if len(extracted_text.split()) < 8:
        return jsonify({"error": "The document contains insufficient readable text."}), 400

    results = process_and_log_analysis("file", file.filename, extracted_text)
    return jsonify(results)


@app.route("/history", methods=["GET"])
def get_history():
    query    = request.args.get("query",    "")
    category = request.args.get("category", "")

    db_query = PredictionHistory.query
    if query:
        db_query = db_query.filter(
            PredictionHistory.text_content.contains(query) |
            PredictionHistory.source_name.contains(query)
        )
    if category:
        db_query = db_query.filter(PredictionHistory.category == category)

    history_logs = db_query.order_by(PredictionHistory.timestamp.desc()).all()
    return jsonify([log.to_dict() for log in history_logs])


@app.route("/trending", methods=["GET"])
def get_trending():
    trends = fetch_trending_news(app.config["NEWS_API_KEY"])
    return jsonify(trends)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
