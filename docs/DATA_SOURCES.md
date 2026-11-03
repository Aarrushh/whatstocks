# Data source check (2026-11-03)

This file records what each free data source returned when tested, before
any code was written. The test covered 97 symbols (every demo holding,
every theme member, every theme proxy, and the benchmark). It ran from one
machine in Europe with **no API keys**, using `yfinance` 1.7.0 and plain
HTTP requests.

## Summary

| Source | Used for | Result | Verdict |
|---|---|---|---|
| Yahoo via `yfinance` | Prices | 97 of 97 symbols returned data, with the last close dated 2026-11-02 or 2026-11-03. Full history since Dec 2019 downloaded in 14 s. | **Use** |
| Stooq CSV | Backup prices | Every request returned a JavaScript bot-check page instead of a CSV. | **Not usable.** whatstocks does not get around bot checks. |
| ECB data API | FX | All 9 currencies needed (USD, GBP, INR, HKD, CHF, AUD, DKK, SEK, NOK) returned, dated today. | **Use** |
| iShares holdings CSV | Fund look-through | Both the US `ACWI` and UCITS `SSAC`/`IUSQ` files downloaded (1,700 to 2,250 rows, as of 2026-11-02). The old `.ajax?fileType=csv` link now returns an HTML page. The working link is `/latest-holdings.csv` on the product page. | **Use**, with the fixes below |
| Vanguard (VWCE) | Fund look-through | Not tested. | Open (see below) |
| GDELT DOC 2.0 API | News | One empty response, then HTTP 429 ("one request every 5 seconds") on every later request, even with 20 to 30 seconds between them. | **Optional only.** Too unreliable to be the main news source. |
| RSS feeds | News | BBC Business, BBC World, Al Jazeera, CNBC World, Guardian Business, Economic Times Markets and a Google News search feed all returned 25 to 62 items dated today. | **Use as the main source** |

## Findings that change the design

### 1. There is no key-free backup for prices

Stooq was the only candidate, and it now blocks scripts. That leaves two
options:

- **(a) Cache as the backup.** Prices are cached on disk. If Yahoo fails, the page uses the last cached prices and shows a "prices from <date>" banner. Needs no key. **Recommended for v1.**
- **(b) Optional keyed backup.** Users who add a free key for a service such as Twelve Data, Alpha Vantage or Tiingo get a second live source. Not tested. Free tiers have daily limits, and their coverage outside the US is unverified.

**Decided 2026-11-03: (a).** The owner chose the cache as the backup (SPEC section 12, decision 3).

### 2. Look-through must match on ticker and exchange

Matching fund holdings by ticker alone gave a wrong match: theme member
`BA.L` (BAE Systems, London) matched `BA` (Boeing, NYSE). The code needs to
map each Yahoo suffix to the exchange names used in the holdings file, and
match on both.

### 3. Exchange names differ between issuer files

The US iShares file says `NYSE`. The UCITS file from the same issuer says
`New York Stock Exchange Inc.` The exchange map must accept several names
for each suffix.

### 4. One company can have several lines

Index funds hold the home-market line, while theme lists often name the US
line. The tested cases were TSM → `2330.TW`, CCJ → `CCO.TO`, BABA →
`9988.HK`, JD → `9618.HK`, BIDU → `9888.HK`, AEM → `AEM.TO`, FNV →
`FNV.TO`, GFI → `GFI.JO` and SQM → `SQM-B.SN`.

Without these alias lines, TSMC (1.74% of ACWI) is missed completely. A
company must be counted once, even when it matches through two lines.

### 5. Funds can hold other funds

The UCITS ACWI fund (`SSAC`/`IUSQ`) holds its Indian stocks through
another ETF: `NDIA`, iShares MSCI India UCITS, at 1.34%. Read one level
deep, the file shows India at 0.03%. Look-through has to recurse into
fund-in-fund rows, or India disappears from any European world fund.

### 6. Benchmark file

The US `ACWI` fund tracks the same index and lists its 163 Indian stocks
directly (1.23% weight). **Recommendation:** use the US `ACWI` holdings file
for benchmark look-through, and keep `IUSQ.DE` for the benchmark's euro
price series.

### 7. Smaller data quirks

- **Pence:** 5 London symbols are quoted in `GBp` (pence), so prices must be divided by 100.
- **KAP.L:** Yahoo has data only from 2026-07-17, although the Kazatomprom GDR has traded for much longer. This is either a line change or a Yahoo gap. Check it before relying on it.
- **Short histories:** 6 symbols start after the 2020 Covid window: HAG.DE, MP, ZIM, CEG, GEV and KAP.L. Crash replay has to show its coverage, as the spec already says.
- **GDELT:** if it is used at all, it needs a cache, one query at a time at least 5 seconds apart, and a quiet fallback to RSS.
- **Google News search RSS** is an unofficial endpoint. It works today and may change without notice.

## First real benchmark numbers

These are ACWI theme shares from the starter `themes.yaml`, computed from
the US `ACWI` file dated 2026-11-02, with the fixes above applied. They are
theme shares, not country weights. The `india` and `china` themes list only
7 names each, so they understate those countries. Region exposure is a
separate measure.

| Theme | ACWI share | Members not in the fund |
|---|---|---|
| AI build-out | 15.5% | none |
| Oil and gas | 2.1% | none |
| Defence | 1.0% | none |
| Power grid | 0.9% | none |
| China (7 names) | 0.6% | none |
| India (7 names) | 0.4% | none |
| Gold | 0.3% | none |
| Nuclear and uranium | 0.2% | KAP.L, NXE, UEC, LEU, BWXT |
| Critical minerals | 0.1% | MP, ILU.AX, ALB |
| Shipping routes | 0.04% | HLAG.DE, ZIM, FRO, STNG, SBLK |

**Sensitivity:** counting Microsoft, Alphabet, Amazon, Meta and Oracle as
`core` instead of `partial` raises the ACWI AI share from about 15% to
about 20%. That one tagging choice moves the headline number by 5 points,
which is why the page must list the names it counted.

## Not yet tested

- **Vanguard holdings for VWCE** (FTSE All-World). If no stable file exists, VWCE can be looked through with the ACWI file and labelled "approximated with MSCI ACWI". The two indexes overlap heavily but are not the same.
- **Other issuers:** SPDR, Invesco, Amundi and Xtrackers.
- **FRED and EIA**, which need free keys and are only used to resolve views.
