# SCBinanceTickDataDownload
Downloads data from Binance archives and converts to CSV format supported by Sierra Chart.

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
