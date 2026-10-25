import datetime
import io
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="IMF Real Exchange Rate (RER) Visualizer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🌐 IMF Real Exchange Rate (RER) Visualizer")
st.markdown(
    """
This app calculates and visualizes the **Real Exchange Rate (RER)** and **Nominal Spot Rate $S(t)$**
between IMF member countries and the Euro Area using official IMF SDMX 3.0 API endpoints.
"""
)

# ---------------------------------------------------------
# Country Dictionary (IMF ISO3 & G163 for Euro Area)
# ---------------------------------------------------------
COUNTRY_OPTIONS = {
    "Euro Area (19/20 countries)": "G163",
    "United States": "USA",
    "United Kingdom": "GBR",
    "Japan": "JPN",
    "Canada": "CAN",
    "Brazil": "BRA",
    "Switzerland": "CHE",
    "China": "CHN",
    "Australia": "AUS",
    "India": "IND",
    "Mexico": "MEX",
    "South Africa": "ZAF",
    "South Korea": "KOR",
    "Norway": "NOR",
    "Sweden": "SWE",
    "New Zealand": "NZL",
    "Singapore": "SGP",
    "Chile": "CHL",
    "Colombia": "COL",
}

# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
st.sidebar.header("1. Currency / Country Selection")
country_names = list(COUNTRY_OPTIONS.keys())

c1_name = st.sidebar.selectbox("Country 1 (Base Currency)", country_names, index=0)
c2_name = st.sidebar.selectbox("Country 2 (Price / Quote Currency)", country_names, index=1)

iso1 = COUNTRY_OPTIONS[c1_name]
iso2 = COUNTRY_OPTIONS[c2_name]

st.sidebar.markdown(
    f"""
**Direction of $S(t)$:**  
Units of **{c2_name}** currency per **1 unit of {c1_name}** currency.
"""
)

st.sidebar.header("2. Display Options")
chart_mode = st.sidebar.radio(
    "Series to Display:",
    options=["Both (Dual Axes)", "Real Index (Base 100)", "Nominal S(t)"],
    index=0,
)

# ---------------------------------------------------------
# IMF SDMX 3.0 API Fetchers
# ---------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_imf_sdmx_series(dataflow: str, key: str) -> pd.Series:
    """
    Fetches monthly time series from the IMF SDMX 3.0 REST API.
    Attempts CSV response first (fastest and most robust), falling back to SDMX-JSON.
    """
    base_url = f"https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/{dataflow}/~/{key}"
    params = {"c[TIME_PERIOD]": "ge:1976-01"}
    headers_csv = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/csv"
    }
    
    # 1. Try CSV stream
    try:
        resp = requests.get(base_url, headers=headers_csv, params=params, timeout=45)
        if resp.status_code == 200 and len(resp.text.strip()) > 50:
            df_csv = pd.read_csv(io.StringIO(resp.text))
            time_col = next((c for c in df_csv.columns if c.upper() in ["TIME_PERIOD", "TIME"]), None)
            val_col = next((c for c in df_csv.columns if c.upper() in ["OBS_VALUE", "VALUE"]), None)
            
            if time_col and val_col:
                df_clean = df_csv[[time_col, val_col]].dropna()
                df_clean[time_col] = df_clean[time_col].astype(str).str.replace("-M", "-")
                df_clean["Date"] = pd.to_datetime(df_clean[time_col], errors="coerce")
                df_clean = df_clean.dropna(subset=["Date"]).sort_values("Date")
                s = pd.Series(df_clean[val_col].values, index=df_clean["Date"])
                s = pd.to_numeric(s, errors="coerce").dropna()
                return s.resample("MS").last()
    except Exception:
        pass

    # 2. Fallback to SDMX-JSON
    try:
        headers_json = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/vnd.sdmx.data+json;version=2.0.0, application/json"
        }
        resp = requests.get(base_url, headers=headers_json, params=params, timeout=45)
        if resp.status_code == 200:
            data_json = resp.json()
            data_block = data_json.get("data", data_json)
            datasets = data_block.get("dataSets", [{}])[0]
            structure = data_block.get("structure", {})
            
            obs_dims = structure.get("dimensions", {}).get("observation", [])
            time_dim = next((d for d in obs_dims if d.get("id") in ["TIME_PERIOD", "TIME"]), None)
            if not time_dim:
                ser_dims = structure.get("dimensions", {}).get("series", [])
                time_dim = next((d for d in ser_dims if d.get("id") in ["TIME_PERIOD", "TIME"]), None)
            
            time_periods = [v.get("id") for v in time_dim.get("values", [])] if time_dim else []

            obs_dict = datasets.get("observations", {})
            if not obs_dict and "series" in datasets:
                first_series = next(iter(datasets["series"].values()), {})
                obs_dict = first_series.get("observations", {})

            records = {}
            for k, v in obs_dict.items():
                idx = int(k.split(":")[-1])
                val = float(v[0]) if isinstance(v, list) and v[0] is not None else None
                if idx < len(time_periods) and val is not None:
                    records[time_periods[idx]] = val

            if records:
                s = pd.Series(records)
                s.index = pd.to_datetime(s.index.astype(str).str.replace("-M", "-"))
                s = s.sort_index().resample("MS").last()
                return s
    except Exception:
        pass

    return pd.Series(dtype=float)


