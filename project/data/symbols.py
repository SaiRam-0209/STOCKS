"""Stock universes: Largecap 100, Midcap 150, Smallcap 250 for NSE.

Each list is ordered by approximate index weight/rank.
Update periodically from https://www.niftyindices.com
"""

# =====================================================
# NIFTY LARGECAP 100 (ranked by index weight)
# =====================================================
LARGECAP_100_RANKED = [
    ("RELIANCE.NS", 1), ("TCS.NS", 2), ("HDFCBANK.NS", 3),
    ("INFY.NS", 4), ("ICICIBANK.NS", 5), ("BHARTIARTL.NS", 6),
    ("ITC.NS", 7), ("SBIN.NS", 8), ("LT.NS", 9),
    ("HINDUNILVR.NS", 10), ("BAJFINANCE.NS", 11), ("HCLTECH.NS", 12),
    ("MARUTI.NS", 13), ("AXISBANK.NS", 14), ("KOTAKBANK.NS", 15),
    ("SUNPHARMA.NS", 16), ("TITAN.NS", 17), ("ADANIENT.NS", 18),
    ("NTPC.NS", 19), ("TATAMOTORS.NS", 20), ("M&M.NS", 21),
    ("BAJAJFINSV.NS", 22), ("ONGC.NS", 23), ("ASIANPAINT.NS", 24),
    ("POWERGRID.NS", 25), ("TATASTEEL.NS", 26), ("WIPRO.NS", 27),
    ("COALINDIA.NS", 28), ("ADANIPORTS.NS", 29), ("NESTLEIND.NS", 30),
    ("JSWSTEEL.NS", 31), ("ULTRACEMCO.NS", 32), ("TECHM.NS", 33),
    ("BAJAJ-AUTO.NS", 34), ("DRREDDY.NS", 35), ("HINDALCO.NS", 36),
    ("INDUSINDBK.NS", 37), ("BRITANNIA.NS", 38), ("CIPLA.NS", 39),
    ("GRASIM.NS", 40), ("EICHERMOT.NS", 41), ("APOLLOHOSP.NS", 42),
    ("DIVISLAB.NS", 43), ("HEROMOTOCO.NS", 44), ("BEL.NS", 45),
    ("BPCL.NS", 46), ("TATACONSUM.NS", 47), ("HDFCLIFE.NS", 48),
    ("SBILIFE.NS", 49), ("SHRIRAMFIN.NS", 50), ("ETERNAL.NS", 51),
    ("GODREJCP.NS", 52), ("DABUR.NS", 53), ("HAVELLS.NS", 54),
    ("PIDILITIND.NS", 55), ("SIEMENS.NS", 56), ("DLF.NS", 57),
    ("ABB.NS", 58), ("AMBUJACEM.NS", 59), ("ADANIGREEN.NS", 60),
    ("TRENT.NS", 61), ("JIOFIN.NS", 62), ("BANKBARODA.NS", 63),
    ("INDIGO.NS", 64), ("IOC.NS", 65), ("VEDL.NS", 66),
    ("ICICIPRULI.NS", 67), ("GAIL.NS", 68), ("CHOLAFIN.NS", 69),
    ("HDFCAMC.NS", 70), ("TATAPOWER.NS", 71), ("PFC.NS", 72),
    ("RECLTD.NS", 73), ("HAL.NS", 74), ("CANBK.NS", 75),
    ("TORNTPHARM.NS", 76), ("UNIONBANK.NS", 77), ("MARICO.NS", 78),
    ("ZYDUSLIFE.NS", 79), ("ATGL.NS", 80), ("MANKIND.NS", 81),
    ("NAUKRI.NS", 82), ("SHREECEM.NS", 83), ("ACC.NS", 84),
    ("MAXHEALTH.NS", 85), ("IRFC.NS", 86), ("PNB.NS", 87),
    ("BOSCHLTD.NS", 88), ("LUPIN.NS", 89), ("INDIANB.NS", 90),
    ("MUTHOOTFIN.NS", 91), ("AUROPHARMA.NS", 92), ("COLPAL.NS", 93),
    ("SRF.NS", 94), ("NHPC.NS", 95), ("MOTHERSON.NS", 96),
    ("IDEA.NS", 97), ("SAIL.NS", 98), ("BERGEPAINT.NS", 99),
    ("VOLTAS.NS", 100),
]

