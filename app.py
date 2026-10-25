# ---------------------------------------------------------
# Charts
# ---------------------------------------------------------
if chart_mode == "Real Index (Base 100)":
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Real_Index_t"],
            mode="lines",
            name="Real Index",
            line=dict(color="#1f77b4", width=2.5)
        )
    )
    fig.add_hline(
        y=100, 
        line_dash="dash", 
        line_color="red", 
        annotation_text="Benchmark RER* = 100", 
        annotation_position="top left"
    )
    fig.update_layout(
        title=f"Real Exchange Rate Index: {c1_name} vs. {c2_name}",
        xaxis_title="Date",
        yaxis_title="Real Index",
        hovermode="x unified",
        template="plotly_white",
        height=550
    )

elif chart_mode == "Nominal S(t)":
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["S_t"],
            mode="lines",
            name="Nominal S(t)",
            line=dict(color="#2ca02c", width=2.5)
        )
    )
    fig.update_layout(
        title=f"Nominal Exchange Rate S(t): {c2_name} per 1 {c1_name}",
        xaxis_title="Date",
        yaxis_title=f"{c2_name} Units",
        hovermode="x unified",
        template="plotly_white",
        height=550
    )

else:  
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Real_Index_t"],
            name="Real Index (Base 100)",
            line=dict(color="#1f77b4", width=2.5)
        ),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["S_t"],
            name=f"Nominal S(t) ({c2_name} units)",
            line=dict(color="#2ca02c", width=2, dash="dot")
        ),
        secondary_y=True
    )
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="rgba(255, 0, 0, 0.7)",
        secondary_y=False,
        annotation_text="RER* = 100",
        annotation_position="top left"
    )
    fig.update_layout(
        title=f"Real Index vs. Nominal Spot Rate ({c1_name} / {c2_name})",
        xaxis_title="Date",
        hovermode="x unified",
        template="plotly_white",
        height=550,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="Real Index (Mean = 100)", secondary_y=False)
    fig.update_yaxes(title_text=f"Nominal S(t) ({c2_name} per 1 {c1_name})", secondary_y=True)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# CSV Download
# ---------------------------------------------------------
st.subheader("Data & Calculation Export")

export_df = pd.DataFrame({
    "Date": df.index.strftime("%Y-%m"),
    "Country1_ISO": iso1,
    "Country2_ISO": iso2,
    "CPI_Country1_P1": df["CPI1"].round(4),
    "CPI_Country2_P2": df["CPI2"].round(4),
    "FX1_per_USD": df["FX1_USD"].round(6),
    "FX2_per_USD": df["FX2_USD"].round(6),
    "Nominal_S_t": df["S_t"].round(6),
    "RER_t_raw": df["RER_t"].round(6),
    "RER_benchmark_mean": round(rer_star, 6),
    "Real_Index_t": df["Real_Index_t"].round(4),
})

st.download_button(
    label="📥 Download Observations as CSV", 
    data=export_df.to_csv(index=False).encode("utf-8"), 
    file_name=f"rer_{iso1}_{iso2}_{start_d}_{end_d}.csv", 
    mime="text/csv"
)

with st.expander("Preview Historical Calculations"):
    st.dataframe(export_df, use_container_width=True)
