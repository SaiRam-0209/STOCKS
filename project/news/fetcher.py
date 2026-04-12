"""Fetch real-time financial news from multiple RSS sources."""

import feedparser
import re
import html
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    published: str
    link: str
    related_symbols: list[str]


# --- RSS Feed URLs ---
RSS_FEEDS = {
    "google_business_india": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
    "google_markets": "https://news.google.com/rss/search?q=indian+stock+market&hl=en-IN&gl=IN&ceid=IN:en",
    "google_smallcap": "https://news.google.com/rss/search?q=smallcap+india+stocks&hl=en-IN&gl=IN&ceid=IN:en",
    "google_nifty": "https://news.google.com/rss/search?q=nifty+sensex+market&hl=en-IN&gl=IN&ceid=IN:en",
    "et_markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "et_stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "moneycontrol_markets": "https://www.moneycontrol.com/rss/marketreports.xml",
    "moneycontrol_news": "https://www.moneycontrol.com/rss/latestnews.xml",
    "livemint_markets": "https://www.livemint.com/rss/markets",
    "google_economy": "https://news.google.com/rss/search?q=india+economy+RBI+inflation&hl=en-IN&gl=IN&ceid=IN:en",
    "google_global": "https://news.google.com/rss/search?q=federal+reserve+US+markets+oil+prices&hl=en-IN&gl=IN&ceid=IN:en",
    "google_sectors": "https://news.google.com/rss/search?q=pharma+IT+banking+auto+india+stocks&hl=en-IN&gl=IN&ceid=IN:en",
}

# Map common company names → ticker symbols
COMPANY_NAME_MAP = {
    "suzlon": "SUZLON.NS", "zomato": "ZOMATO.NS", "cdsl": "CDSL.NS",
    "rvnl": "RVNL.NS", "hudco": "HUDCO.NS", "ircon": "IRCON.NS",
    "bse": "BSE.NS", "mazagon": "MAZDOCK.NS", "cochin shipyard": "COCHINSHIP.NS",
    "kaynes": "KAYNES.NS", "grse": "GRSE.NS", "bdl": "BDL.NS",
    "olectra": "OLECTRA.NS", "hfcl": "HFCL.NS", "manappuram": "MANAPPURAM.NS",
    "kalyan jewellers": "KALYANKJIL.NS", "kalyan": "KALYANKJIL.NS",
    "brigade": "BRIGADE.NS", "angelone": "ANGELONE.NS", "angel one": "ANGELONE.NS",
    "policybazaar": "POLICYBZR.NS", "kpit": "KPITTECH.NS",
    "rbl bank": "RBLBANK.NS", "radico": "RADICO.NS", "cyient": "CYIENT.NS",
    "bikaji": "BIKAJI.NS", "campus": "CAMPUS.NS", "pvr inox": "PVRINOX.NS",
    "devyani": "DEVYANI.NS", "mastek": "MASTEK.NS", "cera": "CERA.NS",
    "national aluminium": "NATIONALUM.NS", "nalco": "NATIONALUM.NS",
    "rites": "RITES.NS", "beml": "BEML.NS", "bharat dynamics": "BDL.NS",
    "sobha": "SOBHA.NS", "just dial": "JUSTDIAL.NS", "justdial": "JUSTDIAL.NS",
    "indiamart": "INDIAMART.NS", "safari": "SAFARI.NS", "metropolis": "METROPOLIS.NS",
    "sun tv": "SUNTV.NS", "titan": "TITAN.NS", "ncc": "NCC.NS",
    "thermax": "THERMAX.NS", "amber": "AMBER.NS", "blue dart": "BLUEDART.NS",
    "raymond": "RAYMOND.NS", "deepak fertilisers": "DEEPAKFERT.NS",
    "ujjivan": "UJJIVANSFB.NS", "equitas": "EQUITASBNK.NS",
    "poonawalla": "POONAWALLA.NS", "religare": "RELIGARE.NS",
    "lalpathlab": "LALPATHLAB.NS", "lal path": "LALPATHLAB.NS",
    "basf": "BASF.NS", "atul": "ATUL.NS",
}

