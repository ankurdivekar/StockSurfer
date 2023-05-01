# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_technicals.ipynb.

# %% auto 0
__all__ = ['base_path', 'raw_data_dir', 'processed_data_dir', 'load_multiple_bhavcopy', 'get_raw_bhavcopy_data', 'preprocess',
           'get_sma', 'get_bollinger_bands', 'get_donchian', 'get_supertrend', 'add_candle_stats', 'add_all_technicals',
           'process_and_save_symbol_data', 'update_symbols', 'rebuild_all_symbols_data', 'update_all_symbols_data']

# %% ../nbs/02_technicals.ipynb 3
import pandas as pd
import os
import numpy as np
from pathlib import Path
import pandas_ta as pdta
import nbdev
import shutil
import datetime

from .scrapers import fetch_bhavcopy_data_for_range

# %% ../nbs/02_technicals.ipynb 4
base_path = nbdev.config.get_config().lib_path
raw_data_dir = base_path / "../Data/Bhavcopy/Raw"
processed_data_dir = base_path / "../Data/Bhavcopy/Processed"

# %% ../nbs/02_technicals.ipynb 7
def load_multiple_bhavcopy(files_to_load):
    
    bhavcopy_dtypes = {
        "SYMBOL": "string",
        "SERIES": "string",
        "OPEN": "float64",
        "HIGH": "float64",
        "LOW": "float64",
        "CLOSE": "float64",
        "TOTTRDQTY": "int64",
        "TOTTRDVAL": "float64",
        "TIMESTAMP": "string",
        "TOTALTRADES": "int64",
        # "ISIN": 'string',
        # "Unnamed: 13": 'string',
    }

    bhavcopy_usecols = [
        "SYMBOL",
        "SERIES",
        "OPEN",
        "HIGH",
        "LOW",
        "CLOSE",
        "TOTTRDQTY",
        "TOTTRDVAL",
        "TIMESTAMP",
        "TOTALTRADES",
    ]
    
    return pd.concat(
            [
                pd.read_csv(
                    f,
                    dtype=bhavcopy_dtypes,
                    usecols=bhavcopy_usecols,
                    parse_dates=["TIMESTAMP"],
                    dayfirst=False,
                )
                for f in files_to_load
            ],
            ignore_index=True,
    )

# %% ../nbs/02_technicals.ipynb 9
def get_raw_bhavcopy_data(start_date: datetime=None, end_date:datetime.datetime=None) -> pd.DataFrame:
    
    if start_date:
        end_date = end_date or datetime.datetime.today()
        # Get list of date from bhavcopy_date till today
        date_list = pd.date_range(start_date, end_date).tolist()
        
        files_to_load = []
        for d in date_list:
            # Get Year, Month, Day
            year = d.year
            month = d.strftime("%B").upper()[:3]
            day = d.date().strftime("%d")
            file_name = f"cm{day:0>2}{month}{year}bhav.csv"
            file_path = raw_data_dir / file_name
            if file_path.exists():
                files_to_load.append(file_path)
        return load_multiple_bhavcopy(files_to_load)
    
    else:
        csv_files = [x for x in raw_data_dir.iterdir() if x.suffix == ".csv"]

        # Read all the csv files and concatenate them into one dataframe
        # TODO filter out by end_date
        return load_multiple_bhavcopy(csv_files)

# %% ../nbs/02_technicals.ipynb 11
def preprocess(df):
    return (
        df.pipe(lambda x: x[x["SERIES"] == "EQ"])
        .assign(
            DATE=pd.to_datetime(df.TIMESTAMP, format="%d-%b-%Y").dt.date,
            # DAY_OF_WEEK=pd.to_datetime(df.TIMESTAMP, format="%d-%b-%Y").dt.day_name(),
            # WEEK_NUM=pd.to_datetime(df.TIMESTAMP, format="%d-%b-%Y").dt.isocalendar().week,
        )
        .drop(
            columns=[
                "TIMESTAMP",
            ]
        )
        .sort_values(["SYMBOL", "DATE"])
        .reset_index(drop=True)
        # .set_index("DATE")
    )

