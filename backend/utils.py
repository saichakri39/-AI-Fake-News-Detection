import requests
from bs4 import BeautifulSoup
import re

def extract_text_from_url(url):
    """
    Extracts article title and clean body text from a webpage, bypassing standard boilerplate.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script, style, and navigation tags
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
            
        title = soup.find('h1')
        title_text = title.get_text().strip() if title else "Extracted Article URL"
        
        # Capture text within main content blocks or paragraphs
        paragraphs = soup.find_all('p')
        body_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        
        return title_text, body_text
    except Exception as e:
        raise Exception(f"Failed to extract content from webpage: {str(e)}")

def fetch_trending_news(api_key):
    """
    Queries NewsAPI with a safe backup of mock trends if no key is configured.
    """
    if not api_key:
        return [
            {
                "title": "Global Climate Committee Announces Bipartisan Ocean Satellite Tracker",
                "description": "Scientists from international agencies confirmed the deployment of advanced ocean scanning technologies.",
                "url": "https://example.com/climate-mission",
                "publishedAt": "2026-05-28T10:00:00Z"
            },
            {
                "title": "Cricket Federation Declares Official Match Schedule for Upcoming Tournament",
                "description": "BCCI releases structural planning coordinates for upcoming IPL matches across ten major venues.",
                "url": "https://example.com/cricket-ipl",
                "publishedAt": "2026-05-28T09:30:00Z"
            }
        ]
    
    try:
        url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            # Filter out deleted articles
            return [a for a in articles if a.get("title") and "[Removed]" not in a.get("title")][:10]
    except Exception:
        pass
    return []

def generate_human_explanation(score, metrics):
    """
    Generates structured, natural language feedback based on text style metrics.
    """
    cues = []
    if metrics["sensationalism_score"] > 60:
        cues.append("exhibits highly loaded sensational vocabulary (clickbait markers)")
    if metrics["caps_ratio"] > 15.0:
        cues.append("uses excessive capitalized words typical of unverified rumors")
    if metrics["exclamation_count"] > 3:
        cues.append("contains highly emotional punctuation indicators")
        
    if score >= 80:
        verdict = "This article appears highly authentic."
        details = "Its style maps strongly to established journalistic standards, showing minimal bias indicators, moderate vocabulary complexity, and structured reporting formats."
    elif score >= 40:
        verdict = "This article exhibits several suspicious characteristics."
        details = f"While it carries some journalistic traits, the model flags concern because the writing {', '.join(cues) if cues else 'utilizes an informal structure with lower complexity bounds'}."
    else:
        verdict = "Warning: This article is classified as unreliable."
        details = f"The stylistic analysis suggests a high likelihood of fabrication or clickbait. The writing style {', '.join(cues) if cues else 'lacks traditional structural standards'} and displays an unusually high ratio of emotive prose."
        
    return f"{verdict} {details}"