"""Sentiment analysis using VADER + custom financial lexicon."""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from project.news.fetcher import NewsItem

# Custom financial lexicon: word → sentiment score (-4.0 to +4.0)
FINANCIAL_LEXICON = {
    # Strong positive
    "buyback": 3.5, "share buyback": 3.5, "bonus": 3.0, "dividend": 2.5,
    "upgrade": 3.0, "upgraded": 3.0, "outperform": 3.0, "overweight": 2.5,
    "bullish": 3.0, "rally": 2.5, "breakout": 2.8, "surge": 2.5,
    "soar": 3.0, "soaring": 3.0, "skyrocket": 3.5, "boom": 3.0,
    "record high": 3.0, "all time high": 3.0, "52 week high": 2.5,
    "strong buy": 3.5, "accumulate": 2.5, "multibagger": 3.5,
    "fda approval": 3.5, "approval": 2.0, "order win": 3.0,
    "order book": 2.5, "contract win": 3.0, "contract": 2.0,
    "beat estimate": 2.5, "beats estimate": 2.5, "better than expected": 2.5,
    "profit surge": 3.0, "revenue growth": 2.5, "profit growth": 2.5,
    "strong results": 2.5, "robust": 2.0, "stellar": 2.5,
    "expansion": 2.0, "capex": 1.5, "growth": 1.5,
    "acquisition": 1.5, "merger": 1.5, "partnership": 1.5,
    "deal": 1.5, "mou signed": 2.0, "collaboration": 1.5,
    "fii buying": 2.5, "dii buying": 2.0, "institutional buying": 2.5,
    "block deal": 1.5, "bulk deal": 1.5, "stake increase": 2.0,
    "promoter buying": 2.5, "insider buying": 2.5,
    "rate cut": 2.0, "stimulus": 2.0, "reform": 1.5,
    "government order": 2.5, "defence order": 3.0, "defense order": 3.0,
    "railway order": 2.5, "export order": 2.0,
    "short squeeze": 2.5, "short covering": 2.0,
    "turnaround": 2.5, "recovery": 2.0, "rebound": 2.0,

    # Mild positive
    "invest": 1.0, "opportunity": 1.0, "positive": 1.0,
    "stable": 0.5, "steady": 0.5, "resilient": 1.0,

    # Strong negative
    "downgrade": -3.0, "downgraded": -3.0, "underperform": -2.5,
    "underweight": -2.5, "sell": -2.0, "strong sell": -3.0,
    "crash": -3.5, "plunge": -3.0, "tank": -3.0, "tanking": -3.0,
    "bearish": -2.5, "correction": -2.0, "collapse": -3.5,
    "fraud": -4.0, "scam": -4.0, "default": -3.5, "bankruptcy": -4.0,
    "debt trap": -3.0, "npa": -2.5, "bad loan": -2.5,
    "loss widened": -2.5, "profit declined": -2.0, "revenue fell": -2.0,
    "miss estimate": -2.0, "missed estimate": -2.0, "below estimate": -2.0,
    "worse than expected": -2.5, "disappointing": -2.0,
    "rate hike": -1.5, "inflation": -1.0, "recession": -2.5,
    "sebi penalty": -2.5, "sebi ban": -3.0, "regulatory action": -2.0,
    "investigation": -2.0, "probe": -2.0, "raid": -2.5,
    "delisting": -3.0, "suspended": -3.0,
    "fii selling": -2.5, "dii selling": -2.0, "institutional selling": -2.5,
    "promoter selling": -2.5, "insider selling": -2.5, "stake sale": -1.5,
    "52 week low": -2.5, "record low": -2.5,
    "shutdown": -2.5, "layoff": -2.0, "layoffs": -2.0,
    "supply chain disruption": -2.0, "shortage": -1.5,
    "geopolitical": -1.5, "war": -2.0, "sanctions": -2.0, "tariff": -1.5,

    # Mild negative
    "risk": -0.5, "concern": -0.5, "volatile": -0.5, "uncertainty": -1.0,
    "caution": -0.5, "weak": -1.0, "pressure": -0.5,
}


def _build_analyzer() -> SentimentIntensityAnalyzer:
    """Create VADER analyzer with custom financial lexicon."""
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(FINANCIAL_LEXICON)
    return analyzer


_analyzer = _build_analyzer()


def analyze_text(text: str) -> dict:
    """Analyze sentiment of a text string.

    Returns:
        Dict with 'compound' (-1 to 1), 'pos', 'neg', 'neu' scores,
        and 'label' (BULLISH/BEARISH/NEUTRAL).
    """
    scores = _analyzer.polarity_scores(text)
    compound = scores["compound"]

    if compound >= 0.15:
        label = "BULLISH"
    elif compound <= -0.15:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    return {
        "compound": round(compound, 4),
        "positive": round(scores["pos"], 4),
        "negative": round(scores["neg"], 4),
        "neutral": round(scores["neu"], 4),
        "label": label,
    }


def analyze_news_item(item: NewsItem) -> dict:
    """Analyze sentiment of a single news item.

    Combines title (2x weight) + summary for final score.
    """
    title_scores = _analyzer.polarity_scores(item.title)
    summary_scores = _analyzer.polarity_scores(item.summary)

    # Title carries 2x weight — headlines drive market reaction
    compound = (title_scores["compound"] * 2 + summary_scores["compound"]) / 3

    if compound >= 0.15:
        label = "BULLISH"
    elif compound <= -0.15:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    return {
        "title": item.title,
        "source": item.source,
        "compound": round(compound, 4),
        "label": label,
        "related_symbols": item.related_symbols,
    }


def aggregate_sentiment_for_stock(news_items: list[NewsItem], symbol: str) -> dict:
    """Compute aggregate sentiment score for a specific stock.

    Considers:
    - Direct mentions (full weight)
    - Sector-level news (0.5x weight)
    - General market news (0.25x weight)

    Returns:
        Dict with avg_sentiment, news_count, bullish_count, bearish_count,
        sentiment_label, top_headlines.
    """
    scores = []
    headlines = []

    for item in news_items:
        analysis = analyze_news_item(item)

        if symbol in item.related_symbols:
            weight = 1.0  # Direct mention
        elif item.related_symbols:
            weight = 0.3  # Sector/other stock news
        else:
            weight = 0.15  # General market

        scores.append(analysis["compound"] * weight)
        if symbol in item.related_symbols:
            headlines.append({
                "title": analysis["title"],
                "sentiment": analysis["compound"],
                "label": analysis["label"],
                "source": analysis["source"],
            })

    if not scores:
        return {
            "avg_sentiment": 0.0,
            "news_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "sentiment_label": "NO_DATA",
            "top_headlines": [],
        }

    avg = sum(scores) / len(scores)
    bullish = sum(1 for s in scores if s > 0.1)
    bearish = sum(1 for s in scores if s < -0.1)

    if avg >= 0.1:
        label = "BULLISH"
    elif avg <= -0.1:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    return {
        "avg_sentiment": round(avg, 4),
        "news_count": len(scores),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "sentiment_label": label,
        "top_headlines": sorted(headlines, key=lambda x: abs(x["sentiment"]), reverse=True)[:5],
    }