# =====================================================
# NIFTY MIDCAP 150 (ranked by index weight)
# =====================================================
MIDCAP_150_RANKED = [
    ("PERSISTENT.NS", 1), ("POLYCAB.NS", 2), ("LTIM.NS", 3),
    ("PIIND.NS", 4), ("COFORGE.NS", 5), ("CUMMINSIND.NS", 6),
    ("MFSL.NS", 7), ("FEDERALBNK.NS", 8), ("SUNDARMFIN.NS", 9),
    ("OBEROIRLTY.NS", 10), ("IDFCFIRSTB.NS", 11), ("PHOENIXLTD.NS", 12),
    ("PATANJALI.NS", 13), ("CONCOR.NS", 14), ("ESCORTS.NS", 15),
    ("PAGEIND.NS", 16), ("MPHASIS.NS", 17), ("HINDPETRO.NS", 18),
    ("LICHSGFIN.NS", 19), ("PETRONET.NS", 20), ("NMDC.NS", 21),
    ("ASTRAL.NS", 22), ("AUBANK.NS", 23), ("SOLARINDS.NS", 24),
    ("ALKEM.NS", 25), ("TATAELXSI.NS", 26), ("SUPREMEIND.NS", 27),
    ("JUBLFOOD.NS", 28), ("PRESTIGE.NS", 29), ("DMART.NS", 30),
    ("BIOCON.NS", 31), ("BANDHANBNK.NS", 32), ("LAURUSLABS.NS", 33),
    ("BALKRISIND.NS", 34), ("ABCAPITAL.NS", 35), ("ICICIGI.NS", 36),
    ("STARHEALTH.NS", 37), ("IPCALAB.NS", 38), ("CROMPTON.NS", 39),
    ("GLAXO.NS", 40), ("APOLLOTYRE.NS", 41), ("LICI.NS", 42),
    ("DEEPAKNTR.NS", 43), ("NATCOPHARM.NS", 44), ("KANSAINER.NS", 45),
    ("TATACHEM.NS", 46), ("AJANTPHARM.NS", 47), ("BHEL.NS", 48),
    ("SUNDRMFAST.NS", 49), ("AIAENG.NS", 50), ("EMAMILTD.NS", 51),
    ("MANYAVAR.NS", 52), ("BHARATFORG.NS", 53), ("FORTIS.NS", 54),
    ("ASTRAZEN.NS", 55), ("BATAINDIA.NS", 56), ("TORNTPOWER.NS", 57),
    ("ENDURANCE.NS", 58), ("GSPL.NS", 59), ("ZEEL.NS", 60),
    ("SYNGENE.NS", 61), ("GMRAIRPORT.NS", 62), ("EXIDEIND.NS", 63),
    ("NYKAA.NS", 64), ("MRF.NS", 65), ("HONAUT.NS", 66),
    ("ABFRL.NS", 67), ("NAVINFLUOR.NS", 68), ("CENTRALBK.NS", 69),
    ("KPRMILL.NS", 70), ("DALBHARAT.NS", 71), ("IDBI.NS", 72),
    ("IPCALAB.NS", 73), ("LUXIND.NS", 74), ("WHIRLPOOL.NS", 75),
    ("LTTS.NS", 76), ("KEI.NS", 77), ("SCHAEFFLER.NS", 78),
    ("CGPOWER.NS", 79), ("JSWENERGY.NS", 80), ("KAJARIACER.NS", 81),
    ("LINDEINDIA.NS", 82), ("SUMICHEM.NS", 83), ("RAMCOCEM.NS", 84),
    ("CRISIL.NS", 85), ("AAVAS.NS", 86), ("SUVENPHAR.NS", 87),
    ("PFIZER.NS", 88), ("BDL.NS", 89), ("SONACOMS.NS", 90),
    ("CLEANTCH.NS", 91), ("MAZDOCK.NS", 92), ("Dixon.NS", 93),
    ("IRCTC.NS", 94), ("CARBORUNIV.NS", 95), ("EIHOTEL.NS", 96),
    ("COCHINSHIP.NS", 97), ("GRSE.NS", 98), ("KAYNES.NS", 99),
    ("LLOYDSME.NS", 100), ("RATNAMANI.NS", 101), ("TIINDIA.NS", 102),
    ("TIMKEN.NS", 103), ("THERMAX.NS", 104), ("SJVN.NS", 105),
    ("BLUESTARCO.NS", 106), ("POWERINDIA.NS", 107), ("CERA.NS", 108),
    ("AARTI.NS", 109), ("CENTURYPLY.NS", 110), ("AFFLE.NS", 111),
    ("RADICO.NS", 112), ("PRAJIND.NS", 113), ("GRINDWELL.NS", 114),
    ("BRIGADE.NS", 115), ("CYIENT.NS", 116), ("FINEORG.NS", 117),
    ("KPITTECH.NS", 118), ("JKCEMENT.NS", 119), ("APLAPOLLO.NS", 120),
    ("SUNTV.NS", 121), ("CHAMBLFERT.NS", 122), ("CAMS.NS", 123),
    ("KFINTECH.NS", 124), ("ROUTE.NS", 125), ("MEDANTA.NS", 126),
    ("NATIONALUM.NS", 127), ("MANAPPURAM.NS", 128), ("GLAND.NS", 129),
    ("EIDPARRY.NS", 130), ("LXCHEM.NS", 131), ("CENTURYTEX.NS", 132),
    ("DEEPAKFERT.NS", 133), ("BIKAJI.NS", 134), ("CLEAN.NS", 135),
    ("HAPPSTMNDS.NS", 136), ("KALYANKJIL.NS", 137), ("CDSL.NS", 138),
    ("ANGELONE.NS", 139), ("POLICYBZR.NS", 140), ("BSE.NS", 141),
    ("APTUS.NS", 142), ("ZOMATO.NS", 143), ("RAINBOW.NS", 144),
    ("IIFL.NS", 145), ("RAJESHEXPO.NS", 146), ("MAHLIFE.NS", 147),
    ("SONATSOFTW.NS", 148), ("JBCHEPHARM.NS", 149), ("REDINGTON.NS", 150),
]

