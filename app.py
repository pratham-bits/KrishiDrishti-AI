"""
Irrigation Advisory Dashboard
Streamlit app entry point.

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from pathlib import Path

# ─── Page configuration ───
st.set_page_config(
    page_title="KrishiDrishti AI",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Import dashboard modules ───
from dashboard.components.sidebar import render_sidebar
from dashboard.components.crop_map import render_crop_map
from dashboard.components.stress_map import render_stress_map
from dashboard.components.advisory_map import render_advisory_map
from dashboard.components.time_series import render_time_series
from dashboard.components.metrics_panel import render_metrics


# ─── Main app ───
def main():
    st.title("🌾 AI-Driven Crop Monitoring & Irrigation Advisory")
    st.caption("KrishiDrishti AI | Nagarjunasagar Canal Command Area | Kharif 2024")

    # Sidebar controls
    config = render_sidebar()

    # ─── Tab layout: 4 main views ───
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗺️ Crop Type Map",
        "💧 Moisture Stress",
        "🚿 Irrigation Advisory",
        "📈 Time Series"
    ])

    with tab1:
        st.subheader("Crop Type Classification — Kharif 2024")
        st.caption("Random Forest | Rice · Maize · Cotton | Nagarjunasagar command area")
        render_crop_map(config)

    with tab2:
        st.subheader("Stage-Wise Moisture Stress Detection")
        st.caption("LSTM | VCI + NDWI + SAR backscatter | Growth stage aware")
        render_stress_map(config)

    with tab3:
        st.subheader("8-Day Irrigation Advisory")
        st.caption("FAO-56 water balance | ETc - P deficit | Canal command area")
        render_advisory_map(config)

    with tab4:
        st.subheader("Multi-Index Time Series")
        st.caption("NDVI · VCI · SAR backscatter · Water deficit across 6 epochs")
        render_time_series(config)

    # ─── Metrics footer ───
    with st.expander("📊 Model Performance Metrics", expanded=False):
        render_metrics()


if __name__ == "__main__":
    main()
