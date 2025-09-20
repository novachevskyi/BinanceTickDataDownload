#!/usr/bin/env python3
"""
binance_data_downloader.py

Downloads Binance trade data (spot / um / cm) using binance_historical_data package.

Usage example:
python3 binance_data_downloader.py \
  --symbol BTCUSDT --asset_class um \
  --date_start 2025-07-19 --date_end 2025-09-19 \
  --tempdir temp_binance

Notes:
- tempdir is where binance_historical_data will dump the downloaded files
- Supports spot, um (USDT-M futures), and cm (COIN-M futures) markets
"""

import os
import argparse
import inspect
import datetime as dt

# Try imports for binance_historical_data
try:
    from binance_historical_data.data_dumper import BinanceDataDumper
except Exception:
    try:
        from binance_historical_data import BinanceDataDumper
    except Exception:
        BinanceDataDumper = None


def build_init_kwargs(sig_params, tempdir, asset_class, data_type="trades", symbols=None):
    """Build initialization kwargs for BinanceDataDumper based on available parameters."""
    params = set(sig_params.keys())
    kwargs = {}

    # Path-like parameter candidates
    for p in ("data_dir", "path_dir_where_to_dump", "path", "path_dir", "dir", "base_path", "root_path"):
        if p in params:
            kwargs[p] = tempdir
            break

    # Asset class parameter
    for p in ("asset_class", "asset", "assetclass"):
        if p in params:
            kwargs[p] = asset_class
            break

    # Data type parameter
    for p in ("data_type", "data_type_name", "data_type_str"):
        if p in params:
            kwargs[p] = data_type
            break

    # Symbols parameter
    for p in ("symbols", "symbol", "tickers", "tickers_list", "pairs", "instruments"):
        if p in params and symbols is not None:
            # Some constructors expect list, some a single symbol
            if p.endswith("s") or p in ("symbols", "tickers", "tickers_list", "pairs"):
                kwargs[p] = symbols
            else:
                kwargs[p] = symbols[0] if isinstance(symbols, (list, tuple)) else symbols
            break

    return kwargs


def init_dumper_adaptive(tempdir, asset_class, data_type, symbols):
    """Initialize BinanceDataDumper with adaptive parameter detection."""
    if BinanceDataDumper is None:
        raise RuntimeError("binance_historical_data package not installed. Install: pip install binance_historical_data")
    
    sig = inspect.signature(BinanceDataDumper.__init__)
    init_kwargs = build_init_kwargs(sig.parameters, tempdir, asset_class, data_type, symbols)
    
    try:
        print("Instantiating BinanceDataDumper with:", init_kwargs)
        bd = BinanceDataDumper(**init_kwargs) if init_kwargs else BinanceDataDumper()
    except TypeError as e:
        # Fallback: try with only path-like parameter if present
        try:
            print("Fallback: instantiate with only path-like param if present.")
            fallback = {}
            for k in ("data_dir", "path_dir_where_to_dump", "path"):
                if k in sig.parameters:
                    fallback[k] = tempdir
                    break
            if fallback:
                bd = BinanceDataDumper(**fallback)
            else:
                bd = BinanceDataDumper()
        except Exception as e2:
            raise RuntimeError(f"Unable to instantiate BinanceDataDumper: {e2}") from e2
    
    return bd