# =====================================================
# NIFTY SMALLCAP 250 (ranked by index weight)
# =====================================================
SMALLCAP_250_RANKED = [
    ("BSE.NS", 1), ("ZOMATO.NS", 2), ("POLICYBZR.NS", 3),
    ("ANGELONE.NS", 4), ("RADICO.NS", 5), ("AFFLE.NS", 6),
    ("APTUS.NS", 7), ("AAVAS.NS", 8), ("KPITTECH.NS", 9),
    ("CYIENT.NS", 10), ("DEEPAKFERT.NS", 11), ("BIKAJI.NS", 12),
    ("FINEORG.NS", 13), ("CLEAN.NS", 14), ("CAMPUS.NS", 15),
    ("HAPPSTMNDS.NS", 16), ("KALYANKJIL.NS", 17), ("CAMS.NS", 18),
    ("RATNAMANI.NS", 19), ("PRAJIND.NS", 20), ("IIFL.NS", 21),
    ("GRINDWELL.NS", 22), ("KFINTECH.NS", 23), ("ROUTE.NS", 24),
    ("MEDANTA.NS", 25), ("RAINBOW.NS", 26), ("BRIGADE.NS", 27),
    ("JKCEMENT.NS", 28), ("NATIONALUM.NS", 29), ("MANAPPURAM.NS", 30),
    ("SUNTV.NS", 31), ("CENTURYTEX.NS", 32), ("CHAMBLFERT.NS", 33),
    ("LXCHEM.NS", 34), ("EIDPARRY.NS", 35), ("CERA.NS", 36),
    ("APLAPOLLO.NS", 37), ("MAHLIFE.NS", 38), ("RAJESHEXPO.NS", 39),
    ("GLAND.NS", 40), ("SONATSOFTW.NS", 41), ("JBCHEPHARM.NS", 42),
    ("LATENTVIEW.NS", 43), ("SHOPERSTOP.NS", 44), ("GNFC.NS", 45),
    ("NIACL.NS", 46), ("TIINDIA.NS", 47), ("REDINGTON.NS", 48),
    ("INOXWIND.NS", 49), ("RITES.NS", 50), ("IRCON.NS", 51),
    ("HFCL.NS", 52), ("TANLA.NS", 53), ("RVNL.NS", 54),
    ("HUDCO.NS", 55), ("WELSPUNLIV.NS", 56), ("BASF.NS", 57),
    ("CDSL.NS", 58), ("ELGIEQUIP.NS", 59), ("CAPLIPOINT.NS", 60),
    ("BLUEDART.NS", 61), ("MAHSEAMLES.NS", 62), ("DATAPATTNS.NS", 63),
    ("PGEL.NS", 64), ("EASEMYTRIP.NS", 65), ("GPPL.NS", 66),
    ("TEJASNET.NS", 67), ("JYOTHYLAB.NS", 68), ("SPARC.NS", 69),
    ("NCC.NS", 70), ("NETWORK18.NS", 71), ("RAYMOND.NS", 72),
    ("KIRLOSENG.NS", 73), ("WESTLIFE.NS", 74), ("SAFARI.NS", 75),
    ("METROPOLIS.NS", 76), ("HEMIPROP.NS", 77), ("GALAXYSURF.NS", 78),
    ("DEVYANI.NS", 79), ("ETHOSLTD.NS", 80), ("EQUITASBNK.NS", 81),
    ("MAN.NS", 82), ("KIMS.NS", 83), ("ZENTEC.NS", 84),
    ("TECHNOE.NS", 85), ("GESHIP.NS", 86), ("MOTILALOFS.NS", 87),
    ("ATUL.NS", 88), ("MASTEK.NS", 89), ("TRITURBINE.NS", 90),
    ("PRIVISCL.NS", 91), ("ELECTCAST.NS", 92), ("ZENSARTECH.NS", 93),
    ("RBLBANK.NS", 94), ("CRAFTSMAN.NS", 95), ("KEC.NS", 96),
    ("ENGINERSIN.NS", 97), ("PNCINFRA.NS", 98), ("VIJAYA.NS", 99),
    ("FINCABLES.NS", 100), ("CHALET.NS", 101), ("KIRLOSBROS.NS", 102),
    ("VRLLOG.NS", 103), ("MAZDOCK.NS", 104), ("BDL.NS", 105),
    ("COCHINSHIP.NS", 106), ("IFBIND.NS", 107), ("PRINCEPIPE.NS", 108),
    ("JKLAKSHMI.NS", 109), ("DCMSHRIRAM.NS", 110), ("SWSOLAR.NS", 111),
    ("MRPL.NS", 112), ("POWERINDIA.NS", 113), ("HGS.NS", 114),
    ("SAPPHIRE.NS", 115), ("CESC.NS", 116), ("SHYAMMETL.NS", 117),
    ("CARERATING.NS", 118), ("GATEWAY.NS", 119), ("UJJIVANSFB.NS", 120),
    ("TITAGARH.NS", 121), ("ESABINDIA.NS", 122), ("PGHH.NS", 123),
    ("SOBHA.NS", 124), ("TARSONS.NS", 125), ("VARROC.NS", 126),
    ("GREENPANEL.NS", 127), ("SWANENERGY.NS", 128), ("CCL.NS", 129),
    ("RENUKA.NS", 130), ("Star.NS", 131), ("GPIL.NS", 132),
    ("SUZLON.NS", 133), ("DOMS.NS", 134), ("ANANTRAJ.NS", 135),
    ("NUVAMA.NS", 136), ("ORIENTELEC.NS", 137), ("ALLCARGO.NS", 138),
    ("HBLPOWER.NS", 139), ("JSWINFRA.NS", 140), ("SYRMA.NS", 141),
    ("KAYNES.NS", 142), ("IDEAFORGE.NS", 143), ("RRKABEL.NS", 144),
    ("JPPOWER.NS", 145), ("GMDCLTD.NS", 146), ("FLAIR.NS", 147),
    ("UTIAMC.NS", 148), ("NSLNISP.NS", 149), ("AEGISLOG.NS", 150),
    ("AMBER.NS", 151), ("ISGEC.NS", 152), ("BSOFT.NS", 153),
    ("TDPOWERSYS.NS", 154), ("GRAPHITE.NS", 155), ("TATACHEM.NS", 156),
    ("GRSE.NS", 157), ("HOMEFIRST.NS", 158), ("SAGCEM.NS", 159),
    ("JMFINANCIL.NS", 160), ("POONAWALLA.NS", 161), ("DREAMFOLKS.NS", 162),
    ("AETHER.NS", 163), ("NEWGEN.NS", 164), ("RATEGAIN.NS", 165),
    ("SENCO.NS", 166), ("OLECTRA.NS", 167), ("HAPPYFORGE.NS", 168),
    ("GHCL.NS", 169), ("SPLPETRO.NS", 170), ("GODFRYPHLP.NS", 171),
    ("RELIGARE.NS", 172), ("JKTYRE.NS", 173), ("PVRINOX.NS", 174),
    ("TEAMLEASE.NS", 175), ("AVALON.NS", 176), ("BBTC.NS", 177),
    ("ZYDUSWELL.NS", 178), ("JUSTDIAL.NS", 179), ("VSTIND.NS", 180),
    ("SUPRIYA.NS", 181), ("ALKYLAMINE.NS", 182), ("CMSINFO.NS", 183),
    ("BOROLTD.NS", 184), ("VGUARD.NS", 185), ("THYROCARE.NS", 186),
    ("GMMPFAUD.NS", 187), ("LALPATHLAB.NS", 188), ("AMIORG.NS", 189),
    ("CHEMPLASTS.NS", 190), ("ANANDRATHI.NS", 191), ("JUBLPHARMA.NS", 192),
    ("SHARDACROP.NS", 193), ("SANOFI.NS", 194), ("BALAMINES.NS", 195),
    ("PCBL.NS", 196), ("CEATLTD.NS", 197), ("SUVEN.NS", 198),
    ("ASAHIINDIA.NS", 199), ("ELECON.NS", 200), ("NOCIL.NS", 201),
    ("FIEMIND.NS", 202), ("THERMAX.NS", 203), ("GARFIBRES.NS", 204),
    ("JTLIND.NS", 205), ("ACE.NS", 206), ("HIKAL.NS", 207),
    ("NUVOCO.NS", 208), ("NEOGEN.NS", 209), ("MMTC.NS", 210),
    ("BIRLACORPN.NS", 211), ("SIS.NS", 212), ("TASTYBIT.NS", 213),
    ("WOCKPHARMA.NS", 214), ("MAPMYINDIA.NS", 215), ("TCI.NS", 216),
    ("FINPIPE.NS", 217), ("EPL.NS", 218), ("GUJALKALI.NS", 219),
    ("RESPONIND.NS", 220), ("BEML.NS", 221), ("SUNDRMFAST.NS", 222),
    ("INDIGOPNTS.NS", 223), ("HEIDELBERG.NS", 224), ("TVSHLDNG.NS", 225),
    ("RSYSTEMS.NS", 226), ("BLUESTARCO.NS", 227), ("PRSMJOHNSN.NS", 228),
    ("VAIBHAVGBL.NS", 229), ("GOCOLORS.NS", 230), ("GPPL.NS", 231),
    ("KRSNAA.NS", 232), ("GENUSPOWER.NS", 233), ("JAIBALAJI.NS", 234),
    ("ROSSARI.NS", 235), ("NAVINFLUOR.NS", 236), ("INDIAMART.NS", 237),
    ("PPLPHARMA.NS", 238), ("HEG.NS", 239), ("FDC.NS", 240),
    ("MAHSCOOTER.NS", 241), ("MIDHANI.NS", 242), ("CANFINHOME.NS", 243),
    ("STARCEMENT.NS", 244), ("JAMNAAUTO.NS", 245), ("AARTI.NS", 246),
    ("PGHL.NS", 247), ("TVSSRICHAK.NS", 248), ("TTML.NS", 249),
    ("WSTCSTPAPR.NS", 250),
]

