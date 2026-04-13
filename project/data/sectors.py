"""Comprehensive NSE sector classification.

Maps all major NSE stocks to their industry sector.
Used by the ML model to incorporate sector rotation signals.

Sectors align with the macro module's sector_rotation_signals:
    technology, banking, pharma, auto, oil_gas, metals,
    infrastructure, chemicals, real_estate, defence,
    fmcg, media, textiles, gold_jewellery, power, telecom,
    cement, fertilizer, insurance, logistics
"""

# ── Sector → list of tickers (without .NS suffix) ─────────────────────

_SECTOR_LISTS = {
    "technology": [
        "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "MPHASIS",
        "COFORGE", "PERSISTENT", "KPITTECH", "CYIENT", "HAPPSTMNDS",
        "MASTEK", "ZENSARTECH", "BSOFT", "NEWGEN", "SONATSOFTW",
        "LATENTVIEW", "RATEGAIN", "TATAELXSI", "ZENSAR", "BIRLASOFT",
        "KAYNES", "SYRMA", "AMBER", "DIXON", "INTELLECT", "TANLA",
        "ECLERX", "NAUKRI", "ZOMATO", "PAYTM", "POLICYBZR",
        "MAPMYINDIA", "ROUTE", "AFFLE", "INDIAMART",
    ],
    "banking": [
        "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
        "INDUSINDBK", "BANKBARODA", "PNB", "CANBK", "UNIONBANK",
        "INDIANB", "IDFCFIRSTB", "FEDERALBNK", "BANDHANBNK",
        "RBLBANK", "EQUITASBNK", "UJJIVANSFB", "AUBANK", "IDBI",
        "MAHABANK", "IOB", "CENTRALBK", "UCOBANK", "J&KBANK",
        "KARNATAKA", "CUB", "KARURVYSYA", "DCB", "POONAWALLA",
        "BSE", "CDSL", "ANGELONE", "CAMS", "KFINTECH",
        "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN",
        "MANAPPURAM", "MUTHOOTFIN", "LICHSGFIN", "PNBHOUSING",
        "AAVAS", "CANFINHOME", "HOMEFIRST", "JIOFIN",
    ],
    "pharma": [
        "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN",
        "AUROPHARMA", "BIOCON", "TORNTPHARM", "ZYDUSLIFE", "MANKIND",
        "ALKEM", "IPCALAB", "GLENMARK", "ABBOTINDIA", "SANOFI",
        "PFIZER", "GLAND", "JBCHEPHARM", "SPARC", "CAPLIPOINT",
        "JUBLPHARMA", "WOCKPHARMA", "LALPATHLAB", "METROPOLIS",
        "NATCOPHARM", "GRANULES", "AJANTPHARM", "ERIS", "LAURUSLABS",
        "SOLARA", "GLENMARK", "SUVEN", "AARTIDRUGS",
        "APOLLOHOSP", "MAXHEALTH", "FORTIS", "MEDANTA", "STARHEALTH",
        "YATHARTH", "KIMS", "SHALBY", "RAINBOWCHIL",
    ],
    "auto": [
        "TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "HEROMOTOCO",
        "EICHERMOT", "ASHOKLEY", "TVSMOTOR", "ESCORTS", "SONACOMS",
        "MOTHERSON", "BOSCHLTD", "EXIDEIND", "AMARARAJA", "BALKRISIND",
        "APOLLOTYRE", "CEATLTD", "JKTYRE", "MRF", "JAMNAAUTO",
        "VARROC", "FIEMIND", "ENDURANCE", "SUNDRMFAST",
        "OLECTRA", "TIINDIA", "SCHAEFFLER",
    ],
    "oil_gas": [
        "RELIANCE", "ONGC", "IOC", "BPCL", "GAIL", "HINDPETRO",
        "PETRONET", "MRPL", "SPLPETRO", "IGL", "MGL", "GUJGASLTD",
        "OIL", "CASTROLIND", "AEGISCHEM", "CHENNPETRO",
        "ATGL", "GSPL", "MAHANAGAR",
    ],
    "metals": [
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL",
        "NATIONALUM", "NMDC", "COALINDIA", "JINDALSTEL", "APLAPOLLO",
        "RATNAMANI", "WELCORP", "MOIL", "HINDCOPPER", "NALCO",
        "KIOCL", "MISHRA", "GRAVITA", "SHYAMMETL",
    ],
    "infrastructure": [
        "LT", "NCC", "PNCINFRA", "KEC", "JSWINFRA", "IRCON",
        "RVNL", "RITES", "NBCC", "HCC", "BEL", "BHEL",
        "ENGINERSIN", "TITAGARH", "IRFC", "RAILTEL",
        "COCHINSHIP", "GRSE", "MAZDOCK", "GARDENREACH",
        "KALPATPOWR", "TECHNOELEC", "GPPL",
    ],
    "defence": [
        "HAL", "BDL", "BEL", "MAZDOCK", "COCHINSHIP", "GRSE",
        "DATAPATTNS", "IDEAFORGE", "PARAS", "GARDENREACH",
        "SOLARINDS", "ASTRAZEN",
    ],
    "chemicals": [
        "PIDILITIND", "SRF", "ATUL", "ALKYLAMINE", "BALAMINES",
        "NOCIL", "TATACHEM", "CHEMPLASTS", "DEEPAKFERT",
        "DEEPAKNTR", "CLEAN", "GALAXYSURF", "LXCHEM", "ANURAS",
        "FINEORG", "VINATIORG", "NAVINFLUOR", "FLUOROCHEM",
        "PI", "UPL", "SUMICHEM", "RALLIS", "BAYER", "DHANUKA",
    ],
    "fmcg": [
        "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "GODREJCP",
        "DABUR", "MARICO", "COLPAL", "TATACONSUM", "EMAMILTD",
        "VGUARD", "BATAINDIA", "RELAXO", "METROBRAND", "CAMPUS",
        "BIKAJI", "DEVYANI", "JUBLFOOD", "ZOMATO", "WESTLIFE",
        "SAPPHIRE", "TRENT", "DMART",
    ],
    "real_estate": [
        "DLF", "GODREJPROP", "BRIGADE", "SOBHA", "ANANTRAJ",
        "HEMIPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD",
        "RAYMOND", "SUNTECK", "MAHLIFE", "LODHA",
    ],
    "cement": [
        "ULTRACEMCO", "AMBUJACEM", "ACC", "SHREECEM", "DALMIACEM",
        "RAMCOCEM", "JKCEMENT", "BIRLACORPN", "NUVOCO", "SAGCEM",
        "INDIACEM", "PRISMJOHN", "HEIDELBERG", "JKLAKSHMI",
        "STARCEMENT", "ORIENTCEM",
    ],
    "power": [
        "NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN", "ADANIENSOL",
        "PFC", "RECLTD", "NHPC", "SJVN", "CESC", "JPPOWER",
        "HBLPOWER", "POWERINDIA", "TORNTPOWER", "JSWENERGY",
        "SUZLON", "INOXWIND", "SWSOLAR", "IREDA", "WAAREEENER",
    ],
    "telecom": [
        "BHARTIARTL", "IDEA", "TTML",
        "INDUSTOWER", "STERLITE",
    ],
    "insurance": [
        "HDFCLIFE", "SBILIFE", "ICICIPRULI", "ICICIGI",
        "STARHEALTH", "NIACL", "GICRE", "LICI",
    ],
    "media": [
        "ZEEL", "PVRINOX", "NETWORK18", "TV18BRDCST", "SUNTV",
        "SAREGAMA", "TIPS", "NAZARA",
    ],
    "textiles": [
        "PAGEIND", "RAYMOND", "ARVIND", "WELSPUNLIV",
        "TRIDENT", "SOMANYCERA", "CENTURYTEX", "GOKALDAS",
    ],
    "gold_jewellery": [
        "TITAN", "KALYANKJIL", "SENCO", "THANGAMAYL",
        "PGHH", "RAJESHEXPO",
    ],
    "fertilizer": [
        "CHAMBLFERT", "COROMANDEL", "GNFC", "GSFC", "RCF",
        "NFL", "DEEPAKFERT", "FACT",
    ],
    "logistics": [
        "ADANIPORTS", "CONCOR", "DELHIVERY", "BLUEDART",
        "TCI", "MAHSEAMLES", "ALLCARGO", "VRL",
    ],
}

# ── Build reverse map: "RELIANCE.NS" → "oil_gas" ──────────────────────

SECTOR_MAP: dict[str, str] = {}
for _sector, _tickers in _SECTOR_LISTS.items():
    for _ticker in _tickers:
        SECTOR_MAP[f"{_ticker}.NS"] = _sector
        SECTOR_MAP[_ticker] = _sector  # also without .NS

# Total mapped
MAPPED_COUNT = len(set(SECTOR_MAP.values()))
STOCK_COUNT = len({k for k in SECTOR_MAP if k.endswith(".NS")})


def get_sector(symbol: str) -> str:
    """Get sector for a stock symbol. Returns empty string if unmapped."""
    return SECTOR_MAP.get(symbol, SECTOR_MAP.get(symbol.replace(".NS", ""), ""))


def get_sector_stocks(sector: str) -> list[str]:
    """Get all stocks in a sector (with .NS suffix)."""
    return [f"{t}.NS" for t in _SECTOR_LISTS.get(sector, [])]
