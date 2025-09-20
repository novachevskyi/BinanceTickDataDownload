#!/usr/bin/env python3
"""
Convert Binance monthly trade files to Sierra Chart tick CSV format with Symbol column.
FIXED VERSION with manual volume multiplier input.

Usage:
  1. Download monthly ZIP(s) from: https://data.binance.vision/
  2. Unzip to a folder (e.g., BTCUSDT-trades-2024-12.csv).
  3. Run: python3 binance_to_sierra_ticks_fixed.py --input folder_with_csvs --output sierra_ticks.csv
"""

import os
import csv
import argparse
from datetime import datetime, timezone, timedelta

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", "-i", required=True, help="Folder with Binance trade CSV files.")
    p.add_argument("--output", "-o", required=True, help="Output Sierra CSV file path.")
    p.add_argument("--tz-offset-hours", "-t", type=float, default=0.0,
                   help="Timezone offset hours (default 0 = UTC).")
    p.add_argument("--sample-limit", type=int, default=0,
                   help="Limit number of records processed (0 = all).")
    return p.parse_args()

def is_trade_file(filename):
    fn = filename.lower()
    return ('trades' in fn or 'aggtrades' in fn) and fn.endswith('.csv')

def extract_symbol_from_filename(filename):
    base = os.path.basename(filename)
    parts = base.split('-')
    if len(parts) >= 2:
        return parts[0].upper()
    return "UNKNOWN"

def convert_timestamp_ms(ms, tz_offset_hours=0.0):
    ts = int(ms) / 1000.0
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if tz_offset_hours != 0.0:
        dt = dt + timedelta(hours=tz_offset_hours)
    return dt

def main():
    args = parse_args()
    input_folder = args.input
    output_file = args.output
    tz_offset = args.tz_offset_hours
    sample_limit = args.sample_limit
    
    # Get volume multiplier from user input
    print("Enter volume multiplier (10000 for Sierra Chart compatibility): ", end="")
    volume_multiplier = float(input().strip() or "1")
    print(f"Using volume multiplier: {volume_multiplier}")

    files = sorted([os.path.join(input_folder, f) for f in os.listdir(input_folder) if is_trade_file(f)])
    if not files:
        print("No trade CSV files found in folder:", input_folder)
        return

    header = ['Symbol', 'Date', 'Time', 'Open', 'High', 'Low', 'Last', 'Volume', 'NumberOfTrades', 'BidVolume', 'AskVolume']
    total_written = 0

    with open(output_file, 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(header)
        print(f"Writing to {output_file}")

        for file in files:
            symbol = extract_symbol_from_filename(file)
            print(f"\nProcessing {os.path.basename(file)} (symbol: {symbol})")
            
            skipped = 0
            processed = 0

            try:
                with open(file, 'r', newline='') as fin:
                    reader = csv.DictReader(fin)  # Use DictReader for proper header handling
                    
                    # Check if we have the expected columns
                    fieldnames = reader.fieldnames
                    print(f"  Columns found: {fieldnames}")
                    
                    required_fields = ['price', 'qty', 'time', 'is_buyer_maker']
                    missing_fields = [f for f in required_fields if f not in fieldnames]
                    if missing_fields:
                        print(f"  ERROR: Missing required fields: {missing_fields}")
                        continue

                    for row in reader:
                        processed += 1
                        
                        if processed <= 3:  # Show first few rows for debugging
                            print(f"  Row {processed}: price={row['price']}, qty={row['qty']}, time={row['time']}, is_buyer_maker={row['is_buyer_maker']}")
                        
                        if processed % 50000 == 0:
                            print(f"  Processed {processed} rows...")

                        try:
                            # Extract values
                            price_f = float(row['price'])
                            qty_f = float(row['qty'])
                            ts_ms = int(row['time'])
                            is_buyer_maker_str = row['is_buyer_maker'].lower().strip()
                            
                            # Convert timestamp
                            dt = convert_timestamp_ms(ts_ms, tz_offset_hours=tz_offset)
                            date_str = dt.strftime('%Y%m%d')
                            time_str = dt.strftime('%H:%M:%S.%f')[:-3]  # milliseconds
                            
                            # For tick data, OHLC are all the same (the trade price)
                            last = price_f
                            openp = price_f
                            high = price_f
                            low = price_f
                            
                            # Use qty (BTC volume) and apply multiplier
                            volume = qty_f * volume_multiplier
                            number_of_trades = 1
                            
                            # Determine bid/ask volume based on maker flag
                            is_buyer_maker = is_buyer_maker_str in ('true', '1', 't', 'y', 'yes')
                            if is_buyer_maker:
                                bid_volume = volume  # Buyer was maker = sell order hit = bid volume
                                ask_volume = 0.0
                            else:
                                bid_volume = 0.0
                                ask_volume = volume  # Seller was maker = buy order hit = ask volume

                            # Write the tick
                            writer.writerow([
                                symbol, 
                                date_str, 
                                time_str, 
                                f"{openp:.8f}", 
                                f"{high:.8f}",
                                f"{low:.8f}", 
                                f"{last:.8f}", 
                                f"{volume:.8f}",
                                number_of_trades, 
                                f"{bid_volume:.8f}", 
                                f"{ask_volume:.8f}"
                            ])
                            total_written += 1

                        except (ValueError, KeyError) as e:
                            skipped += 1
                            if skipped <= 5:  # Only show first few errors
                                print(f"  Skipped row {processed}: {e}")
                            continue

                        if sample_limit and total_written >= sample_limit:
                            print(f"Sample limit reached: {sample_limit}")
                            break

                print(f"  Processed: {processed}, Written: {total_written - (total_written - processed + skipped)}, Skipped: {skipped}")

            except Exception as e:
                print(f"  Error processing {file}: {e}")
                continue

            if sample_limit and total_written >= sample_limit:
                break

    print(f"\nDone! Total records written: {total_written:,}")
    print(f"Output file: {output_file}")

if __name__ == '__main__':
    main()
