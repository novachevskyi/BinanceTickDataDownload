#!/usr/bin/env python3
"""
Binance Trade Data to Freqtrade Feather Converter
Converts Binance archive CSV trade data to Freqtrade format for orderflow backtesting
Supports both single file and batch directory processing
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import glob
from datetime import datetime
import os
import gc
from typing import Optional, List, Tuple

def process_csv_chunk(csv_file: str, chunksize: int = 1000000) -> pd.DataFrame:
    """
    Read large CSV files in chunks to manage memory
    
    Args:
        csv_file: Path to CSV file
        chunksize: Number of rows per chunk
    
    Returns:
        Processed DataFrame with all trades
    """
    chunks = []
    total_rows = 0
    
    try:
        # Read CSV in chunks
        for chunk in pd.read_csv(csv_file, 
                                 names=['id', 'price', 'qty', 'quote_qty', 'time', 'is_buyer_maker'],
                                 chunksize=chunksize):
            chunks.append(chunk)
            total_rows += len(chunk)
            print(f"  Processed {total_rows:,} rows...", end='\r')
        
        print(f"  Loaded {total_rows:,} trades from file")
        return pd.concat(chunks, ignore_index=True)
    
    except Exception as e:
        print(f"  Error reading {csv_file}: {e}")
        return pd.DataFrame()

def convert_trades_to_freqtrade_format(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert Binance trade format to Freqtrade format
    
    Args:
        df: DataFrame with Binance trade data
    
    Returns:
        DataFrame in Freqtrade format
    """
    trades_df = pd.DataFrame()
    
    # Timestamp in milliseconds
    trades_df['timestamp'] = df['time'].astype(np.int64)
    
    # Trade ID
    trades_df['id'] = df['id'].astype(str)
    
    # Type: 'limit' for all trades
    trades_df['type'] = 'limit'
    
    # Side: if is_buyer_maker is True, the taker was a seller (sell)
    # if is_buyer_maker is False, the taker was a buyer (buy)
    trades_df['side'] = df['is_buyer_maker'].apply(lambda x: 'sell' if x else 'buy')
    
    # Price
    trades_df['price'] = df['price'].astype(np.float64)
    
    # Amount (base currency quantity)
    trades_df['amount'] = df['qty'].astype(np.float64)
    
    # Cost (quote currency amount)
    trades_df['cost'] = df['quote_qty'].astype(np.float64)
    
    # Sort by timestamp
    trades_df = trades_df.sort_values('timestamp')
    
    return trades_df

def save_trades_feather(trades_df: pd.DataFrame, output_file: Path, 
                       date_range: Optional[Tuple[datetime, datetime]] = None) -> None:
    """
    Save trades DataFrame to feather file with statistics
    
    Args:
        trades_df: DataFrame with trade data
        output_file: Path to output file
        date_range: Optional tuple of (start_date, end_date) for filename
    """
    # Create directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save as feather file
    trades_df.to_feather(output_file)
    
    # Print statistics
    print(f"  Saved: {output_file.name}")
    print(f"  Trades: {len(trades_df):,}")
    print(f"  Date range: {pd.to_datetime(trades_df['timestamp'].min(), unit='ms').strftime('%Y-%m-%d %H:%M')} to "
          f"{pd.to_datetime(trades_df['timestamp'].max(), unit='ms').strftime('%Y-%m-%d %H:%M')}")
    print(f"  Buy trades: {(trades_df['side'] == 'buy').sum():,}")
    print(f"  Sell trades: {(trades_df['side'] == 'sell').sum():,}")