# =====================================================
# Flat lists (ordered by rank)
# =====================================================
LARGECAP_100 = [s for s, _ in LARGECAP_100_RANKED]
MIDCAP_150 = [s for s, _ in MIDCAP_150_RANKED]
SMALLCAP_250 = [s for s, _ in SMALLCAP_250_RANKED]

# All stocks combined (deduplicated, preserving order)
_seen = set()
ALL_STOCKS = []
for s in LARGECAP_100 + MIDCAP_150 + SMALLCAP_250:
    if s not in _seen:
        _seen.add(s)
        ALL_STOCKS.append(s)

# =====================================================
# Rank maps per universe
# =====================================================
LARGECAP_RANK_MAP = {s: r for s, r in LARGECAP_100_RANKED}
MIDCAP_RANK_MAP = {s: r for s, r in MIDCAP_150_RANKED}
SMALLCAP_RANK_MAP = {s: r for s, r in SMALLCAP_250_RANKED}

# Combined rank map (for backward compat, uses smallcap ranks)
RANK_MAP = {}
RANK_MAP.update(SMALLCAP_RANK_MAP)
RANK_MAP.update(MIDCAP_RANK_MAP)
RANK_MAP.update(LARGECAP_RANK_MAP)

# =====================================================
# Dynamic: All NSE stocks (fetched from NSE, cached)
# =====================================================
def _load_all_nse():
    """Load all NSE stocks dynamically. Falls back to hardcoded full list."""
    try:
        from project.data.symbols_fetcher import get_all_nse_stocks
        stocks = get_all_nse_stocks()
        if stocks and len(stocks) > 500:
            return stocks
    except Exception:
        pass
    # Fallback: use the baked-in full NSE list (works on Streamlit Cloud
    # where NSE API is blocked)
    try:
        from project.data.nse_stocks import NSE_ALL_SYMBOLS
        if NSE_ALL_SYMBOLS:
            return [s if s.endswith(".NS") else f"{s}.NS" for s in NSE_ALL_SYMBOLS]
    except Exception:
        pass
    return ALL_STOCKS  # last resort: index stocks only


NSE_ALL_STOCKS = _load_all_nse()
NSE_ALL_RANK_MAP = {s: i + 1 for i, s in enumerate(NSE_ALL_STOCKS)}

# =====================================================
# Universe registry — single source of truth
# =====================================================
UNIVERSES = {
    "All NSE": {
        "symbols": NSE_ALL_STOCKS,
        "rank_map": NSE_ALL_RANK_MAP,
        "count": len(NSE_ALL_STOCKS),
    },
    "Index Stocks (500)": {
        "symbols": ALL_STOCKS,
        "rank_map": RANK_MAP,
        "count": len(ALL_STOCKS),
    },
    "Largecap 100": {
        "symbols": LARGECAP_100,
        "rank_map": LARGECAP_RANK_MAP,
        "count": 100,
    },
    "Midcap 150": {
        "symbols": MIDCAP_150,
        "rank_map": MIDCAP_RANK_MAP,
        "count": 150,
    },
    "Smallcap 250": {
        "symbols": SMALLCAP_250,
        "rank_map": SMALLCAP_RANK_MAP,
        "count": 250,
    },
}

# Backward compat
NIFTY_50 = LARGECAP_100
