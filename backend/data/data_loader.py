import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# Configuration
DATA_DIR = "data"
PRICES_FILE = os.path.join(DATA_DIR, "prices.parquet")

# Your Tickers
TICKERS = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    "SPY", "^IRX", "VNQ", "VOX"
]
START_DATE = "2005-01-01"


def ensure_data_freshness():
    """Checks if data is fresh (updated today). If not, downloads it."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    needs_update = True
    if os.path.exists(PRICES_FILE):
        try:
            # Check modification time
            mod_time = datetime.fromtimestamp(os.path.getmtime(PRICES_FILE))
            if mod_time.date() == datetime.now().date():
                needs_update = False
                print("Data is fresh. Loading from cache.")
        except Exception:
            pass

    if needs_update:
        print("Data is stale or missing. Downloading from Yahoo...")
        _download_and_save()


def _download_and_save():
    print(f"--- Downloading tickers: {len(TICKERS)} ---")

    # Download
    try:
        data = yf.download(TICKERS, start=START_DATE, auto_adjust=False, progress=False)
    except Exception as e:
        print(f"CRITICAL DOWNLOAD ERROR: {e}")
        return

    # --- AGGRESSIVE FLATTENING LOGIC ---
    # yfinance often returns MultiIndex columns like ('Adj Close', 'AAPL')
    # We want just 'AAPL'.

    px = pd.DataFrame()

    # Case 1: MultiIndex Columns (Standard yfinance behavior for multiple tickers)
    if isinstance(data.columns, pd.MultiIndex):
        # Try to grab 'Adj Close' level
        if 'Adj Close' in data.columns.get_level_values(0):
            px = data['Adj Close']
        elif 'Close' in data.columns.get_level_values(0):
            print("Warning: 'Adj Close' not found. Using 'Close'.")
            px = data['Close']
        else:
            # Fallback: The levels might be flipped or weird.
            # Let's try to just pull the float data if possible.
            print("Warning: Unknown column structure. Using raw data.")
            px = data
    else:
        # Case 2: Single Level Index (Rare for multiple tickers, but possible)
        # If columns are just tickers, great. If they are 'Open', 'High'... we need 'Adj Close'.
        if "Adj Close" in data.columns:
            px = data["Adj Close"]  # This would imply single ticker, which isn't our case, but good safety.
        else:
            px = data

    # Clean Index
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px.columns.name = None

    # Validation: Ensure we actually have columns
    if px.empty or len(px.columns) == 0:
        print("ERROR: Downloaded dataframe is empty or has no columns!")
        return

    # Save
    px.to_parquet(PRICES_FILE)
    print(f"Data saved to {PRICES_FILE}. Shape: {px.shape}")
    print(f"Columns: {list(px.columns)[:5]}...")


def load_data():
    """Returns the prices DataFrame."""
    ensure_data_freshness()
    if not os.path.exists(PRICES_FILE):
        return pd.DataFrame()
    return pd.read_parquet(PRICES_FILE)