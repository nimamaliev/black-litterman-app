import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# Configuration
DATA_DIR = "data"
# On Render, we might be inside 'backend/data' or just 'data'. 
# Let's use absolute paths to be safe.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRICES_FILE = os.path.join(BASE_DIR, "data", "prices.parquet")

# Your Tickers
TICKERS = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    "SPY", "^IRX", "VNQ", "VOX"
]
START_DATE = "2005-01-01"

def ensure_data_freshness():
    """Checks if data is fresh (updated today). If not, downloads it."""
    # Ensure directory exists
    if not os.path.exists(os.path.dirname(PRICES_FILE)):
        os.makedirs(os.path.dirname(PRICES_FILE))

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
    
    # FIX: Disable yfinance cache to prevent 'database is locked' on Render
    try:
        yf.set_tz_cache_location("/tmp/yf_cache") # Try moving cache to tmp
    except:
        pass # If fails, ignore

    try:
        # Download data
        data = yf.download(TICKERS, start=START_DATE, auto_adjust=False, progress=False)
    except Exception as e:
        print(f"CRITICAL DOWNLOAD ERROR: {e}")
        return

    # --- FLATTENING LOGIC ---
    px = pd.DataFrame()
    
    if isinstance(data.columns, pd.MultiIndex):
        if 'Adj Close' in data.columns.get_level_values(0):
            px = data['Adj Close']
        elif 'Close' in data.columns.get_level_values(0):
            print("Warning: 'Adj Close' not found. Using 'Close'.")
            px = data['Close']
        else:
            print("Warning: Unknown column structure. Using raw data.")
            px = data
    else:
        if "Adj Close" in data.columns:
            px = data["Adj Close"]
        else:
            px = data

    # FIX: Explicitly remove timezones
    if px.index.tz is not None:
        px.index = px.index.tz_localize(None)
    
    px.index = pd.to_datetime(px.index)
    px.columns.name = None
    
    # Validation
    if px.empty or len(px.columns) == 0:
        print("ERROR: Downloaded dataframe is empty or has no columns!")
        return

    # Save
    try:
        px.to_parquet(PRICES_FILE)
        print(f"Data saved to {PRICES_FILE}. Shape: {px.shape}")
    except Exception as e:
        print(f"Error saving parquet: {e}")

def load_data():
    """Returns the prices DataFrame."""
    ensure_data_freshness()
    if not os.path.exists(PRICES_FILE):
        print("Error: Prices file not found after download attempt.")
        return pd.DataFrame()
    
    df = pd.read_parquet(PRICES_FILE)
    # Double check timezone on load
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df

