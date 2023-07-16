# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_filters.ipynb.

# %% auto 0
__all__ = ['base_path', 'processed_data_dir', 'filter_stocks', 'bollinger_squeeze', 'volume_surge', 'wedge_200_20', 'level_catch',
           'alltime_high', 'single_candle_span', 'hammer_on_BBL', 'green_engulfing_on_BBL',
           'three_rising_green_candles_on_SMA20']

# %% ../nbs/04_filters.ipynb 3
import pandas as pd
from datetime import datetime, timedelta
import nbdev
from stocksurfer.technicals import (
    get_symbol_data,
    add_all_technicals,
    get_monthly_data,
    get_weekly_data,
    get_bollinger_bands,
    get_keltner_channels,
)
from stocksurfer.scrapers import (
    get_nifty500_stocks,
    get_nifty100_stocks,
    get_fno_stocks,
)

# %% ../nbs/04_filters.ipynb 4
base_path = nbdev.config.get_config().lib_path
processed_data_dir = base_path / "../Data/Bhavcopy/Processed"

# %% ../nbs/04_filters.ipynb 6
def filter_stocks(
    symbols=None,
    timeframe="daily",
    cutoff_date=None,
    lookback=0,
    n_detections=0,
    strategy=None,
    strategy_args=None,
):
    match symbols:
        case None:
            symbols = get_nifty500_stocks()
        case "nifty100":
            symbols = get_nifty100_stocks()
        case "nifty500":
            symbols = get_nifty500_stocks()
        case "fno":
            symbols = get_fno_stocks()
        case "all":
            symbols = [f.stem for f in processed_data_dir.glob("*.parquet")]
    

    # if not symbols:
    #     symbols = get_nifty500_stocks()
    # elif symbols == "nifty100":
    #     symbols = get_nifty100_stocks()
    # elif symbols == "fno":
    #     symbols = get_fno_stocks()
    # elif symbols == "all":
    #     symbols = [f.stem for f in processed_data_dir.glob("*.parquet")]
    
    for symbol in symbols:
        # print(symbol)
        df = get_symbol_data(symbol)
        if df is None:
            print(f"Data not found for {symbol}")
        elif len(df) < 202:
            # print(f"Data not sufficient for {symbol}: {len(df)} rows")
            pass
        else:
            # Filter data by cutoff data
            if cutoff_date:
                df = df.query("DATE < @cutoff_date")
            
            # Resample data to monthly or weekly
            if timeframe.lower() == "monthly":
                df = add_all_technicals(get_monthly_data(df))
            elif timeframe.lower() == "weekly":
                df = add_all_technicals(get_weekly_data(df))

            # Iteratively evaluate strategy for lookback period
            detection_count = 0
            for lb in range(min(lookback+1, len(df)-1)):
                df_lb = df.drop(df.tail(lb).index)

                # Pass strategy args to the strategy method and run it
                if strategy(df_lb, kwargs=strategy_args):
                    detection_count += 1
                    if detection_count == n_detections:
                        break

# %% ../nbs/04_filters.ipynb 11
def bollinger_squeeze(df, kwargs=None):
    # Get args
    window = kwargs["window"] if kwargs and "window" in kwargs.keys() else 10

    if "KC_U" not in df.columns:
        df = get_keltner_channels(df)
    if "BB_U" not in df.columns:
        df = get_bollinger_bands(df)

    conditions = [
        all(df.iloc[-window - 1 : -1].KC_U > df.iloc[-window - 1 : -1].BB_U),
        all(df.iloc[-window - 1 : -1].KC_L < df.iloc[-window - 1 : -1].BB_L),
        any(
            [
                df.iloc[-1].KC_U < df.iloc[-1].BB_U,
                df.iloc[-1].KC_L > df.iloc[-1].BB_L,
            ]
        ),
    ]

    if all(conditions):
        print(
            f"{df.iloc[-1].SYMBOL} has a bollinger squeeze breakout on {df.DATE.iloc[-1].date()} @ {df.iloc[-1].CLOSE}"
        )
        return True
    return False

