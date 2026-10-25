import datetime
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
between any two IMF-monitored countries or currency areas using official SDMX 3.0 API endpoints.
"""
)

# ---------------------------------------------------------
# IMF ISO-3 Country Directory (including Euro Area G163)
# ---------------------------------------------------------
COUNTRY_OPTIONS = {
    "United States": "USA",
    "Euro Area (19/20 countries)": "G163",
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
    "Argentina": "ARG",
    "Turkey": "TUR",
    "Poland": "POL",
    "Indonesia": "IDN",
}

# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
st.sidebar.header("1. Currency / Country Selection")

country_names = list(COUNTRY_OPTIONS.keys())
c1_default_idx = country_names.index("Euro Area (19/20 countries)")
c2_default_idx = country_names.index("United States")

c1_name = st.sidebar.selectbox("Country 1 (Base Currency)", country_names, index=c1_default_idx)
c2_name = st.sidebar.selectbox("Country 2 (Price / Quote Currency)", country_names, index=c2_default_idx)

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
    options=["Real Index (Base 100)", "Nominal S(t)", "Both (Dual Axes)"],
    index=2,
)

# ---------------------------------------------------------
# Data Ingestion & Transformation Functions
# ---------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_imf_series(series_key: str) -> pd.Series:
    """
    Fetches a monthly timeseries from the IMF SDMX 3.0 API.
    URL Pattern: https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF/{series_key}
    Fallback to SDMX REST structure if needed.
    """
    # IMF SDMX 3.0 data endpoint pattern
    url = f"https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF/{series_key}?startPeriod=1976-01"
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            # Fallback query format in case endpoint expects compact or direct sdmx-json
            url_alt = f"https://api.imf.org/external/sdmx/3.0/data/{series_key}?startPeriod=1976-01"
            response = requests.get(url_alt, headers=headers, timeout=20)
            if response.status_code != 200:
                return pd.Series(dtype=float)

        payload = response.json()
        
        # Parse standard SDMX-JSON structures
        data_block = payload.get("data", payload.get("Data", {}))
        data_sets = data_block.get("dataSets", [{}])[0]
        structures = data_block.get("structure", {})
        
        # Extract time dimension periods
        dims = structures.get("dimensions", {}).get("observation", [])
        time_dim = next((d for d in dims if d.get("id") in ["TIME_PERIOD", "TIME"]), None)
        
        if not time_dim:
            # Try finding dimensions in series
            series_dims = structures.get("dimensions", {}).get("series", [])
            time_dim = next((d for d in series_dims if d.get("id") in ["TIME_PERIOD", "TIME"]), None)

        time_values = [v.get("id", v.get("name")) for v in time_dim.get("values", [])] if time_dim else []

        observations = data_sets.get("observations", {})
        if not observations and "series" in data_sets:
            # Series level nesting
            series_data = data_sets.get("series", {})
            first_key = next(iter(series_data), None)
            if first_key:
                observations = series_data[first_key].get("observations", {})

        records = {}
        for key, obs in observations.items():
            # In SDMX-JSON, keys can be index positions like "0:12" or single index "12"
            idx = int(key.split(":")[-1])
            val = float(obs[0]) if isinstance(obs, list) and obs[0] is not None else None
            if idx < len(time_values) and val is not None:
                records[time_values[idx]] = val

        if not records:
            return pd.Series(dtype=float)

        s = pd.Series(records)
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        # Ensure monthly resample / monthly period start
        s = s.resample("MS").last()
        return s
    except Exception:
        return pd.Series(dtype=float)


def get_country_exchange_rate_vs_usd(iso_code: str) -> pd.Series:
    """
    Retrieves or constructs the currency units per 1 USD ($XDC/USD).
    If Country is USA, rate is 1.0.
    """
    if iso_code == "USA":
        idx = pd.date_range("1976-01-01", datetime.date.today(), freq="MS")
        return pd.Series(1.0, index=idx)

    series_key = f"{iso_code}.XDC_USD.PA_RT.M"
    return fetch_imf_series(series_key)


def get_country_cpi(iso_code: str) -> pd.Series:
    """
    Retrieves monthly CPI index.
    Key: {ISO3}.CPI._T.IX.M
    """
    series_key = f"{iso_code}.CPI._T.IX.M"
    return fetch_imf_series(series_key)


# ---------------------------------------------------------
# Load Data
# ---------------------------------------------------------
with st.spinner("Retrieving monthly series from IMF SDMX API..."):
    # Exchange rates vs USD: e1 = C1/USD, e2 = C2/USD
    e1_usd = get_country_exchange_rate_vs_usd(iso1)
    e2_usd = get_country_exchange_rate_vs_usd(iso2)

    # Consumer Price Indices
    cpi1 = get_country_cpi(iso1)
    cpi2 = get_country_cpi(iso2)

# Verify minimum requirements
has_missing = False
missing_reasons = []

if cpi1.empty:
    missing_reasons.append(f"CPI data for {c1_name} ({iso1}) not found or API is unavailable.")
if cpi2.empty:
    missing_reasons.append(f"CPI data for {c2_name} ({iso2}) not found or API is unavailable.")
if e1_usd.empty:
    missing_reasons.append(f"Exchange rate data for {c1_name} ({iso1}) not found.")
if e2_usd.empty:
    missing_reasons.append(f"Exchange rate data for {c2_name} ({iso2}) not found.")

if missing_reasons:
    st.error("### Data Fetch Error / Coverage Limitation")
    for msg in missing_reasons:
        st.warning(f"- {msg}")
    st.info(
        "Note: Some developing nations or legacy records may have limited coverage in IMF's monthly CPI/FX feeds. "
        "Try selecting broader currencies such as USA, G163 (Euro Area), GBR, JPN, or CAN."
    )
    st.stop()

# ---------------------------------------------------------
# Calculations & Alignments
# ---------------------------------------------------------
# Construct DataFrame
df_all = pd.DataFrame({
    "e1_usd": e1_usd,
    "e2_usd": e2_usd,
    "P1": cpi1,
    "P2": cpi2,
}).dropna()

if df_all.empty:
    st.warning("No overlapping monthly dates found where all 4 series have valid data.")
    st.stop()

# Nominal exchange rate S(t) = units of Country 2 currency per 1 unit of Country 1
# e1_usd = C1 / USD  =>  1 C1 = (1 / e1_usd) USD
# e2_usd = C2 / USD  =>  1 USD = e2_usd C2
# S(t) = e2_usd / e1_usd
df_all["S_t"] = df_all["e2_usd"] / df_all["e1_usd"]

# RER(t) = S(t) * P1(t) / P2(t)
df_all["RER_t"] = df_all["S_t"] * df_all["P1"] / df_all["P2"]

# Drop any infinite/nan entries
df_all = df_all.replace([float("inf"), float("-inf")], pd.NA).dropna()

# ---------------------------------------------------------
# Dynamic Date Range Filter
# ---------------------------------------------------------
min_date = df_all.index.min().date()
max_date = df_all.index.max().date()

st.sidebar.header("3. Benchmark & Sample Window")
date_range = st.sidebar.date_input(
    "Observation Sample Period:",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = min_date, max_date

# Filter sample
mask = (df_all.index.date >= start_d) & (df_all.index.date <= end_d)
df = df_all.loc[mask].copy()

if df.empty:
    st.error("No valid monthly data available for the chosen date range.")
    st.stop()

# Recalculate RER* over selected window
rer_benchmark = df["RER_t"].mean()
df["Real_Index_t"] = 100.0 * df["RER_t"] / rer_benchmark

# ---------------------------------------------------------
# Display Key Metrics
# ---------------------------------------------------------
latest_row = df.iloc[-1]
latest_date_str = df.index[-1].strftime("%B %Y")
latest_real_idx = latest_row["Real_Index_t"]
latest_nominal = latest_row["S_t"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Selected Observations", f"{len(df)} months")
col2.metric(f"Benchmark RER* ({start_d.strftime('%Y')} - {end_d.strftime('%Y')})", f"{rer_benchmark:.4f}")
col3.metric(f"Latest Nominal S(t) ({latest_date_str})", f"{latest_nominal:.4f}")
col4.metric(
    f"Latest Real Index ({latest_date_str})",
    f"{latest_real_idx:.2f}",
    delta=f"{latest_real_idx - 100.0:.2f}% vs Mean",
)

# Valuation Callout
if latest_real_idx > 100:
    st.warning(
        f"**Valuation Status ({latest_date_str}):** Country 1 (**{c1_name}**) is **overvalued** "
        f"relative to Country 2 (**{c2_name}**) by approx. **{latest_real_idx - 100:.2f}%** "
        f"against the sample benchmark."
    )
else:
    st.success(
        f"**Valuation Status ({latest_date_str}):** Country 1 (**{c1_name}**) is **undervalued** "
        f"relative to Country 2 (**{c2_name}**) by approx. **{100 - latest_real_idx:.2f}%** "
        f"against the sample benchmark."
    )

# ---------------------------------------------------------
# Plotting with Plotly
# ---------------------------------------------------------
if chart_mode == "Real Index (Base 100)":
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Real_Index_t"],
            mode="lines",
            name="Real Exchange Rate Index (Mean = 100)",
            line=dict(color="#1f77b4", width=2.5),
        )
    )
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="red",
        annotation_text="Benchmark (RER* = 100)",
        annotation_position="top left",
    )
    fig.update_layout(
        title=f"Real Exchange Rate Index: {c1_name} vs. {c2_name} (Base 100 = Sample Average)",
        xaxis_title="Date",
        yaxis_title="Real Index (100 = Average RER)",
        hovermode="x unified",
        template="plotly_white",
        height=550,
    )

elif chart_mode == "Nominal S(t)":
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["S_t"],
            mode="lines",
            name=f"Nominal S(t) ({c2_name} per 1 {c1_name})",
            line=dict(color="#2ca02c", width=2.5),
        )
    )
    fig.update_layout(
        title=f"Nominal Spot Exchange Rate: {c2_name} per 1 {c1_name} (Unnormalized)",
        xaxis_title="Date",
        yaxis_title=f"{c2_name} currency units",
        hovermode="x unified",
        template="plotly_white",
        height=550,
    )

else:  # Both (Dual Axes)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Real_Index_t"],
            name="Real Index (Base 100)",
            line=dict(color="#1f77b4", width=2.5),
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["S_t"],
            name=f"Nominal S(t) ({c2_name} units)",
            line=dict(color="#2ca02c", width=2, dash="dot"),
        ),
        secondary_y=True,
    )

    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="rgba(255, 0, 0, 0.6)",
        secondary_y=False,
        annotation_text="RER* = 100",
        annotation_position="top left",
    )

    fig.update_layout(
        title=f"Real Exchange Rate Index vs. Nominal Exchange Rate ({c1_name} / {c2_name})",
        xaxis_title="Date",
        hovermode="x unified",
        template="plotly_white",
        height=550,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Real Index (Mean = 100)", secondary_y=False)
    fig.update_yaxes(title_text=f"Nominal S(t) ({c2_name} per 1 {c1_name})", secondary_y=True)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# Data Export and Inspection Table
# ---------------------------------------------------------
st.subheader("Data & Calculation Export")

export_df = pd.DataFrame({
    "Date": df.index.strftime("%Y-%m"),
    "Country1_ISO": iso1,
    "Country2_ISO": iso2,
    "CPI_Country1_P1": df["P1"].round(4),
    "CPI_Country2_P2": df["P2"].round(4),
    "FX1_per_USD": df["e1_usd"].round(6),
    "FX2_per_USD": df["e2_usd"].round(6),
    "Nominal_S_t": df["S_t"].round(6),
    "RER_t_raw": df["RER_t"].round(6),
    "RER_benchmark_mean": round(rer_benchmark, 6),
    "Real_Index_t": df["Real_Index_t"].round(4),
})

csv_data = export_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="📥 Download Sample Observations as CSV",
    data=csv_data,
    file_name=f"rer_{iso1}_{iso2}_{start_d}_{end_d}.csv",
    mime="text/csv",
)

with st.expander("Preview Historical Calculations Table"):
    st.dataframe(export_df, use_container_width=True)
