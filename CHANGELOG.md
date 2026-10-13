# Genomförda ändringar och kvalitetskontroll

## 8 oktober 2026 – Perioder, förklaringar och valbara villkor

- Gemensamt datumval, aktiv vikt styr historik, Sverige jämförs under samma KI-period och döljs vid 100 % Sverige.
- Lokala återställningsknappar och separat återställning av perioden.
- Valbara tekniska köpkällor, MACD-sälj och RSI-/SMA-filter; grafval är fristående.
- Valbart KI-trendfilter med väntande köp och endast föregående dags kända priser. Med/utan filter jämförs separat.
- Förklaringar i affärsloggar, slutvärden, avslutade KI-cykler och längsta tid under tidigare topp.
- Fördjupningar samlade i utfällbara rutor. Skillnad i totalavkastning märks som procentenheter.
- Senast kända beslut sätter startallokering; historiska signaler krockar inte längre första handelsdagen.
- SMA påverkar inte längre tekniskt tests start när SMA är enbart visning. RSI/MACD-uppvärmning gäller aktiva villkor.
- KI:s revideringar och publiceringsschablon granskade mot KI:s information och förklarade i UI/README.
- Automatiska regressionstester för aktiva indikatorer, oförändrade visningsval, perioder, nollvikter,
  återställning, trendorder utan framtidsinformation och återhämtningstid. Testdata är syntetiska.

Verifiering: 102 tester passerar (syntetiska data, nätverk spärrat i testerna).
De tidigare testantalen nedan avser tidigare versioner.

## 8 oktober 2026 – Oförändrat eller stigande KI

- Nytt val `flat_or_up` i både Konjunktur och Portföljbacktest, med separata inställningar.
- Efter försäljning aktiverar KI strikt under köpgränsen återköp vid första oförändrade eller stigande månad, även över köpgränsen. Separat golv ignoreras för denna regel.
- Återköp nollställer aktiveringen. Jämförelsen kräver två intilliggande kalendermånader med tillgängliga värden.
- Den nya regeln ingår i automatisk jämförelse; portföljgraf och modellöversikt visar dess faktiska aktiveringsnivå.
- 91 tester passerar, inklusive 21 nya testfall för köpregeln, handelsfördröjning och båda flikarnas parameterkoppling.

## Tidigare ändringar

Samtliga åtta önskade punkter är hanterade. Modularkitekturen och de två separata
backtestmotorerna är bevarade. Originalarkivet har inte ändrats.

## Ändrade befintliga filer

| Fil | Ändring och orsak |
|---|---|
| `ki_model.py` | Strikt framåtmappning med `side="right"` på kalenderdatum. Signalen kan inte exekveras samma handelsdag som Available_Date, inte heller med tidsstämplar inom dagen. Signaler efter sista möjliga exekveringsdag utelämnas. |
| `indicators.py` | Klassisk Wilder-seed över de första N prisförändringarna och därefter recursion. NaN under uppvärmning, ny seed efter datagap, validerad period och bevarade specialfall 0/50/100. |
| `portfolio.py` | FX fylls bara framåt på unionen av pris- och FX-datum. Okänd tidigare kurs förblir NaN och rensas vid kalenderanpassning. Kostnader och omsättning redovisas per dag, inklusive initialköp, avriskning, återköp och rebalansering; benchmarken får samma kostnadsparametrar. Rebalanseringsdatum använder konsekvent Pandas Timestamp, vilket rättar den tidigare typblandningen. Effektiv riskfri ränta finns på PortfolioParams. Ursprungligt kapital bevaras i equity-attribut. |
| `metrics.py` | Totalavkastning, CAGR, drawdown och Calmar kan räkna från portföljens ursprungliga kapital så initialkostnaden inte tappas bort. Vanliga serier utan attribut behåller befintligt beteende. Sharpe-/Sortino-formlerna är oförändrade. |
| `app.py` | Vald effektiv årsränta skickas till samtliga Sharpe/Sortino-rapportanrop, inklusive teknisk strategi/benchmark och KI-parametersvep. Samma kostnadsparametrar skickas till samtliga KI-varianter och Sverigebenchmarken. Tydliga räntetexter, faktisk period, historikvarning och fel vid färre än två gemensamma datum. KI-drawdowngrafer tar hänsyn till initialkostnaden. |
| `conftest.py` | Importvägen anpassad till arkivets projektrot; automatisk spärr mot nätverksanslutningar i tester. |
| `README.md` | Exakt RSI-metod, execution, FX, räntekonvention, kostnadsmodell, historik/proxyval och begränsningar dokumenterade. Testkommando och projektstruktur rättade till faktisk placering i projektroten. |

## Nya filer

- `test_regressions.py`: 28 nya parametriserade testfall för beräkningsmotorer och UI:s parameterkopplingar.
- `test_app.py`: 2 testfall som kör hela Streamlit-gränssnittet med syntetiska data, inklusive upprepade körningar med ändrade inställningar.
- `CHANGELOG.md`: denna redovisning.