# %% ../nbs/04_filters.ipynb 13
def volume_surge(df, kwargs=None):
    # Get args
    window = kwargs["window"] if kwargs and "window" in kwargs.keys() else 12
    surge_factor = (
        kwargs["surge_factor"] if kwargs and "surge_factor" in kwargs.keys() else 3
    )

    # vol_mean = df.iloc[-window-1:-1].TOTTRDQTY.mean()
    vol_max = df.iloc[-window - 1 : -1].TOTTRDQTY.max()

    conditions = [
        vol_max * surge_factor < df.iloc[-1].TOTTRDQTY,
        # df.iloc[-1].CLOSE > df.iloc[-1].OPEN,
    ]

    if all(conditions):
        print(
            f"{df.iloc[-1].SYMBOL} has a volume surge on {df.DATE.iloc[-1].date()} @ {df.iloc[-1].CLOSE} -> {df.iloc[-1].TOTTRDQTY}"
        )
        return True
    return False

# %% ../nbs/04_filters.ipynb 15
# Check for a 200-20 wedge position
def wedge_200_20(df, kwargs=None):
    
    # Get args
    window = kwargs['window'] if kwargs and 'window' in kwargs.keys() else 12
    
    # Get df tail
    df_tail = df.tail(window)
    
    # Get 200-20 diff
    tail_diff = df_tail.apply(lambda x: x.SMA_200_C - x.SMA_20_C, axis=1)
    
    conditions = [
        
        # SMA 20 is rising
        df_tail.SMA_20_C.is_monotonic_increasing,
        
        # SMA 20 is roughly rising, calculated as 75% of candles are closing higher than previous candle
        # ((df_tail.SMA_20_C.diff() > 0).sum()+1)/(len(df_tail)) > 0.75,
        
        # SMA 200 and SMA 20 are converging
        tail_diff.is_monotonic_decreasing,

        # SMA 200 is above SMA 20
        all(tail_diff > 0),

        # SMA 200 and SMA 20 are within x% of each other
        all(tail_diff < df_tail.SMA_200_C * 0.2),
        
        # Any of these positions
        any([
            # Last candle has crossed SMA 200 with green candle
            df.iloc[-1].CLOSE > df.iloc[-1].SMA_200_C > df.iloc[-1].LOW,
            # Last candle is cleanly above SMA 200 and the one before spanned SMA 200 but closed below it
            df.iloc[-1].LOW > df.iloc[-1].SMA_200_C and df.iloc[-2].HIGH > df.iloc[-2].SMA_200_C > df.iloc[-2].LOW,
            # Last candle is cleanly above SMA 200 and the one before is cleanly below SMA 200
            df.iloc[-1].LOW > df.iloc[-1].SMA_200_C and df.iloc[-2].HIGH < df.iloc[-2].SMA_200_C,
        ]),
    
        
        # Candle before last has closed below SMA 200
        # df.iloc[-2].CLOSE < df.iloc[-2].SMA_200_C,
        
        # Body of last candle should be bigger than upper and lower wick
        df.iloc[-1].CLOSE - df.iloc[-1].OPEN > df.iloc[-1].HIGH - df.iloc[-1].CLOSE,
        df.iloc[-1].CLOSE - df.iloc[-1].OPEN > df.iloc[-1].OPEN - df.iloc[-1].LOW,
        
        # SMA 20 crosses over SMA 200 from below
        # df.iloc[-1].SMA_20_C > df.iloc[-1].SMA_200_C,
        # df.iloc[-2].SMA_20_C < df.iloc[-2].SMA_200_C,

        # df.iloc[-2].CLOSE < df.iloc[-2].SMA_200_C,
        # df.iloc[-3].CLOSE < df.iloc[-3].SMA_200_C,

    ]

    if all(conditions):
        print(f"{df.iloc[-1].SYMBOL} is in a 200-20 wedge position on {df.DATE.iloc[-1].date()} @ {df.iloc[-1].CLOSE}")
        return True
    return False

# %% ../nbs/04_filters.ipynb 17
# Check for SMA 20 catch
def level_catch(df, kwargs=None):
    if kwargs and "level" in kwargs.keys():
        conditions = [
            # df.iloc[-1].CLOSE > df.iloc[-1].OPEN,
            df.iloc[-2].CLOSE > df.iloc[-2].OPEN,
            df.iloc[-2].LOW < df.iloc[-2][kwargs['level']],
            min(df.iloc[-1].OPEN, df.iloc[-1].CLOSE) > df.iloc[-1][kwargs['level']],
            df.iloc[-1].CLOSE > df.iloc[-2].CLOSE,
        ]

        if all(conditions):
            print(f"{df.SYMBOL.iloc[0]} -> {kwargs['level']} catch on {df.DATE.iloc[-1].date()} at {df.iloc[-1].CLOSE}")
            return True
    else:
        print("Level not specified")
    return False

