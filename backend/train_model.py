import pandas as pd
import pickle
import re
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

print("=" * 50)
print("       FAKE NEWS DETECTOR - TRAINING")
print("=" * 50)

# Load
true_df = pd.read_csv("dataset/True.csv")
fake_df = pd.read_csv("dataset/Fake.csv")
print(f"Real news: {len(true_df)} articles")
print(f"Fake news: {len(fake_df)} articles")

true_df["label"] = 1
fake_df["label"] = 0

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

for df in [true_df, fake_df]:
    title = df["title"].fillna("") if "title" in df.columns else ""
    text  = df["text"].fillna("")  if "text"  in df.columns else ""
    df["combined"] = (title + " " + text).apply(clean_text)

data = pd.concat([true_df, fake_df])
data = data.sample(frac=1, random_state=42).reset_index(drop=True)
data = data.dropna(subset=["combined"])

X = data["combined"]
y = data["label"]
print(f"Total articles: {len(data)}")

vectorizer = TfidfVectorizer(
    stop_words="english",
    max_features=20000,
    ngram_range=(1, 1),
    max_df=0.7,
    min_df=2
)
X_vec = vectorizer.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_vec, y, test_size=0.2,
    random_state=42, stratify=y
)

print("\nTraining Naive Bayes...")
model_nb = MultinomialNB(alpha=0.1)
model_nb.fit(X_train, y_train)
acc_nb = accuracy_score(y_test, model_nb.predict(X_test))
print(f"Accuracy: {acc_nb*100:.2f}%")

print("Training Logistic Regression...")
model_lr = LogisticRegression(max_iter=1000, class_weight="balanced")
model_lr.fit(X_train, y_train)
acc_lr = accuracy_score(y_test, model_lr.predict(X_test))
print(f"Accuracy: {acc_lr*100:.2f}%")

print("Training Random Forest (2-3 mins)...")
model_rf = RandomForestClassifier(
    n_estimators=200, random_state=42, n_jobs=-1
)
model_rf.fit(X_train, y_train)
acc_rf = accuracy_score(y_test, model_rf.predict(X_test))
print(f"Accuracy: {acc_rf*100:.2f}%")

print("\n" + "="*50)
print("         FINAL ACCURACY REPORT")
print("="*50)
print(f"Naive Bayes:          {acc_nb*100:.2f}%")
print(f"Logistic Regression:  {acc_lr*100:.2f}%")
print(f"Random Forest:        {acc_rf*100:.2f}%")
print("="*50)
print(classification_report(
    y_test, model_lr.predict(X_test),
    target_names=["Fake News", "Real News"]
))

pickle.dump(vectorizer, open("vectorizer.pkl", "wb"))
pickle.dump(model_nb,   open("model_nb.pkl",   "wb"))
pickle.dump(model_lr,   open("model_lr.pkl",   "wb"))
pickle.dump(model_rf,   open("model_rf.pkl",   "wb"))
print("All models saved!")