## Nya tester

| Test | Antal fall | Verifierar |
|---|---:|---|
| `test_execution_strictly_after_availability` | 5 | Handelsdag, intradagstid, helg, helgdag och datasetets slut; uttryckligen Exec_Date > Available_Date. |
| `test_wilder_rsi_exact_reference` | 1 | Handräknad N=3-serie med exakta bråk, NaN och oförändrad historik när framtida priser tillkommer. |
| `test_wilder_fourteen_period_published_example_values` | 1 | Klassisk 14-perioders exempelprisserie med sju förväntade RSI-värden utan avrundning av mellanresultat. |
| `test_wilder_edge_cases` | 3 | Endast uppgångar, endast nedgångar och platt serie. |
| `test_rsi_gap_requires_fresh_seed` | 1 | Datagap kräver ny fullständig seed. |
| `test_invalid_rsi_period` | 3 | Noll, negativ och icke-heltal avvisas. |
| `test_fx_never_uses_future_and_keeps_off_calendar_history` | 1 | Ingen bakåtfyllning, tidigare FX utanför priskalender bevaras, framtida ändring påverkar inte historik, sen start och tom FX. |
| `test_selected_interest_rate_in_risk_report` | 2 | Fast 2,5 % respektive nollränta mot separat numerisk Sharpe-/Sortino-beräkning. |
| `test_costs_on_initial_derisk_and_buyback` | 1 | Exakta kostnader, kapital och kostnadsfri hållperiod; benchmarkens initialköp; initialkostnad i totalavkastning/drawdown. |
| `test_rebalance_costs_and_benchmark_fairness` | 3 | Månads-, kvartals- och årsrebalansering; exakta målvikter och omsättningskostnader samt identisk KI/B&H utan signaler. |
| `test_simultaneous_signal_and_rebalance_charged_once` | 1 | Partiell avriskning och samtidig schemarebalansering ger en omallokering. |
| `test_invalid_costs_rejected` | 4 | Negativa, för höga och NaN-kostnader avvisas. |
| `test_app_all_report_and_portfolio_call_sites_are_wired` | 1 | Alla sex riskmåttsanrop och fyra portföljkonstruktioner har rätt parametrar; effektiv ränta för båda lägena. |
| `test_initial_cost_in_cagr_calmar_and_drawdown_chart` | 1 | Ursprungligt kapital används även av CAGR/Calmar och grafens drawdown. |
| `test_ui_history_and_reports_offline` | 2 | Fem flikar startar, faktisk historik efter FX-rensning och cykelvarning visas; ändrad ränta ändrar Sharpe och ändrade kostnader ändrar KI-benchmarkens avkastning; enbart framtida FX ger tydligt fel. |

## Verifiering

- Hela sviten: **67 passed**, varav alla 37 befintliga tester fortfarande passerar.
- Alla Python-filer kompilerar utan syntaxfel.
- Testmiljö: Python 3.13.2, pytest 8.4.2, Pandas 2.3.3, NumPy 2.1.3, Streamlit 1.63.0.
- Installation följer befintliga `requirements.txt`; den filen är oförändrad.
- Tester använder syntetiska data. UI-datahämtare är ersatta och nätverksanslutningar spärrade.
- Livehämtning från Yahoo/KI har inte verifierats och inga verkliga backtestresultat hävdas.
- Streamlit loggar befintliga deprecationsmeddelanden för `use_container_width`; ingen av UI-körningarna ger app-undantag. Anropen behålls för kompatibilitet med projektets äldre tillåtna Streamlit-versioner.

## Dokumenterade metodval

URTH/EWD/EEM behålls. EFA ger längre historik men täcker inte USA/Kanada och är därför
inte en likvärdig MSCI World-proxy. Ingen syntetisk skarvning introduceras.
Se källorna och resonemanget i README, avsnitt 20. Den faktiska startdagen beror på
hämtade data; rapporten hittar inte på något live-startdatum.

KI-kostnaden är en additiv bps-modell på omsatt aktievärde med målvikter efter kostnad.
Tekniska motorn behåller sin befintliga separata slippage-prisjustering och kostnadsfria
Buy & Hold. KI:s Buy & Hold har däremot exakt samma kostnadsmodell som KI-strategin.

Initialköpets kostnad ingår i slutvärde, totalavkastning, CAGR, drawdown och Calmar.
Sharpe/Sortino beräknas på avkastning mellan observerade dagsvärden och exkluderar
initialdagens engångsavdrag. Behåll equity.attrs["initial_capital"] vid vidare analys.
Riskmåttens befintliga årsränta/252 och Sortino-definition har bevarats och dokumenterats.
KI:s publiceringslagg är fortfarande en schablon och historiska KI-revideringar modelleras inte.