# Sector keywords → list of tickers affected
SECTOR_MAP = {
    "defence": ["BDL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS", "BEL.NS", "DATAPATTNS.NS"],
    "defense": ["BDL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS", "BEL.NS", "DATAPATTNS.NS"],
    "railway": ["RVNL.NS", "IRCON.NS", "RITES.NS", "TITAGARH.NS"],
    "railways": ["RVNL.NS", "IRCON.NS", "RITES.NS", "TITAGARH.NS"],
    "pharma": ["JBCHEPHARM.NS", "GLAND.NS", "SPARC.NS", "CAPLIPOINT.NS", "JUBLPHARMA.NS", "WOCKPHARMA.NS"],
    "solar": ["SWSOLAR.NS", "INOXWIND.NS"],
    "renewable": ["SWSOLAR.NS", "INOXWIND.NS", "SUZLON.NS"],
    "wind energy": ["SUZLON.NS", "INOXWIND.NS"],
    "infra": ["NCC.NS", "PNCINFRA.NS", "KEC.NS", "JSWINFRA.NS", "IRCON.NS"],
    "infrastructure": ["NCC.NS", "PNCINFRA.NS", "KEC.NS", "JSWINFRA.NS", "IRCON.NS"],
    "shipyard": ["MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS"],
    "ship": ["MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS", "GESHIP.NS"],
    "banking": ["RBLBANK.NS", "EQUITASBNK.NS", "UJJIVANSFB.NS"],
    "smallcap": [],  # general market mood
    "small cap": [],
    "auto": ["JAMNAAUTO.NS", "VARROC.NS", "CEATLTD.NS", "JKTYRE.NS", "FIEMIND.NS"],
    "chemical": ["ATUL.NS", "ALKYLAMINE.NS", "BALAMINES.NS", "NOCIL.NS", "TATACHEM.NS", "CHEMPLASTS.NS"],
    "chemicals": ["ATUL.NS", "ALKYLAMINE.NS", "BALAMINES.NS", "NOCIL.NS", "TATACHEM.NS", "CHEMPLASTS.NS"],
    "cement": ["JKCEMENT.NS", "SAGCEM.NS", "HEIDELBERG.NS", "BIRLACORPN.NS", "NUVOCO.NS", "STARCEMENT.NS"],
    "electronics": ["KAYNES.NS", "SYRMA.NS", "DATAPATTNS.NS"],
    "ems": ["KAYNES.NS", "SYRMA.NS", "AMBER.NS"],
    "real estate": ["BRIGADE.NS", "SOBHA.NS", "ANANTRAJ.NS", "HEMIPROP.NS"],
    "realty": ["BRIGADE.NS", "SOBHA.NS", "ANANTRAJ.NS", "HEMIPROP.NS"],
    "fmcg": ["BIKAJI.NS", "ZYDUSWELL.NS", "GODFRYPHLP.NS", "RAJESHEXPO.NS", "TASTYBIT.NS"],
    "technology": ["KPITTECH.NS", "CYIENT.NS", "HAPPSTMNDS.NS", "MASTEK.NS", "ZENSARTECH.NS", "BSOFT.NS", "NEWGEN.NS"],
    "fintech": ["BSE.NS", "CDSL.NS", "ANGELONE.NS", "CAMS.NS", "KFINTECH.NS"],
    "gold": ["KALYANKJIL.NS", "SENCO.NS"],
    "jewellery": ["KALYANKJIL.NS", "SENCO.NS"],
    "oil": ["MRPL.NS", "SPLPETRO.NS"],
    "crude": ["MRPL.NS", "SPLPETRO.NS"],
    "power": ["HBLPOWER.NS", "JPPOWER.NS", "CESC.NS", "POWERINDIA.NS", "TDPOWERSYS.NS"],
    "fertiliser": ["DEEPAKFERT.NS", "CHAMBLFERT.NS", "GNFC.NS"],
    "fertilizer": ["DEEPAKFERT.NS", "CHAMBLFERT.NS", "GNFC.NS"],
}


def _clean_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_symbols(text: str) -> list[str]:
    """Extract stock symbols mentioned in text via company names and sector keywords."""
    text_lower = text.lower()
    matched = set()

    # Direct company name matches
    for name, symbol in COMPANY_NAME_MAP.items():
        if name in text_lower:
            matched.add(symbol)

    # Sector keyword matches
    for keyword, symbols in SECTOR_MAP.items():
        if keyword in text_lower:
            matched.update(symbols)

    return list(matched)


def fetch_news(max_age_hours: int = 48) -> list[NewsItem]:
    """Fetch news from all RSS feeds.

    Args:
        max_age_hours: Only include news from the last N hours.

    Returns:
        List of NewsItem objects with related stock symbols.
    """
    all_news = []
    cutoff = datetime.now() - timedelta(hours=max_age_hours)

    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:  # Top 20 per feed
                title = _clean_html(entry.get("title", ""))
                summary = _clean_html(entry.get("summary", entry.get("description", "")))

                # Parse publish date
                published = entry.get("published", entry.get("updated", ""))

                # Match to stock symbols
                full_text = f"{title} {summary}"
                related = _match_symbols(full_text)

                news_item = NewsItem(
                    title=title,
                    summary=summary[:500],
                    source=source_name,
                    published=published,
                    link=entry.get("link", ""),
                    related_symbols=related,
                )
                all_news.append(news_item)
        except Exception as e:
            print(f"[WARN] Failed to fetch RSS feed {source_name}: {e}")

    return all_news


def fetch_stock_news(symbol: str, max_items: int = 10) -> list[NewsItem]:
    """Fetch news specifically about one stock via Google News RSS."""
    # Strip .NS suffix for search
    clean_name = symbol.replace(".NS", "").replace("-", " ")
    url = f"https://news.google.com/rss/search?q={clean_name}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"

    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            title = _clean_html(entry.get("title", ""))
            summary = _clean_html(entry.get("summary", entry.get("description", "")))
            items.append(NewsItem(
                title=title,
                summary=summary[:500],
                source="google_stock_search",
                published=entry.get("published", ""),
                link=entry.get("link", ""),
                related_symbols=[symbol],
            ))
    except Exception as e:
        print(f"[WARN] Failed to fetch stock news for {symbol}: {e}")

    return items