def aggregate_trades_to_ohlcv(trades_df: pd.DataFrame, timeframe: str, 
                             output_dir: Path, pair_formatted: str, exchange: str) -> pd.DataFrame:
    """
    Aggregate trades to OHLCV candles
    
    Args:
        trades_df: DataFrame with trade data
        timeframe: Candle timeframe (1m, 5m, etc.)
        output_dir: Output directory path
        pair_formatted: Formatted pair name (e.g., BTC_USDT)
        exchange: Exchange name
    
    Returns:
        DataFrame with OHLCV data
    """
    # Convert timeframe to pandas frequency
    timeframe_map = {
        '1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min',
        '1h': '1h', '4h': '4h', '1d': '1D'
    }
    
    if timeframe not in timeframe_map:
        return pd.DataFrame()
    
    freq = timeframe_map[timeframe]
    
    # Set timestamp as index
    trades_df['datetime'] = pd.to_datetime(trades_df['timestamp'], unit='ms')
    trades_df.set_index('datetime', inplace=True)
    
    # Aggregate to OHLCV
    ohlcv = trades_df.groupby(pd.Grouper(freq=freq)).agg({
        'price': ['first', 'max', 'min', 'last'],
        'amount': 'sum'
    })
    
    # Flatten column names
    ohlcv.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Remove NaN rows
    ohlcv = ohlcv.dropna()
    
    # Reset index and convert back to timestamp
    ohlcv.reset_index(inplace=True)
    ohlcv['date'] = ohlcv['datetime'].astype(np.int64) // 10**6  # Convert to milliseconds
    
    # Create final OHLCV dataframe
    final_ohlcv = pd.DataFrame()
    final_ohlcv['date'] = ohlcv['date']
    final_ohlcv['open'] = ohlcv['open']
    final_ohlcv['high'] = ohlcv['high']
    final_ohlcv['low'] = ohlcv['low']
    final_ohlcv['close'] = ohlcv['close']
    final_ohlcv['volume'] = ohlcv['volume']
    
    # Save OHLCV data
    ohlcv_file = output_dir / exchange / f"{pair_formatted}-{timeframe}.feather"
    ohlcv_file.parent.mkdir(parents=True, exist_ok=True)
    final_ohlcv.to_feather(ohlcv_file)
    
    return final_ohlcv

def process_single_csv(csv_file: str, output_dir: str, pair: str = "BTC/USDT", 
                      exchange: str = "binance", create_ohlcv: bool = True,
                      timeframes: List[str] = None) -> Optional[pd.DataFrame]:
    """
    Process a single CSV file
    
    Args:
        csv_file: Path to CSV file
        output_dir: Output directory path
        pair: Trading pair
        exchange: Exchange name
        create_ohlcv: Whether to create OHLCV candles
        timeframes: List of timeframes to create
    
    Returns:
        DataFrame with processed trades or None if error
    """
    if timeframes is None:
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
    
    csv_path = Path(csv_file)
    if not csv_path.exists():
        print(f"  File not found: {csv_file}")
        return None
    
    # Get file size
    file_size_mb = csv_path.stat().st_size / (1024 * 1024)
    print(f"\nProcessing: {csv_path.name} ({file_size_mb:.1f} MB)")
    
    # Read CSV (with chunking for large files)
    if file_size_mb > 100:
        print(f"  Large file detected, reading in chunks...")
        df = process_csv_chunk(csv_file)
    else:
        df = pd.read_csv(csv_file, names=['id', 'price', 'qty', 'quote_qty', 'time', 'is_buyer_maker'])
        print(f"  Loaded {len(df):,} trades")
    
    if df.empty:
        return None
    
    # Convert to Freqtrade format
    trades_df = convert_trades_to_freqtrade_format(df)
    
    # Extract date from filename if possible (e.g., BTCUSDT-trades-2024-01.csv)
    pair_formatted = pair.replace('/', '_')
    filename_parts = csv_path.stem.split('-')
    
    if len(filename_parts) >= 4 and filename_parts[-2].isdigit() and filename_parts[-1].isdigit():
        # Has year-month in filename
        year_month = f"{filename_parts[-2]}-{filename_parts[-1]}"
        output_file = Path(output_dir) / exchange / f"{pair_formatted}-trades-{year_month}.feather"
    else:
        # Generic filename
        output_file = Path(output_dir) / exchange / f"{pair_formatted}-trades-{csv_path.stem}.feather"
    
    # Save trades
    save_trades_feather(trades_df, output_file)
    
    # Create OHLCV candles if requested
    if create_ohlcv:
        print(f"  Creating OHLCV candles...")
        for timeframe in timeframes:
            ohlcv_df = aggregate_trades_to_ohlcv(
                trades_df.copy(), timeframe, Path(output_dir), 
                pair_formatted, exchange
            )
            if not ohlcv_df.empty:
                print(f"    {timeframe}: {len(ohlcv_df):,} candles")
    
    # Clean up memory
    del df
    gc.collect()
    
    return trades_df