def call_dumper_adaptive(bd, date_start, date_end, symbols):
    """Call the appropriate download method on BinanceDataDumper with adaptive parameter detection."""
    # Convert date strings to date objects (many versions expect datetime.date)
    ds_date = None
    de_date = None
    if date_start:
        ds_date = dt.datetime.strptime(date_start, "%Y-%m-%d").date()
    if date_end:
        de_date = dt.datetime.strptime(date_end, "%Y-%m-%d").date()

    # Candidate method names to try
    candidates = ["dump_data", "dump", "download", "download_data", "download_data_for", "run", "fetch", "download_files"]
    
    for name in candidates:
        if hasattr(bd, name):
            func = getattr(bd, name)
            sig = inspect.signature(func)
            params = sig.parameters
            
            # Build keyword arguments
            kw = {}
            for p in params:
                if p in ("tickers", "symbols", "symbols_list", "tickers_list", "symbolsToDownload", "tickers_to_download"):
                    kw[p] = symbols
                elif p in ("symbol", "ticker"):
                    kw[p] = symbols[0] if isinstance(symbols, (list, tuple)) else symbols
                elif p in ("date_start", "start_date", "start", "from_date", "from_"):
                    kw[p] = ds_date
                elif p in ("date_end", "end_date", "end", "to_date", "to_"):
                    kw[p] = de_date
                elif p in ("asset_class", "asset"):
                    kw[p] = getattr(bd, "asset_class", None) or None
                elif p in ("data_type",):
                    kw[p] = "trades"
            
            # Attempt 1: call with date objects
            try:
                print(f"Calling {name} with kwargs: {kw}")
                return func(**{k: v for k, v in kw.items() if v is not None})
            except TypeError:
                # Attempt 2: try with string dates (some versions expect str)
                try:
                    kw2 = {}
                    for k, v in kw.items():
                        if isinstance(v, dt.date):
                            kw2[k] = v.isoformat()
                        else:
                            kw2[k] = v
                    print(f"Calling {name} with string dates: {kw2}")
                    return func(**{k: v for k, v in kw2.items() if v is not None})
                except Exception:
                    # Attempt 3: try positional call with common order (symbols, date_start, date_end)
                    try:
                        pos = []
                        if any(p in params for p in ("symbols", "tickers", "symbol")):
                            pos.append(symbols)
                        if any(p in params for p in ("date_start", "start_date")):
                            pos.append(ds_date)
                        if any(p in params for p in ("date_end", "end_date")):
                            pos.append(de_date)
                        if pos:
                            print(f"Trying positional call {name} with args: {pos}")
                            return func(*pos)
                    except Exception:
                        pass
            except Exception as e:
                # Other error - bubble up
                raise
    
    raise RuntimeError("Could not find a suitable download/dump method on your BinanceDataDumper instance.")


def main():
    parser = argparse.ArgumentParser(description="Download Binance trade data using binance_historical_data package")
    parser.add_argument("--symbol", required=True, help="Symbol to download, e.g. BTCUSDT")
    parser.add_argument("--asset_class", choices=["spot", "um", "cm"], default="um", 
                       help="Asset class: spot | um (USDT-M futures) | cm (COIN-M futures)")
    parser.add_argument("--date_start", required=True, help="Start date in YYYY-MM-DD format (inclusive)")
    parser.add_argument("--date_end", required=True, help="End date in YYYY-MM-DD format (inclusive)")
    parser.add_argument("--tempdir", default="temp_binance", 
                       help="Directory where binance_historical_data will store downloaded files")
    
    args = parser.parse_args()

    # Validate dates
    try:
        start_date = dt.datetime.strptime(args.date_start, "%Y-%m-%d")
        end_date = dt.datetime.strptime(args.date_end, "%Y-%m-%d")
        if start_date > end_date:
            raise ValueError("Start date must be before or equal to end date")
    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")

    # Create temp directory if it doesn't exist
    os.makedirs(args.tempdir, exist_ok=True)
    
    print(f"Downloading {args.symbol} trades from {args.asset_class} market")
    print(f"Date range: {args.date_start} to {args.date_end}")
    print(f"Output directory: {args.tempdir}")
    
    # Initialize and run downloader
    bd = init_dumper_adaptive(args.tempdir, args.asset_class, "trades", [args.symbol])
    
    try:
        call_dumper_adaptive(bd, args.date_start, args.date_end, [args.symbol])
        print("✅ Download completed successfully!")
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise


if __name__ == "__main__":
    main()