# %% ../nbs/02_technicals.ipynb 14
# Generate simple moving average data
def get_sma(df_symbol, period=20, metric="CLOSE"):
    metric_col = f"SMA_{period}_{metric.upper()[0]}"
    
    if metric.upper() not in ["CLOSE", "OPEN", "HIGH", "LOW"]:
        raise ValueError(f"Invalid metric: {metric}. Valid metrics are: CLOSE, OPEN, HIGH, LOW")
    elif len(df_symbol) < period + 1:
        df_symbol[metric_col] = np.nan
        return df_symbol
    else:
        return pd.concat(
            [
                df_symbol,
                pdta.sma(df_symbol[metric], length=period).rename(
                    f"SMA_{period}_{metric.upper()[0]}"
                ),
            ],
            axis=1,
        )

# %% ../nbs/02_technicals.ipynb 16
# Generate bollinger bands data
def get_bollinger_bands(df_symbol, period=20, std=2):
    if len(df_symbol) >= period:
        return pd.concat(
            [
                df_symbol,
                pdta.bbands(df_symbol.CLOSE, length=period, std=std).rename(
                    columns={
                        f"BBU_{period}_{std:.1f}": f"BBU_{period}_{std}",
                        f"BBM_{period}_{std:.1f}": f"BBM_{period}_{std}",
                        f"BBL_{period}_{std:.1f}": f"BBL_{period}_{std}",
                        f"BBB_{period}_{std:.1f}": f"BBB_{period}_{std}",
                        f"BBP_{period}_{std:.1f}": f"BBP_{period}_{std}",
                    }
                ),
            ],
            axis=1,
        )
    df_symbol[f"BBU_{period}_{std}"] = np.nan
    df_symbol[f"BBM_{period}_{std}"] = np.nan
    df_symbol[f"BBL_{period}_{std}"] = np.nan
    df_symbol[f"BBB_{period}_{std}"] = np.nan
    df_symbol[f"BBP_{period}_{std}"] = np.nan
    return df_symbol

# %% ../nbs/02_technicals.ipynb 18
# Generate donchian channel data
def get_donchian(df_symbol, upper=22, lower=66):
    return pd.concat(
        [
            df_symbol,
            pdta.donchian(
                df_symbol.HIGH, df_symbol.LOW, lower_length=66, upper_length=22
            )
            # .rename(
            #     columns={
            #         f"DCL_{lower}_{upper}": f"DONCHIAN_L{lower}",
            #         f"DCU_{lower}_{upper}": f"DONCHIAN_U{upper}"})
            .drop(columns=[f"DCM_{lower}_{upper}"]),
        ],
        axis=1,
    )

# %% ../nbs/02_technicals.ipynb 20
# Generate supertrend data
def get_supertrend(df_symbol, period=12, multiplier=3):
    return pd.concat(
        [
            df_symbol,
            pdta.supertrend(
                df_symbol.HIGH,
                df_symbol.LOW,
                df_symbol.CLOSE,
                length=period,
                multiplier=multiplier,
            )
            .drop(
                columns=[
                    f"SUPERT_{period}_{multiplier:.1f}",
                    f"SUPERTl_{period}_{multiplier:.1f}",
                    f"SUPERTs_{period}_{multiplier:.1f}",
                ]
            )
            .rename(
                columns={
                    f"SUPERTd_{period}_{multiplier:.1f}": f"ST_{period}_{multiplier}"
                }
            ),
        ],
        axis=1,
    )

# %% ../nbs/02_technicals.ipynb 22
def add_candle_stats(df_symbol):
    return df_symbol.assign(
        CDL_COLOR=df_symbol.apply(
            lambda x: "green" if x.CLOSE > x.OPEN else "red", axis=1
        ).astype("string"),
        CDL_SIZE=abs(df_symbol.CLOSE - df_symbol.OPEN),
        TOPWICK_SIZE=df_symbol.HIGH - df_symbol[["OPEN", "CLOSE"]].max(axis=1),
        BOTWICK_SIZE=df_symbol[["OPEN", "CLOSE"]].min(axis=1) - df_symbol.LOW,
    )