def process_folder(input_folder: str, output_dir: str, pair: str = "BTC/USDT", 
                  exchange: str = "binance", combine_files: bool = True, 
                  create_ohlcv: bool = True, timeframes: List[str] = None) -> None:
    """
    Process all CSV files in a folder
    
    Args:
        input_folder: Path to folder containing CSV files
        output_dir: Output directory path
        pair: Trading pair
        exchange: Exchange name
        combine_files: Whether to combine all files into one
        create_ohlcv: Whether to create OHLCV candles
        timeframes: List of timeframes to create
    """
    if timeframes is None:
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
    
    # Find all CSV files
    csv_files = sorted(glob.glob(os.path.join(input_folder, "*.csv")))
    
    if not csv_files:
        print(f"No CSV files found in {input_folder}")
        return
    
    print(f"Found {len(csv_files)} CSV files in {input_folder}")
    print("=" * 60)
    
    all_trades = []
    failed_files = []
    
    # Process each file
    for i, csv_file in enumerate(csv_files, 1):
        print(f"\n[{i}/{len(csv_files)}] ", end="")
        
        trades_df = process_single_csv(
            csv_file, output_dir, pair, exchange, 
            create_ohlcv=False  # We'll create OHLCV later if combining
        )
        
        if trades_df is not None:
            all_trades.append(trades_df)
        else:
            failed_files.append(csv_file)
    
    print("\n" + "=" * 60)
    
    # Report any failures
    if failed_files:
        print(f"\nFailed to process {len(failed_files)} files:")
        for f in failed_files:
            print(f"  - {Path(f).name}")
    
    # Combine files if requested
    if combine_files and len(all_trades) > 1:
        print(f"\nCombining {len(all_trades)} files...")
        
        # Combine all trades
        combined_trades = pd.concat(all_trades, ignore_index=True)
        combined_trades = combined_trades.sort_values('timestamp')
        combined_trades = combined_trades.drop_duplicates(subset=['id'], keep='first')
        
        # Save combined file
        pair_formatted = pair.replace('/', '_')
        combined_file = Path(output_dir) / exchange / f"{pair_formatted}-trades-combined.feather"
        
        print(f"Combined statistics:")
        save_trades_feather(combined_trades, combined_file)
        
        # Create OHLCV from combined trades
        if create_ohlcv:
            print(f"\nCreating combined OHLCV candles...")
            for timeframe in timeframes:
                ohlcv_df = aggregate_trades_to_ohlcv(
                    combined_trades.copy(), timeframe, Path(output_dir),
                    pair_formatted, exchange
                )
                if not ohlcv_df.empty:
                    print(f"  {timeframe}: {len(ohlcv_df):,} candles")
        
        # Clean up memory
        del combined_trades
        gc.collect()
    
    elif not combine_files and all_trades and create_ohlcv:
        # Create OHLCV for each file separately
        print(f"\nCreating OHLCV candles for individual files...")
        for trades_df in all_trades:
            for timeframe in timeframes:
                aggregate_trades_to_ohlcv(
                    trades_df.copy(), timeframe, Path(output_dir),
                    pair.replace('/', '_'), exchange
                )
    
    # Clean up memory
    del all_trades
    gc.collect()

