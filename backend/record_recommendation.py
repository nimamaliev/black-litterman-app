"""Append today's live recommendation to the track record.

Run from backend/ (the GitHub Actions workflow does this every weekday):

    python record_recommendation.py [--file PATH]

It refreshes prices from Yahoo Finance, computes the current recommendation
with no discretionary views, and appends one row per data date to
track_record/recommendations.csv. Re-running on the same data date is a no-op.
"""
import argparse
import logging
import sys

from app import data_loader
from app.engine import BLEngine
from app.track_record import TRACK_FILE, append_row, build_row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=TRACK_FILE)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    prices = data_loader.load_data()
    if prices.empty:
        sys.exit("No price data available.")
    row = build_row(BLEngine(prices))
    if append_row(row, args.file):
        print(f"Recorded recommendation for {row['data_date']} -> {args.file}")
    else:
        print(f"A recommendation for {row['data_date']} is already recorded; nothing to do.")


if __name__ == "__main__":
    main()
