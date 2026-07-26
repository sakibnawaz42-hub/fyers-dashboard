"""
Fyers Live F&O Dashboard
------------------------
Single-page Streamlit dashboard for F&O stocks showing:
  - Option chain (Call/Put) with OI, OI change %, Volume, Bid/Ask
  - PCR (Put-Call Ratio)
  - OI Support / OI Resistance (max Put OI / max Call OI strikes)
  - OI Crossover (Total Call OI vs Total Put OI over time)
  - 7 MA / 20 MA crossover on price
  - VWAP

Data source: Fyers API v3 (fyers-apiv3 python package)
"""

import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from fyers_apiv3 import fyersModel

# --------------------------------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------------------------------
st.set_page_config(page_title="Fyers F&O Live Dashboard", layout="wide")

# --------------------------------------------------------------------------
# SIDEBAR - CONNECTION + SETTINGS
# --------------------------------------------------------------------------
st.sidebar.title("⚙️ Settings")

client_id = st.sidebar.text_input(
    "Fyers App ID (client_id)",
    value=st.secrets.get("FYERS_CLIENT_ID", ""),
    help="Format: XXXXXX-100",
)
access_token = st.sidebar.text_input(
    "Access Token",
    value=st.secrets.get("FYERS_ACCESS_TOKEN", ""),
    type="password",
    help="Generate daily using generate_token.py (Fyers tokens expire every day).",
)

symbol = st.sidebar.text_input(
    "F&O Symbol (Fyers format)",
    value="NSE:RELIANCE-EQ",
    help="Example: NSE:RELIANCE-EQ, NSE:TCS-EQ, NSE:HDFCBANK-EQ",
).strip().upper()

strike_count = st.sidebar.slider("Strikes each side (Call/Put)", 5, 30, 10)
refresh_secs = st.sidebar.slider("Auto-refresh interval (seconds)", 15, 120, 30)
ma_short = st.sidebar.number_input("Short MA period", value=7, min_value=2)
ma_long = st.sidebar.number_input("Long MA period", value=20, min_value=3)
candle_interval = st.sidebar.selectbox(
    "Candle interval for MA / VWAP", ["1", "3", "5", "15"], index=2
)

st.sidebar.caption(
    "⚠️ Fyers access tokens expire daily around market open. "
    "Re-run generate_token.py each morning and update the token above "
    "(or in Streamlit Cloud → App settings → Secrets)."
)

if not client_id or not access_token:
    st.warning(
        "Sidebar me apna Fyers App ID aur Access Token daalein "
        "(ya Streamlit Cloud secrets me FYERS_CLIENT_ID / FYERS_ACCESS_TOKEN set karein)."
    )
    st.stop()

st_autorefresh(interval=refresh_secs * 1000, key="auto_refresh")

# --------------------------------------------------------------------------
# FYERS CLIENT
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_client(cid, token):
    return fyersModel.FyersModel(client_id=cid, token=token, is_async=False, log_path="")


fyers = get_client(client_id, access_token)


# --------------------------------------------------------------------------
# DATA FETCHERS
# --------------------------------------------------------------------------
def fetch_option_chain(symbol, strikecount):
    data = {"symbol": symbol, "strikecount": strikecount, "timestamp": ""}
    resp = fyers.optionchain(data=data)
    if resp.get("s") != "ok":
        raise RuntimeError(resp)
    return resp["data"]


def fetch_history(symbol, resolution, days_back=5):
    now = datetime.now()
    frm = now - timedelta(days=days_back)
    data = {
        "symbol": symbol,
        "resolution": resolution,
        "date_format": "1",
        "range_from": frm.strftime("%Y-%m-%d"),
        "range_to": now.strftime("%Y-%m-%d"),
        "cont_flag": "1",
    }
    resp = fyers.history(data=data)
    if resp.get("s") != "ok" or not resp.get("candles"):
        return pd.DataFrame()
    df = pd.DataFrame(
        resp["candles"], columns=["ts", "open", "high", "low", "close", "volume"]
    )
    df["datetime"] = pd.to_datetime(df["ts"], unit="s") + pd.Timedelta(hours=5, minutes=30)
    return df


# --------------------------------------------------------------------------
# FETCH + ERROR HANDLING
# --------------------------------------------------------------------------
try:
    chain = fetch_option_chain(symbol, strike_count)
except Exception as e:
    st.error(f"Option chain fetch fail hui: {e}")
    st.stop()

options_raw = chain.get("optionsChain", [])
underlying = next((o for o in options_raw if o.get("option_type") == ""), {})
ltp = underlying.get("ltp", chain.get("callOi", 0))

rows = [o for o in options_raw if o.get("option_type") in ("CE", "PE")]
df = pd.DataFrame(rows)

if df.empty:
    st.error("Option chain khali aayi — symbol ya strikecount check karein.")
    st.stop()

calls = df[df["option_type"] == "CE"].sort_values("strike_price").reset_index(drop=True)
puts = df[df["option_type"] == "PE"].sort_values("strike_price").reset_index(drop=True)

total_call_oi = calls["oi"].sum()
total_put_oi = puts["oi"].sum()
pcr = round(total_put_oi / total_call_oi, 3) if total_call_oi else 0.0

oi_resistance = calls.loc[calls["oi"].idxmax(), "strike_price"] if not calls.empty else None
oi_support = puts.loc[puts["oi"].idxmax(), "strike_price"] if not puts.empty else None

# --------------------------------------------------------------------------
# OI CROSSOVER HISTORY (kept in session so it builds up across refreshes)
# --------------------------------------------------------------------------
if "oi_history" not in st.session_state:
    st.session_state.oi_history = []