def main():
    """
    Main function for command-line usage
    """
    
    # ============================================
    # CONFIGURATION - MODIFY THESE SETTINGS
    # ============================================
    
    # Input: Folder containing Binance CSV files OR single CSV file
    INPUT_PATH = "/path/to/your/binance/csv/folder"  # Folder with CSVs
    # INPUT_PATH = "/path/to/single/file.csv"  # Or single file
    
    # Output: Path to your Freqtrade installation
    FREQTRADE_DIR = "/path/to/freqtrade"
    OUTPUT_DIR = f"{FREQTRADE_DIR}/user_data/data"
    
    # Trading pair (must match what you'll use in strategy)
    PAIR = "BTC/USDT"
    
    # Exchange name (for directory structure)
    EXCHANGE = "binance"
    
    # Whether to combine all CSV files into one large file
    # True: Create one combined file (better for continuous backtesting)
    # False: Keep files separate (better for memory management)
    COMBINE_FILES = True
    
    # Whether to create OHLCV candles from trades
    CREATE_OHLCV = True
    
    # Which timeframes to create (comment out any you don't need)
    TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d']
    
    # ============================================
    # END CONFIGURATION
    # ============================================
    
    print("=" * 60)
    print("Binance to Freqtrade Data Converter")
    print("=" * 60)
    
    input_path = Path(INPUT_PATH)
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {INPUT_PATH}")
        sys.exit(1)
    
    # Check if input is a folder or file
    if input_path.is_dir():
        print(f"Mode: Folder processing")
        print(f"Input folder: {INPUT_PATH}")
        print(f"Combine files: {COMBINE_FILES}")
        process_folder(
            INPUT_PATH, OUTPUT_DIR, PAIR, EXCHANGE,
            combine_files=COMBINE_FILES,
            create_ohlcv=CREATE_OHLCV,
            timeframes=TIMEFRAMES
        )
    else:
        print(f"Mode: Single file processing")
        print(f"Input file: {INPUT_PATH}")
        process_single_csv(
            INPUT_PATH, OUTPUT_DIR, PAIR, EXCHANGE,
            create_ohlcv=CREATE_OHLCV,
            timeframes=TIMEFRAMES
        )
    
    # Print final summary
    print("\n" + "=" * 60)
    print("CONVERSION COMPLETE!")
    print("=" * 60)
    
    pair_formatted = PAIR.replace('/', '_')
    data_path = Path(OUTPUT_DIR) / EXCHANGE
    
    print("\nOutput files location:")
    print(f"  {data_path}/")
    
    # List created files
    trade_files = sorted(data_path.glob(f"{pair_formatted}-trades*.feather"))
    ohlcv_files = sorted(data_path.glob(f"{pair_formatted}-*.feather"))
    ohlcv_files = [f for f in ohlcv_files if 'trades' not in f.name]
    
    if trade_files:
        print("\nTrade files created:")
        for f in trade_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  - {f.name} ({size_mb:.1f} MB)")
    
    if ohlcv_files:
        print("\nOHLCV files created:")
        for f in ohlcv_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  - {f.name} ({size_mb:.1f} MB)")
    
    print("\nTo use in Freqtrade:")
    print("1. Enable orderflow in config.json:")
    print("   'use_public_trades': true")
    print("2. Configure orderflow settings")
    print("3. Run backtesting:")
    print(f"   freqtrade backtesting --strategy YourStrategy --timeframe 5m")
    
    if COMBINE_FILES and len(trade_files) > 1:
        print("\nNote: Files were combined. Use the 'combined' file for continuous backtesting")

if __name__ == "__main__":
    # Check required libraries
    try:
        import pandas
        import numpy
        import pyarrow
    except ImportError as e:
        print(f"Missing required library: {e}")
        print("\nPlease install required libraries:")
        print("  pip install pandas numpy pyarrow")
        sys.exit(1)
    
    main()
