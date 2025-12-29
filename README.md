# BinanceTickDataDownload
Downloads data from Binance archives and converts to CSV format supported by Sierra Chart and Freqtrade.

https://orderflowtriggers.gumroad.com/l/scbinance

## Freqtrade conversion

How to Use

Set up your configuration (lines 285-304):

python# Point to your folder with all CSV files
INPUT_PATH = "/path/to/binance/csvs"  

### Your Freqtrade directory
FREQTRADE_DIR = "/home/username/freqtrade"

### Choose whether to combine files
COMBINE_FILES = True  # Recommended for continuous backtesting

### Select timeframes you need
TIMEFRAMES = ['1m', '5m', '15m', '1h']  # Remove any you don't need

Run the script:
```
bashpython binance_trades_to_feather.py
```
Example Output
Found 5 CSV files in /data/binance/csvs
============================================================
```
[1/5] Processing: BTCUSDT-trades-2024-01.csv (342.5 MB)
  Large file detected, reading in chunks...
  Loaded 5,234,567 trades
  Saved: BTC_USDT-trades-2024-01.feather
  Trades: 5,234,567
  Date range: 2024-01-01 00:00 to 2024-01-31 23:59
  Buy trades: 2,617,283
  Sell trades: 2,617,284

[2/5] Processing: BTCUSDT-trades-2024-02.csv (298.1 MB)
  ...

Combining 5 files...
Combined statistics:
  Saved: BTC_USDT-trades-combined.feather
  Trades: 25,172,835
  Date range: 2024-01-01 00:00 to 2024-05-31 23:59
```

## Important
Conversion script takes multiplier as a parameter. It's being used to multiply raw tick data Qty value to match SC's **Chart Settings -> Symbol -> Tick Size**
For example, for BTCUSDT perp Binance pair there is 0.001 default Tick Size value. If chart is using 10.0 instead then converter should get 10000 multiplier input value.

## 📂 Where to put your CSV

Find your Sierra Chart Data folder (default is something like): **C:\SierraChart\Data**

## ✅ Importing a CSV into Sierra Chart
Disconnect from the Data Feed first:
**File → Disconnect**

Go to menu:
**Edit → Import and Load Intraday Data**

Line format: 
**Symbol, Date, Time, Open, High, Low, Last, Volume, NumberOfTrades, BidVolume, AskVolume**

## Example calls
Data download:
```
python3 download_binance_ticks.py --symbol BTCUSDT --asset_class um --date_start 2025-06-19 --date_end 2025-06-20 --tempdir temp_binance
```

Data conversion:
```
python3 binance_to_sierra_ticks_mult.py --input ./temp_binance/futures/um/daily/trades/BTCUSDT/ --output sierra_ticks_btcusdt.csv
```

# Dependencies
https://pypi.org/project/binance-historical-data/?utm_source=chatgpt.com

Last used version: binance-historical-data 0.1.14

# Data Source
https://data.binance.vision/