st.session_state.oi_history.append(
    {"time": datetime.now(), "call_oi": total_call_oi, "put_oi": total_put_oi}
)
st.session_state.oi_history = st.session_state.oi_history[-200:]  # cap size
oi_hist_df = pd.DataFrame(st.session_state.oi_history)

oi_crossover_signal = "—"
if len(oi_hist_df) >= 2:
    prev_diff = oi_hist_df.iloc[-2]["call_oi"] - oi_hist_df.iloc[-2]["put_oi"]
    curr_diff = oi_hist_df.iloc[-1]["call_oi"] - oi_hist_df.iloc[-1]["put_oi"]
    if prev_diff <= 0 < curr_diff:
        oi_crossover_signal = "🔴 Call OI ne Put OI cross kiya (Bearish)"
    elif prev_diff >= 0 > curr_diff:
        oi_crossover_signal = "🟢 Put OI ne Call OI cross kiya (Bullish)"
    else:
        oi_crossover_signal = "Call OI > Put OI" if curr_diff > 0 else "Put OI > Call OI"

# --------------------------------------------------------------------------
# HISTORICAL CANDLES → MA CROSSOVER + VWAP
# --------------------------------------------------------------------------
hist = fetch_history(symbol, candle_interval)
ma_signal, vwap_val, last_close = "—", None, None

if not hist.empty:
    hist[f"MA{ma_short}"] = hist["close"].rolling(ma_short).mean()
    hist[f"MA{ma_long}"] = hist["close"].rolling(ma_long).mean()
    hist["typical_price"] = (hist["high"] + hist["low"] + hist["close"]) / 3

    today = hist[hist["datetime"].dt.date == datetime.now().date()]
    if not today.empty:
        cum_vol = today["volume"].cumsum()
        cum_tpv = (today["typical_price"] * today["volume"]).cumsum()
        vwap_val = round((cum_tpv / cum_vol).iloc[-1], 2)

    if len(hist) >= 2 and hist[f"MA{ma_long}"].notna().sum() >= 2:
        prev_short, prev_long = hist.iloc[-2][f"MA{ma_short}"], hist.iloc[-2][f"MA{ma_long}"]
        curr_short, curr_long = hist.iloc[-1][f"MA{ma_short}"], hist.iloc[-1][f"MA{ma_long}"]
        if prev_short <= prev_long < curr_short >= curr_long:
            ma_signal = f"🟢 Golden Cross (MA{ma_short} > MA{ma_long})"
        elif prev_short >= prev_long > curr_short <= curr_long:
            ma_signal = f"🔴 Death Cross (MA{ma_short} < MA{ma_long})"
        else:
            ma_signal = f"MA{ma_short} > MA{ma_long}" if curr_short > curr_long else f"MA{ma_short} < MA{ma_long}"
    last_close = round(hist.iloc[-1]["close"], 2)

# --------------------------------------------------------------------------
# UI — TOP METRICS
# --------------------------------------------------------------------------
st.title(f"📊 {symbol} — Live F&O Dashboard")
st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')} | Auto-refresh every {refresh_secs}s")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("LTP", last_close if last_close else ltp)
c2.metric("PCR", pcr)
c3.metric("OI Support", oi_support)
c4.metric("OI Resistance", oi_resistance)
c5.metric("VWAP", vwap_val if vwap_val else "—")
c6.metric(f"MA{ma_short}/MA{ma_long}", ma_signal)

st.info(f"**OI Crossover Signal:** {oi_crossover_signal}")

# --------------------------------------------------------------------------
# OI CROSSOVER CHART
# --------------------------------------------------------------------------
st.subheader("OI Crossover — Total Call OI vs Total Put OI")
if len(oi_hist_df) >= 2:
    chart_df = oi_hist_df.set_index("time")[["call_oi", "put_oi"]]
    st.line_chart(chart_df)
else:
    st.caption("Crossover chart build karne ke liye kam se kam 2 refresh cycles chahiye.")

# --------------------------------------------------------------------------
# PRICE + MA + VWAP CHART
# --------------------------------------------------------------------------
st.subheader(f"Price with MA{ma_short}, MA{ma_long} & VWAP ({candle_interval} min candles)")
if not hist.empty:
    plot_df = hist.set_index("datetime")[["close", f"MA{ma_short}", f"MA{ma_long}"]].tail(150)
    st.line_chart(plot_df)
else:
    st.caption("Historical candles nahi mile.")

# --------------------------------------------------------------------------
# OI BY STRIKE (BAR) + OPTION CHAIN TABLE
# --------------------------------------------------------------------------
st.subheader("OI by Strike (Call vs Put)")
oi_bar = pd.DataFrame(
    {
        "strike": calls["strike_price"].values,
        "Call OI": calls["oi"].values,
        "Put OI": puts.set_index("strike_price").reindex(calls["strike_price"])["oi"].values,
    }
).set_index("strike")
st.bar_chart(oi_bar)

st.subheader("Option Chain — Live")


def build_table(leg_df, label):
    cols = {
        "strike_price": "Strike",
        "ltp": "LTP",
        "bid": "Bid",
        "ask": "Ask",
        "volume": "Volume",
        "oi": "OI",
        "oich": "OI Chg",
        "oichp": "OI Chg %",
    }
    out = leg_df[[c for c in cols if c in leg_df.columns]].rename(columns=cols)
    out.insert(0, "Type", label)
    return out


table = pd.concat([build_table(calls, "CE"), build_table(puts, "PE")], ignore_index=True)
st.dataframe(table, use_container_width=True, hide_index=True)

st.caption(
    "Data source: Fyers API v3 (optionchain + history endpoints). "
    "OI Support = highest Put OI strike, OI Resistance = highest Call OI strike."
)
