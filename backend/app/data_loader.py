import os
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Configuration
# Use absolute paths to ensure it works on Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRICES_FILE = os.path.join(BASE_DIR, "data", "prices.parquet")

# Your Tickers
TICKERS = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    "SPY", "^IRX", "VNQ", "VOX"
]
START_DATE = "2005-01-01"

# Markets are closed on weekends/holidays, so the most recent available data
# point is frequently a few calendar days old. Treat data as fresh if it is
# within this many calendar days of today (covers weekends + most holidays)
# instead of requiring it to be dated today, which forced a re-download on
# every weekend/holiday startup.
FRESHNESS_TOLERANCE_DAYS = 4


def ensure_data_freshness():
    """Checks if cached data is recent enough. If not, updates it in place."""
    # Ensure directory exists
    if not os.path.exists(os.path.dirname(PRICES_FILE)):
        os.makedirs(os.path.dirname(PRICES_FILE))

    existing = _read_cache()

    if existing is not None:
        last_data_date = existing.index.max().date()
        today = datetime.now().date()
        staleness_days = (today - last_data_date).days

        # Fresh if the most recent data point is within tolerance (covers
        # weekends + holidays when no new market data is expected).
        if staleness_days <= FRESHNESS_TOLERANCE_DAYS:
            logger.info("Data is fresh (Last date: %s, %dd old). Loading from cache.", last_data_date, staleness_days)
            return
        logger.info("Data is stale (Last date: %s, %dd old). Refreshing...", last_data_date, staleness_days)
    else:
        logger.info("No usable cache found. Downloading full history...")

    _refresh_data(existing)


def download_and_flatten(tickers, start_date):
    """Download prices from Yahoo Finance and flatten them into a single-level
    price DataFrame (Adj Close preferred, then Close) with a tz-naive
    DatetimeIndex. Shared by the cache writer below and engine.download_prices()
    so the download + flattening logic lives in exactly one place.
    """
    # Disable yfinance cache to prevent 'database is locked' on Render
    try:
        yf.set_tz_cache_location("/tmp/yf_cache")
    except Exception as e:
        logger.warning("Could not set yfinance cache location: %s", e)

    data = yf.download(tickers, start=start_date, auto_adjust=False, progress=False)

    if isinstance(data.columns, pd.MultiIndex):
        if 'Adj Close' in data.columns.get_level_values(0):
            px = data['Adj Close']
        elif 'Close' in data.columns.get_level_values(0):
            logger.warning("'Adj Close' not found. Using 'Close'.")
            px = data['Close']
        else:
            logger.warning("Unknown column structure. Using raw data.")
            px = data
    else:
        if "Adj Close" in data.columns:
            px = data["Adj Close"]
        elif "Close" in data.columns:
            px = data["Close"]
        else:
            px = data

    # Explicitly remove timezones
    if px.index.tz is not None:
        px.index = px.index.tz_localize(None)
    px.index = pd.to_datetime(px.index)
    px = px.dropna(axis=1, how='all')
    if hasattr(px, "columns"):
        px.columns.name = None
    return px


def _read_cache():
    """Load the cached price frame, or None if missing/empty/unreadable."""
    if not os.path.exists(PRICES_FILE):
        return None
    try:
        df = pd.read_parquet(PRICES_FILE)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df if not df.empty else None
    except Exception as e:
        logger.warning("Could not read cache (%s).", e)
        return None


def _save_cache(px):
    try:
        px.to_parquet(PRICES_FILE)
        logger.info("Data saved to %s. Shape: %s", PRICES_FILE, px.shape)
        return True
    except Exception as e:
        logger.error("Error saving parquet: %s", e)
        return False


def _merge_frames(existing, fresh):
    """Combine cached + freshly downloaded prices, preferring fresh values on
    overlapping dates and keeping rows sorted by date."""
    if fresh is None or fresh.empty:
        return existing
    if existing is None or existing.empty:
        return fresh.sort_index()
    combined = pd.concat([existing, fresh])
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined.sort_index()


def _refresh_data(existing):
    """Bring the price cache up to today.

    If we already have cached data, download only the recent tail (incremental,
    fast, less failure-prone) and merge it in. With no cache, or if the
    incremental fetch fails/returns nothing, fall back to a full history
    download. The existing cache is NEVER overwritten with empty data, so a
    failed network call leaves the last good data intact.
    """
    fresh = None

    # 1) Incremental update when we already have a cache.
    if existing is not None and not existing.empty:
        last_date = existing.index.max().date()
        # Re-fetch a small overlap window to absorb any vendor revisions.
        inc_start = (last_date - timedelta(days=7)).strftime("%Y-%m-%d")
        try:
            logger.info("Incremental refresh from %s ...", inc_start)
            fresh = download_and_flatten(TICKERS, inc_start)
        except Exception as e:
            logger.warning("Incremental download failed (%s). Trying full history...", e)
            fresh = None

    # 2) Full download (no cache, or incremental came back empty/failed).
    if fresh is None or fresh.empty:
        try:
            logger.info("Full history download from %s ...", START_DATE)
            fresh = download_and_flatten(TICKERS, START_DATE)
        except Exception as e:
            logger.error("CRITICAL DOWNLOAD ERROR: %s", e)
            fresh = None

    # Never destroy good data with an empty/failed download.
    if fresh is None or fresh.empty or len(fresh.columns) == 0:
        logger.error("No fresh data downloaded; keeping existing cache.")
        return existing

    combined = _merge_frames(existing, fresh)
    _save_cache(combined)
    return combined


def _download_and_save():
    """Backwards-compatible full refresh entry point."""
    _refresh_data(_read_cache())


def load_data():
    """Returns the prices DataFrame."""
    ensure_data_freshness()
    if not os.path.exists(PRICES_FILE):
        logger.error("Error: Prices file not found after download attempt.")
        return pd.DataFrame()

    df = pd.read_parquet(PRICES_FILE)
    # Double check timezone on load
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


if __name__ == "__main__":
    # Manual refresh helper: run `python -m app.data_loader` from backend/ to
    # force an update and print how current the data is.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    prices = load_data()
    if prices.empty:
        print("No data available (download failed and no cache).")
    else:
        print("Rows:", len(prices))
        print("Columns:", list(prices.columns))
        print("Data through:", prices.index.max().date())
