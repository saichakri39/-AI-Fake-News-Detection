from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import os
import io
import re
import requests
from pypdf import PdfReader
import pandas as pd
import wikipedia
from config import Config
from database import db, PredictionHistory, User
from utils import extract_text_from_url, fetch_trending_news

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/*": {"origins": "*"}})
db.init_app(app)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        default_admin = User(
            name="System Administrator",
            username="admin",
            password="password"
        )
        db.session.add(default_admin)
        db.session.commit()

# ── NEWSAPI KEY ──────────────────────────────────────────────────────────────
NEWS_API_KEY = "51587f1b10334e0abf9b6b2b25c65ea4"

# ── INDICATOR LISTS ──────────────────────────────────────────────────────────
trusted_words = [
    "reuters", "associated press", "official press release",
    "bipartisan support", "spokesman announced", "parliamentary committee"
]
fake_words = [
    "alien space alliance", "ghost captured on camera",
    "time traveler from", "hollow spacecraft",
    "subterranean world beneath", "dinosaurs are currently living"
]
scam_keywords = [
    "verify your identity", "click the link",
    "account will be suspended", "locked your access",
    "permanent account deletion", "unusual activity on your",
    "verify my account", "secure link", "urgent: your",
    "account suspension", "verify your account",
    "click below to verify"
]

# ── LOAD MODELS ──────────────────────────────────────────────────────────────
try:
    vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
    model_nb   = pickle.load(open("model_nb.pkl",   "rb"))
    model_lr   = pickle.load(open("model_lr.pkl",   "rb"))
    model_rf   = pickle.load(open("model_rf.pkl",   "rb"))
    MODELS_LOADED = True
    print("Models loaded successfully!")
except Exception as e:
    print(f"Error loading models: {e}")
    MODELS_LOADED = False


# ── VERIFICATION 1: WIKIPEDIA ────────────────────────────────────────────────
def verify_entity(text):
    text_lower = text.lower()
    words      = text.split()

    role_keywords = {
        "football player":   ["football", "soccer", "footballer", "fifa"],
        "footballer":        ["football", "soccer", "footballer", "fifa"],
        "cricket player":    ["cricket", "cricketer", "batsman", "bowler", "ipl"],
        "cricketer":         ["cricket", "cricketer", "batsman", "bowler"],
        "basketball player": ["basketball", "nba"],
        "tennis player":     ["tennis", "grand slam", "wimbledon", "atp", "wta"],
        "politician":        ["politician", "minister", "president", "parliament"],
        "prime minister":    ["prime minister", "premier"],
        "president":         ["president", "head of state"],
        "actor":             ["actor", "actress", "film", "movie", "bollywood"],
        "singer":            ["singer", "musician", "vocalist", "album"],
        "scientist":         ["scientist", "physicist", "researcher", "professor"],
        "businessman":       ["businessman", "ceo", "entrepreneur", "founder"],
    }

    possible_entities = []
    for i in range(len(words) - 1):
        w1 = re.sub(r'[^a-zA-Z]', '', words[i])
        w2 = re.sub(r'[^a-zA-Z]', '', words[i+1])
        if w1 and w2 and w1[0].isupper() and w2[0].isupper():
            possible_entities.append(f"{w1} {w2}")
    for word in words:
        clean = re.sub(r'[^a-zA-Z]', '', word)
        if clean and clean[0].isupper() and len(clean) > 3:
            possible_entities.append(clean)

    seen = set()
    unique_entities = []
    for e in possible_entities:
        if e not in seen:
            seen.add(e)
            unique_entities.append(e)

    for entity in unique_entities[:4]:
        try:
            summary      = wikipedia.summary(entity, sentences=4, auto_suggest=True)
            summary_lower = summary.lower()

            for claimed_role, wiki_terms in role_keywords.items():
                if claimed_role in text_lower:
                    if any(term in summary_lower for term in wiki_terms):
                        return {
                            "verdict": "REAL",
                            "reason":  f"Wikipedia confirms '{entity}' is '{claimed_role}'",
                            "wiki_summary": summary[:200]
                        }
                    else:
                        return {
                            "verdict": "FAKE",
                            "reason":  f"Wikipedia says '{entity}' is NOT a '{claimed_role}'. Actually: {summary[:120]}",
                            "wiki_summary": summary[:200]
                        }
        except wikipedia.exceptions.DisambiguationError as e:
            try:
                summary       = wikipedia.summary(e.options[0], sentences=4)
                summary_lower = summary.lower()
                for claimed_role, wiki_terms in role_keywords.items():
                    if claimed_role in text_lower:
                        if any(term in summary_lower for term in wiki_terms):
                            return {"verdict": "REAL", "reason": f"Wikipedia confirms '{entity}'", "wiki_summary": summary[:200]}
                        else:
                            return {"verdict": "FAKE", "reason": f"Role mismatch for '{entity}': {summary[:120]}", "wiki_summary": summary[:200]}
            except Exception:
                continue
        except Exception:
            continue

    return {
        "verdict": "UNKNOWN",
        "reason":  "Could not verify via Wikipedia",
        "wiki_summary": ""
    }


# ── VERIFICATION 2: NEWSAPI ──────────────────────────────────────────────────
def newsapi_fact_check(text):
    """
    Searches NewsAPI for the same news headline/topic.
    If found in trusted sources → REAL
    If not found at all → suspicious
    """
    try:
        # Take first 10 words as search query
        query = " ".join(text.split()[:10])

        url = "https://newsapi.org/v2/everything"
        params = {
            "q":        query,
            "apiKey":   NEWS_API_KEY,
            "language": "en",
            "pageSize": 5,
            "sortBy":   "relevancy"
        }

        response = requests.get(url, params=params, timeout=5)
        data     = response.json()

        trusted_sources = [
            "reuters", "bbc", "associated press", "the hindu",
            "ndtv", "times of india", "cnn", "bloomberg",
            "guardian", "washington post", "ap news"
        ]

        if data.get("totalResults", 0) > 0:
            articles = data.get("articles", [])
            for article in articles:
                source = article.get("source", {}).get("name", "").lower()
                if any(t in source for t in trusted_sources):
                    return {
                        "verdict": "REAL",
                        "reason":  f"Found in trusted source: {article['source']['name']}",
                        "source":  article["source"]["name"]
                    }
            return {
                "verdict": "UNKNOWN",
                "reason":  "Found in news but not from trusted sources",
                "source":  "Unknown"
            }
        else:
            return {
                "verdict": "UNKNOWN",
                "reason":  "News not found in any source",
                "source":  "None"
            }

    except Exception as e:
        return {
            "verdict": "UNKNOWN",
            "reason":  f"NewsAPI check failed: {str(e)}",
            "source":  "None"
        }


# ── ML PREDICTION ────────────────────────────────────────────────────────────
def generate_human_explanation(score, metrics, is_scam=False, wiki_result=None, news_result=None):
    if is_scam:
        return ("Warning: Phishing/Scam detected. Uses urgent coercive language "
                "typical of digital fraud.")

    wiki_note = ""
    news_note = ""
    if wiki_result and wiki_result["verdict"] != "UNKNOWN":
        wiki_note = f"Wikipedia: {wiki_result['reason']}. "
    if news_result and news_result["verdict"] != "UNKNOWN":
        news_note = f"NewsAPI: {news_result['reason']}. "

    cues = []
    if metrics["sensationalism_score"] > 60:
        cues.append("highly sensational vocabulary")
    if metrics["caps_ratio"] > 15.0:
        cues.append("excessive capitalization")
    if metrics["exclamation_count"] > 3:
        cues.append("emotional punctuation")

    if score >= 80:
        verdict = "This article appears highly authentic."
        details = "Writing style matches established journalistic standards."
    elif score >= 40:
        verdict = "This article has suspicious characteristics."
        details = f"Flags: {', '.join(cues) if cues else 'informal structure'}."
    else:
        verdict = "Warning: Classified as unreliable."
        details = f"High likelihood of fabrication. {', '.join(cues) if cues else 'Lacks structural standards'}."

    return f"{wiki_note}{news_note}{verdict} {details}"


def run_multi_model_prediction(text):
    vector = vectorizer.transform([text])

    prob_nb = float(model_nb.predict_proba(vector)[0][1]) if hasattr(model_nb, "predict_proba") else 0.5
    prob_lr = float(model_lr.predict_proba(vector)[0][1]) if hasattr(model_lr, "predict_proba") else 0.5
    prob_rf = float(model_rf.predict_proba(vector)[0][1]) if hasattr(model_rf, "predict_proba") else 0.5

    weighted = (prob_lr * 0.4) + (prob_nb * 0.4) + (prob_rf * 0.2)
    trust_score = int(weighted * 100)

    if trust_score >= 80:   category = "Trusted"
    elif trust_score >= 40: category = "Suspicious"
    else:                   category = "Fake"

    return {
        "nb_conf": prob_nb, "lr_conf": prob_lr,
        "rf_conf": prob_rf, "trust_score": trust_score,
        "category": category
    }


# ── CORE PIPELINE ────────────────────────────────────────────────────────────
def process_and_log_analysis(input_type, source_name, text_content):
    words      = text_content.split()
    word_count = len(words) if words else 1
    text_lower = text_content.lower()

    # STEP 1: Wikipedia
    wiki_result  = verify_entity(text_content)
    wiki_verdict = wiki_result["verdict"]

    # STEP 2: NewsAPI
    news_result  = newsapi_fact_check(text_content)
    news_verdict = news_result["verdict"]

    # STEP 3: Scam check
    is_scam = any(phrase in text_lower for phrase in scam_keywords)

    # STEP 4: ML prediction
    pred = run_multi_model_prediction(text_content)

    # STEP 5: Final decision (priority order)
    #
    # NewsAPI REAL    → 95% trust (trusted source confirmed)
    # Wikipedia FAKE  → 10% trust (fact mismatch)
    # Wikipedia REAL  → boost to 80%
    # Scam            → 12% trust (always override)
    # ML model        → fallback
    #
    if news_verdict == "REAL":
        pred["trust_score"] = 95
        pred["category"]    = "Trusted"

    if wiki_verdict == "FAKE":
        pred["trust_score"] = 10
        pred["category"]    = "Fake"

    elif wiki_verdict == "REAL" and news_verdict != "REAL":
        pred["trust_score"] = max(pred["trust_score"], 80)
        pred["category"]    = "Trusted"

    if is_scam:
        pred["trust_score"] = 12
        pred["category"]    = "Fake"
        pred["nb_conf"]     = 0.15
        pred["lr_conf"]     = 0.08
        pred["rf_conf"]     = 0.11

    # STEP 6: Diagnostics
    total_chars     = len(text_content) if text_content else 1
    uppercase_chars = sum(1 for c in text_content if c.isupper())
    caps_ratio      = (uppercase_chars / total_chars) * 100
    excl_count      = text_content.count("!")

    clickbait_words = [
        "shocking", "unbelievable", "secret", "exposed",
        "conspiracy", "hidden", "alert", "omg", "must see", "breaking"
    ]
    clickbait_count      = sum(1 for w in words if w.lower().strip(".,!?") in clickbait_words)
    sensationalism_score = min(100, int((clickbait_count / word_count) * 250) + (15 if excl_count > 0 else 0))
    complexity_factor    = min(100, max(15, int(word_count * 0.3)))

    metrics = {
        "word_count":           word_count,
        "caps_ratio":           round(caps_ratio, 1),
        "exclamation_count":    excl_count,
        "sensationalism_score": sensationalism_score,
        "complexity_factor":    complexity_factor
    }

    explanation = generate_human_explanation(
        pred["trust_score"], metrics,
        is_scam=is_scam,
        wiki_result=wiki_result,
        news_result=news_result
    )

    triggered_fake    = [w for w in fake_words    if w in text_lower]
    triggered_trusted = [w for w in trusted_words if w in text_lower]

    rule_prediction = "None"
    if is_scam:              rule_prediction = "Phishing Scam"
    elif wiki_verdict == "FAKE": rule_prediction = "Fake News (Wikipedia)"
    elif wiki_verdict == "REAL": rule_prediction = "Real News (Wikipedia)"
    elif news_verdict == "REAL": rule_prediction = "Real News (NewsAPI)"
    elif triggered_fake:     rule_prediction = "Fake News"
    elif triggered_trusted:  rule_prediction = "Real News"

    # XAI
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
        print(f"XAI error: {e}")

    # DB log
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
        print(f"DB error: {e}")
        db.session.rollback()

    max_confidence = max(pred["nb_conf"], pred["lr_conf"], pred["rf_conf"])
    if is_scam:
        max_confidence = max(
            1.0 - pred["nb_conf"],
            1.0 - pred["lr_conf"],
            1.0 - pred["rf_conf"]
        )

    return {
        "prediction":         "Real News" if pred["trust_score"] >= 50 else "Fake News",
        "trust_score":        pred["trust_score"],
        "authenticity_score": pred["trust_score"],
        "category":           pred["category"],
        "confidence":         round(max_confidence * 100, 1),
        "rule_prediction":    rule_prediction,
        "explanation":        explanation,
        "wiki_verification": {
            "verdict":      wiki_verdict,
            "reason":       wiki_result["reason"],
            "wiki_summary": wiki_result.get("wiki_summary", "")
        },
        "news_verification": {
            "verdict": news_verdict,
            "reason":  news_result["reason"],
            "source":  news_result.get("source", "")
        },
        "metrics":      metrics,
        "xai_features": xai_features,
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


# ── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("username") or not data.get("password"):
        return jsonify({"error": "All fields required."}), 400
    username = data["username"].lower().strip()
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists."}), 400
    new_user = User(name=data["name"].strip(), username=username, password=data["password"])
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password required."}), 400
    username = data["username"].lower().strip()
    user = User.query.filter_by(username=username, password=data["password"]).first()
    if user:
        return jsonify(user.to_dict()), 200
    return jsonify({"error": "Invalid credentials."}), 401


@app.route("/predict", methods=["POST"])
def predict():
    if not MODELS_LOADED:
        return jsonify({"error": "ML models not loaded."}), 500
    data = request.get_json()
    if not data or "text" not in data or not data["text"].strip():
        return jsonify({"error": "No text provided"}), 400
    results = process_and_log_analysis("text", "Manual Entry", data["text"])
    return jsonify(results)


@app.route("/predict-url", methods=["POST"])
def predict_url():
    if not MODELS_LOADED:
        return jsonify({"error": "ML models not loaded."}), 500
    data = request.get_json()
    if not data or "url" not in data or not data["url"].strip():
        return jsonify({"error": "No URL provided"}), 400
    try:
        title, extracted_text = extract_text_from_url(data["url"])
        if len(extracted_text.split()) < 8:
            return jsonify({"error": "Insufficient text from URL."}), 400
        results = process_and_log_analysis("url", data["url"], extracted_text)
        results["extracted_title"] = title
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/predict-file", methods=["POST"])
def predict_file():
    if not MODELS_LOADED:
        return jsonify({"error": "ML models not loaded."}), 500
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file     = request.files['file']
    filename = file.filename.lower()
    extracted_text = ""
    try:
        if filename.endswith('.txt'):
            extracted_text = file.read().decode('utf-8', errors='ignore')
        elif filename.endswith('.pdf'):
            pdf_bytes = io.BytesIO(file.read())
            reader    = PdfReader(pdf_bytes)
            extracted_text = "\n".join(
                [p.extract_text() for p in reader.pages if p.extract_text()]
            )
        elif filename.endswith('.csv'):
            csv_bytes = io.BytesIO(file.read())
            df  = pd.read_csv(csv_bytes)
            col = [c for c in df.columns if df[c].dtype == object][0]
            extracted_text = " ".join(df[col].dropna().astype(str).head(15).tolist())
        else:
            return jsonify({"error": "Unsupported format"}), 400
    except Exception as e:
        return jsonify({"error": f"File parse error: {str(e)}"}), 500
    if len(extracted_text.split()) < 8:
        return jsonify({"error": "Insufficient text in document."}), 400
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
    logs = db_query.order_by(PredictionHistory.timestamp.desc()).all()
    return jsonify([log.to_dict() for log in logs])


@app.route("/trending", methods=["GET"])
def get_trending():
    trends = fetch_trending_news(app.config["NEWS_API_KEY"])
    return jsonify(trends)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)