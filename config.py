# ============================================================
# config.py
# ------------------------------------------------------------
# Centrala standardvärden, tickerproxys och pedagogiska
# förklaringstexter. Inga beräkningar eller Streamlit-anrop
# här - bara ren konfiguration som övriga moduler importerar.
# ============================================================

from __future__ import annotations

# ------------------------------------------------------------
# Tekniska indikatorer - standardvärden
# ------------------------------------------------------------
DEFAULT_TICKER = "SPY"
DEFAULT_SMA_PERIOD = 200
DEFAULT_RSI_PERIOD = 14
DEFAULT_BUY_RSI_THRESHOLD = 28
DEFAULT_SELL_RSI_FILTER = 65
DEFAULT_COOLDOWN_BARS = 15  # handelsdagar (bars), inte kalenderdagar
DEFAULT_VIX_PANIC_THRESHOLD = 34.0
DEFAULT_HEATMAP_CAP = 150

MACD_FAST = 24
MACD_SLOW = 52
MACD_SIGNAL = 9

# ------------------------------------------------------------
# Execution / kostnader
# ------------------------------------------------------------
DEFAULT_EXECUTION_METHOD = "Nästa dags stängning (Close)"
EXECUTION_METHODS = [
    "Nästa dags stängning (Close)",
    "Nästa dags öppning (Open)",
]
DEFAULT_COST_BPS = 0.0       # courtage/transaktionskostnad, baspunkter
DEFAULT_SLIPPAGE_BPS = 0.0   # slippage, baspunkter
DEFAULT_INITIAL_CAPITAL = 10_000.0
DEFAULT_RISK_FREE_RATE_ANNUAL = 0.0  # används i Sharpe/Sortino, procent/år -> decimal

# ------------------------------------------------------------
# KI / Konjunkturmodellen - standardvärden
# ------------------------------------------------------------
DEFAULT_KI_SELL_THRESHOLD = 110
DEFAULT_KI_BUY_THRESHOLD = 90
DEFAULT_KI_DURATION_MONTHS = 3
DEFAULT_KI_FLOOR_THRESHOLD = 90  # KI måste ha varit under denna nivå innan en "vänd upp"-signal tillåts

KI_BUYBACK_RULES = {
    "classic": "A. Klassisk modell (KI under köpgräns i N månader)",
    "turn_1m": "B. KI vänder upp - 1 månad",
    "turn_2m": "C. KI vänder upp - 2 månader",
    "turn_3m": "D. KI vänder upp - 3 månader",
    "flat_or_up": "E. KI oförändrat eller stigande efter passerad köpgräns",
}
DEFAULT_KI_BUYBACK_RULE = "classic"

KI_SIGNAL_SCOPE_OPTIONS = {
    "all": "Hela portföljen",
    "sweden_only": "Endast Sverige",
    "sweden_em": "Sverige + Emerging Markets",
}
DEFAULT_KI_SIGNAL_SCOPE = "all"

DERISK_LEVELS = [0, 25, 50, 75, 100]
DEFAULT_DERISK_LEVEL = 50

# ------------------------------------------------------------
# Portfölj - proxys och vikter
# ------------------------------------------------------------
# Alla tre proxys handlas i USD (utdelningsjusterade ETF:er via
# yfinance auto_adjust=True). Portföljen normaliseras därefter
# till gemensam basvaluta (default SEK) via USD/SEK-växelkurs.
PORTFOLIO_PROXIES = {
    "global": {"ticker": "URTH", "label": "Global (iShares MSCI World ETF, USD, utd.just.)"},
    "sweden": {"ticker": "EWD", "label": "Sverige (iShares MSCI Sweden ETF, USD, utd.just.)"},
    "em": {"ticker": "EEM", "label": "Emerging Markets (iShares MSCI EM ETF, USD, utd.just.)"},
}
FX_TICKER = "USDSEK=X"
DEFAULT_BASE_CURRENCY = "SEK"

DEFAULT_PORTFOLIO_WEIGHTS = {"global": 0.75, "sweden": 0.10, "em": 0.15}

REBALANCE_OPTIONS = {
    "none": "Ingen rebalansering",
    "annual": "Årlig",
    "quarterly": "Kvartalsvis",
    "monthly": "Månadsvis",
}
DEFAULT_REBALANCE = "annual"

# Originalmodell / Sverige - jämförelseticker (samma proxy som portföljens
# Sverige-del, se README för motivering och begränsningar).
SWEDEN_ORIGINAL_TICKER = PORTFOLIO_PROXIES["sweden"]["ticker"]

# ------------------------------------------------------------
# Räntekonto
# ------------------------------------------------------------
INTEREST_MODES = {
    "fixed": "Fast ränta",
    "zero": "0 % ränta (jämförelse)",
}
DEFAULT_INTEREST_MODE = "fixed"
DEFAULT_ANNUAL_INTEREST_RATE = 0.025  # 2.5 %

# ------------------------------------------------------------
# Datumhantering / look-ahead
# ------------------------------------------------------------
# KI-barometern publiceras i praktiken med viss eftersläpning efter
# månadens slut. Vi känner inte till exakt historiskt publiceringsdatum
# via det öppna API:et, så vi använder en konservativ schablon: signalen
# anses tillgänglig först ett antal kalenderdagar efter månadsskiftet,
# och exekveras därefter tidigast nästa handelsdag. Detta dokumenteras
# även i README och i UI.
KI_PUBLICATION_LAG_DAYS = 20