# %% ../nbs/02_technicals.ipynb 24
# Generate all technicals for a symbol data
def add_all_technicals(df_symbol):
    return (
        df_symbol.sort_values(["SYMBOL", "DATE"])
        .reset_index(drop=True)
        # Add SMA
        .pipe(get_sma, period=20, metric="CLOSE")
        .pipe(get_sma, period=20, metric="HIGH")
        .pipe(get_sma, period=44, metric="CLOSE")
        .pipe(get_sma, period=200, metric="CLOSE")
        # Add Bollinger bands
        .pipe(get_bollinger_bands)
        # Add Donchian channel
        # .pipe(get_donchian)
        # Add supertrend data
        # .pipe(get_supertrend, period=12, multiplier=3)
        # .pipe(get_supertrend, period=11, multiplier=2)
        # .pipe(get_supertrend, period=10, multiplier=1)
        # Add candle properties data
        # .pipe(add_candle_stats)
    )

# %% ../nbs/02_technicals.ipynb 26
def process_and_save_symbol_data(df):
    df = add_all_technicals(df)
    file_path = processed_data_dir / f"{df.SYMBOL.iloc[-1]}.parquet"
    df.to_parquet(file_path, index=False)
    print(f"Saved {file_path.name}")

# %% ../nbs/02_technicals.ipynb 27
def update_symbols(df):
    symbol_replacements = [
        ("CADILAHC", "ZYDUSLIFE"),
        ("MINDAIND", "UNOMINDA"),
    ]

    for old, new in symbol_replacements:
        df.SYMBOL = df.SYMBOL.replace({old: new})
        
    return df

# %% ../nbs/02_technicals.ipynb 28
def rebuild_all_symbols_data():
    df = get_raw_bhavcopy_data()
    df = preprocess(df)
    df = update_symbols(df)
    
    # Recursively delete all files and directories inside the processed data directory
    _ = [
        shutil.rmtree(f) if f.is_dir() else f.unlink()
        for f in processed_data_dir.iterdir()
    ]

    for symbol, df_symbol in df.groupby("SYMBOL"):
        # if len(df_symbol) > 200:
        process_and_save_symbol_data(df_symbol)
            

# %% ../nbs/02_technicals.ipynb 29
def update_all_symbols_data():
    # Define date range
    start_date = (
        pd.read_parquet(processed_data_dir / "INFY.parquet")
        .sort_values(["DATE"])
        .reset_index(drop=True)
        .DATE.iloc[-2]
    )
    end_date = datetime.datetime.now().date()#-datetime.timedelta(days=15)
    print(start_date, end_date)

    # Fetch latest data from NSE
    fetch_bhavcopy_data_for_range(start_date, end_date)

    df = preprocess(get_raw_bhavcopy_data(start_date=start_date))
    new_rows_per_symbol = df.shape[0]/df.SYMBOL.nunique()
    
    if new_rows_per_symbol < 3:
        print("No new data to update")
    else:
        for symbol, df_symbol in df.groupby("SYMBOL"):
            pq = processed_data_dir / f"{symbol}.parquet"
            if pq.exists():
                # Load earlier data
                old_df = pd.read_parquet(pq)
                old_df = old_df.drop(
                    columns=[
                        x
                        for x in old_df.columns
                        if x
                        not in [
                            "SYMBOL",
                            "SERIES",
                            "OPEN",
                            "HIGH",
                            "LOW",
                            "CLOSE",
                            "TOTTRDQTY",
                            "TOTTRDVAL",
                            "TOTALTRADES",
                            "DATE",
                        ]
                    ]
                )
                
                new_df = (
                    pd.concat([old_df, df_symbol])
                    .sort_values(["DATE"])
                    .drop_duplicates(subset=["DATE"], keep="first")
                    .reset_index(drop=True)
                )
                #TODO: new_df has duplicates
                # print(old_df.shape)
                # print(df_symbol.shape)
                process_and_save_symbol_data(new_df)