# %% ../nbs/04_filters.ipynb 20
# Check for alltime high
def alltime_high(df, kwargs=None):
    df2 = df[:-1]
    conditions = [
        df.iloc[-1].CLOSE >= df2.HIGH.max(),
        df.iloc[-2].CLOSE < df2.HIGH.max(),
        
        df.iloc[-3].CLOSE < df2.HIGH.max(),
        df.iloc[-4].CLOSE < df2.HIGH.max(),
        df.iloc[-5].CLOSE < df2.HIGH.max(),
    ]
    
    if all(conditions):
        print(f"{df.SYMBOL.iloc[0]} -> All time high on {df.DATE.iloc[-1].date()}")
        return True
    return False

# %% ../nbs/04_filters.ipynb 22
# Check if the latest candle spans the given SMAs
def single_candle_span(df, kwargs=None):
    if kwargs and "col_list" in kwargs.keys():
        col_list = kwargs["col_list"]
    else:
        col_list = ["SMA_20_C", "SMA_200_C"]

    conditions = [
        df.LOW.iloc[-1] <= df[col].iloc[-1] <= df.HIGH.iloc[-1] for col in col_list
    ]
    if all(conditions):
        print(f"{df.SYMBOL.iloc[0]} -> Single candle span on {df.DATE.iloc[-1].date()}")
        return True
    return False

# %% ../nbs/04_filters.ipynb 25
# Check if the latest candle is a hammer
def hammer_on_BBL(df, kwargs=None):
    body = df.iloc[-1].CLOSE - df.iloc[-1].OPEN
    upper_wick = df.iloc[-1].HIGH - df.iloc[-1].CLOSE
    lower_wick = df.iloc[-1].OPEN - df.iloc[-1].LOW

    conditions = [
        df.iloc[-1].CLOSE > df.iloc[-1].OPEN,
        lower_wick >= 2 * body,
        body >= 1.5 * upper_wick,
        df.iloc[-1].CLOSE > df.iloc[-1].BBL_20_2 > df.iloc[-1].LOW,
    ]

    if all(conditions):
        print(f"{df.SYMBOL.iloc[0]} -> Hammer on BBL on {df.DATE.iloc[-1].date()}")
        return True
    return False

# %% ../nbs/04_filters.ipynb 28
# Check if latest candle is green takes out red on BBL
def green_engulfing_on_BBL(df, kwargs=None):
    conditions = [
        df.iloc[-2].CLOSE < df.iloc[-2].OPEN,
        df.iloc[-1].CLOSE > df.iloc[-1].OPEN,
        df.iloc[-1].LOW < df.iloc[-1].BBL_20_2 < df.iloc[-1].HIGH,
        df.iloc[-1].CLOSE > df.iloc[-2].OPEN,
    ]

    if all(conditions):
        print(
            f"{df.SYMBOL.iloc[0]} -> Green engulfing on BBL on {df.DATE.iloc[-1].date()}"
        )
        return True
    return False

# %% ../nbs/04_filters.ipynb 31
# Check for three rising green candles
def three_rising_green_candles_on_SMA20(df, kwargs=None):
    conditions = [
        df.iloc[-1].CLOSE > df.iloc[-1].OPEN,
        df.iloc[-2].CLOSE > df.iloc[-2].OPEN,
        df.iloc[-3].CLOSE > df.iloc[-3].OPEN,
        df.iloc[-1].CLOSE > df.iloc[-2].CLOSE,
        df.iloc[-2].CLOSE > df.iloc[-3].CLOSE,
        df.iloc[-3].CLOSE > df.iloc[-3].SMA_20_C,
        df.iloc[-3].LOW < df.iloc[-3].SMA_20_C,
    ]

    if all(conditions):
        print(
            f"{df.SYMBOL.iloc[0]} -> Three rising green candles on {df.DATE.iloc[-1].date()}"
        )
        return True
    return False