def get_cpi(iso: str) -> pd.Series:
    """Monthly CPI key: {ISO3}.CPI._T.IX.M. Includes fallbacks for Euro Area."""
    s = fetch_imf_sdmx_series("CPI", f"{iso}.CPI._T.IX.M")
    
    # Fallback mappings if the standard CPI key fails
    if s.empty and iso == "G163":
        s = fetch_imf_sdmx_series("CPI", "U2.CPI._T.IX.M")
        if s.empty:
            s = fetch_imf_sdmx_series("IFS", "M.U2.PCPI_IX")
    return s


def get_fx_vs_usd(iso: str) -> pd.Series:
    """Returns currency units per 1 USD. Includes fallbacks for Euro Area."""
    if iso == "USA":
        idx = pd.date_range("1976-01-01", datetime.date.today(), freq="MS")
        return pd.Series(1.0, index=idx)
        
    s = fetch_imf_sdmx_series("ER", f"{iso}.XDC_USD.PA_RT.M")
    
    if s.empty and iso == "G163":
        s = fetch_imf_sdmx_series("ER", "U2.XDC_USD.PA_RT.M")
        if s.empty:
            s = fetch_imf_sdmx_series("IFS", "M.U2.TXC_USD_PT")
    return s


# ---------------------------------------------------------
# Load Series & Validate
# ---------------------------------------------------------
with st.spinner("Connecting to IMF SDMX 3.0 API..."):
    cpi1 = get_cpi(iso1)
    cpi2 = get_cpi(iso2)
    fx1_usd = get_fx_vs_usd(iso1)
    fx2_usd = get_fx_vs_usd(iso2)

errors = []
if cpi1.empty:
    errors.append(f"CPI data for {c1_name} ({iso1}) could not be retrieved from the IMF API.")
if cpi2.empty:
    errors.append(f"CPI data for {c2_name} ({iso2}) could not be retrieved from the IMF API.")
if fx1_usd.empty:
    errors.append(f"Exchange rate data for {c1_name} ({iso1}) could not be retrieved.")
if fx2_usd.empty:
    errors.append(f"Exchange rate data for {c2_name} ({iso2}) could not be retrieved.")

if errors:
    st.error("### Data Fetch Error / Coverage Limitation")
    for err in errors:
        st.warning(f"- {err}")
    st.info("Tip: Ensure the IMF server is accessible. Try refreshing the app in a few seconds.")
    st.stop()

# ---------------------------------------------------------
# RER Calculations
# ---------------------------------------------------------
df_all = pd.DataFrame({
    "CPI1": cpi1,
    "CPI2": cpi2,
    "FX1_USD": fx1_usd,
    "FX2_USD": fx2_usd,
}).dropna()

if df_all.empty:
    st.warning("No overlapping monthly observations found across all 4 series.")
    st.stop()

df_all["S_t"] = df_all["FX2_USD"] / df_all["FX1_USD"]
df_all["RER_t"] = df_all["S_t"] * df_all["CPI1"] / df_all["CPI2"]

# ---------------------------------------------------------
# Dynamic Date Filter & Benchmark Calculation
# ---------------------------------------------------------
min_date = df_all.index.min().date()
max_date = df_all.index.max().date()

st.sidebar.header("3. Benchmark & Sample Window")
date_range = st.sidebar.date_input(
    "Sample Observation Period:",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = min_date, max_date

mask = (df_all.index.date >= start_d) & (df_all.index.date <= end_d)
df = df_all.loc[mask].copy()

if df.empty:
    st.error("No valid observations exist within the chosen dates.")
    st.stop()

rer_star = df["RER_t"].mean()
df["Real_Index_t"] = 100.0 * df["RER_t"] / rer_star

# ---------------------------------------------------------
# Metrics Banner
# ---------------------------------------------------------
latest_dt = df.index[-1].strftime("%B %Y")
latest_real_idx = df["Real_Index_t"].iloc[-1]
latest_s = df["S_t"].iloc[-1]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Observations in Range", f"{len(df)} months")
c2.metric("Benchmark RER* (Average)", f"{rer_star:.4f}")
c3.metric(f"Nominal S(t) ({latest_dt})", f"{latest_s:.4f}")
c4.metric(
    f"Real Index ({latest_dt})",
    f"{latest_real_idx:.2f}",
    delta=f"{latest_real_idx - 100.0:.2f}% vs Benchmark",
)

if latest_real_idx > 100:
    st.warning(
        f"**Valuation in {latest_dt}:** **{c1_name}** is **overvalued** relative to "
        f"**{c2_name}** by **{latest_real_idx - 100:.2f}%** compared to the sample benchmark average."
    )
else:
    st.success(
        f"**Valuation in {latest_dt}:** **{c1_name}** is **undervalued** relative to "
        f"**{c2_name}** by **{100 - latest_real_idx:.2f}%** compared to the sample benchmark average."
    )

# ---------------------------------------------------------
# Charts
# ---------------------------------------------------------
if chart_mode == "Real Index (Base 100)":
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Real_Index_t"], mode="lines", name="Real Index", line=dict(color="#1f