# ------------------------------------------------------------
# Pedagogiska förklaringar (används som help= och i expanders)
# ------------------------------------------------------------
EXPLANATIONS = {
    "sma": "SMA (Simple Moving Average) är priset i genomsnitt över de senaste X dagarna. "
           "Den visar den långsiktiga prisriktningen: pris över SMA = uppåttrend, pris under SMA = nedåttrend.",
    "rsi": "RSI (Relative Strength Index) mäter kortsiktigt momentum på en skala 0-100. "
           "Här används den framför allt för att identifiera kraftigt översålda lägen (lågt RSI).",
    "macd": "MACD jämför två glidande medelvärden för att försöka identifiera förändringar i momentum. "
            "När MACD-linjen korsar ner under sin signallinje tolkas det som en försvagning.",
    "vix": "VIX mäter förväntad volatilitet/stress på den amerikanska aktiemarknaden. "
           "Höga VIX-nivåer har historiskt ofta sammanfallit med paniknedgångar och efterföljande återhämtningar.",
    "trend": "Positiv trend = priset ligger över sitt glidande medelvärde (SMA). "
             "Negativ trend = priset ligger under. Detta säger inget om framtiden, bara nuläget.",
    "cooldown": "Signal-cooldown (handelsdagar) förhindrar att nya signaler av samma typ skapas för tätt inpå "
                "varandra. Måttet räknas i handelsdagar (börsdagar), inte kalenderdagar.",
    "heatmap": "Heatmap-intensiteten styr bara hur snabbt graf-färgerna mättas ju längre en trend pågått. "
               "Den påverkar enbart visualiseringen, inte några signaler eller backtestresultat.",
    "ki_barometer": "KI:s Barometerindikator är Konjunkturinstitutets sammanvägda mått på stämningsläget i "
                    "svensk ekonomi. Värden kring 100 anses normalläge.",
    "ki_sell": "KI-säljgränsen anger vid vilken nivå konjunkturen anses överhettad. Modellen är konträr: "
               "vid överhettning minskas aktieexponeringen, i tron att risken för avmattning ökat.",
    "ki_buy": "KI-köpgränsen anger vid vilken nivå konjunkturen anses vara i en tydlig lågkonjunktur. "
              "Modellen är konträr: vid svag konjunktur ökas aktieexponeringen igen.",
    "ki_months": "Antal månader i följd över säljgränsen före försäljning. För klassiskt återköp gäller "
                 "samma antal månader under köpgränsen. Övriga återköpsregler har egna villkor.",
    "ki_flat_or_up": "Efter försäljning måste KI först vara strikt under köpgränsen. Köp sedan vid första "
                      "månad som är oförändrad eller högre än månaden innan, även över köpgränsen "
                      "(t.ex. 89 → 91 med köpgräns 90). Två månaders värden jämförs; två uppgångar krävs inte. "
                      "Aktiveringen nollställs efter återköp. Antal bekräftande månader gäller här endast sälj.",
    "cagr": "CAGR (Compound Annual Growth Rate) är den genomsnittliga årliga avkastningen, jämnt utspridd "
            "över hela perioden - även om den faktiska resan var betydligt ojämnare.",
    "total_return": "Totalavkastningen är den sammanlagda procentuella förändringen av portföljvärdet från "
                     "start till slut, inklusive alla mellanliggande upp- och nedgångar.",
    "mdd": "Max Drawdown är det största observerade fallet från en tidigare topp till en efterföljande botten. "
           "Ett mått på det värsta som historiskt hänt en investerare som köpte på fel dag.",
    "sharpe": "Sharpe Ratio mäter avkastning per enhet total risk (volatilitet), justerat för riskfri ränta. "
              "Högre är bättre, men måttet straffar även uppåtgående volatilitet.",
    "sortino": "Sortino Ratio liknar Sharpe men straffar bara nedåtgående volatilitet (förluster), "
               "vilket ofta upplevs som mer rättvisande för investerare.",
    "calmar": "Calmar Ratio ställer CAGR i relation till Max Drawdown. Ett sätt att väga avkastning "
              "mot det värsta historiska fallet.",
    "win_rate": "Win Rate är andelen avslutade affärer som gick med vinst, av samtliga avslutade affärer.",
    "profit_factor": "Profit Factor är summan av alla vinster delat med summan av alla förluster (i kronor/dollar). "
                      "Ett värde över 1 betyder att vinsterna historiskt överstigit förlusterna.",
    "exposure": "Marknadsexponering anger hur stor andel av tidsperioden portföljen faktiskt varit investerad "
                "i aktier, till skillnad från att stå i kassa/räntekonto.",
    "slippage": "Slippage är skillnaden mellan det pris man förväntade sig och det pris man faktiskt fick vid "
                "exekvering, t.ex. på grund av snabba prisrörelser eller låg likviditet.",
    "cost": "Courtage/transaktionskostnad är den avgift som tas ut vid varje köp/sälj, här angiven i baspunkter "
            "(1 baspunkt = 0,01 %) av affärens värde.",
    "risk_free": "Räntekonto/riskfri avkastning är den ränta kapital som inte är investerat i aktier antas "
                 "generera under tiden, t.ex. på ett räntekonto eller i statsskuldväxlar.",
    "derisk_pct": "Anger hur stor andel av aktieexponeringen som säljs av vid en KI-säljsignal. 100 % innebär "
                  "att allt flyttas till räntekontot, 0 % innebär att inget säljs.",
    "ki_scope": "Bestämmer vilken del av portföljen som påverkas av KI-signalen: hela portföljen, "
                "enbart den svenska delen, eller Sverige + Emerging Markets.",
    "rebalance": "Rebalansering innebär att portföljens vikter periodiskt återställs till målvikterna. "
                 "Utan rebalansering driver vinnande tillgångar successivt upp sin andel av portföljen.",
    "currency": "Alla portföljdelar konverteras till en gemensam basvaluta (SEK) via USD/SEK-kursen innan "
                "de vägs samman, så att avkastningar är jämförbara rakt av.",
}
