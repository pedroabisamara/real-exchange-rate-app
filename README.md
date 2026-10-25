# real-exchange-rate-app

An interactive web application built with Streamlit and Plotly that calculates and visualizes the **Real Exchange Rate (RER)** and **Nominal Spot Exchange Rate** between IMF member countries and the Euro Area.

## Methodological Definitions

1. **Nominal Rate $S(t)$**:
   $$S(t) = \frac{e_2^{\text{USD}}(t)}{e_1^{\text{USD}}(t)}$$
   Expressed as units of Country 2 currency per 1 unit of Country 1 currency.
   
2. **Real Exchange Rate $\text{RER}(t)$**:
   $$\text{RER}(t) = \frac{S(t) \cdot P_1(t)}{P_2(t)}$$
   Where $P_1(t)$ and $P_2(t)$ are monthly Consumer Price Indices (CPI) from the IMF.

3. **Benchmark $\text{RER}^*$ & Normalized Real Index**:
   $$\text{RER}^* = \frac{1}{N}\sum_{t=1}^N \text{RER}(t)$$
   $$\text{Real Index}(t) = 100 \times \frac{\text{RER}(t)}{\text{RER}^*}$$
   Where $\text{RER}^*$ is dynamically computed as the arithmetic mean of all valid monthly observations in the user-selected date range.

## Requirements & Compatibility

- Python 3.12+
- `streamlit`
- `requests`
- `pandas`
- `plotly`

## Installation & Local Execution

1. Clone or download this repository:
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/<your-repo-name>.git
   cd <your-repo-name>
