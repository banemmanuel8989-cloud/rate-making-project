#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd

# 1. Page Config & Professional Styling
st.set_page_config(page_title="WC Live Quote", page_icon="🛡️", layout="centered")

st.markdown("""
    <style>
    .big-font { font-size:40px !important; font-weight: bold; color: #1E3A8A; }
    .quote-box { background-color: #f0f4f8; padding: 20px; border-radius: 10px; border-left: 5px solid #1E3A8A; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Sidebar: Inputs (The "Controls")
st.sidebar.header("📋 Policy Setup")
RATES = {"8810": 0.45, "8824": 3.50, "8825": 2.65, "5183": 5.12}
selected_code = st.sidebar.selectbox("Class Code", list(RATES.keys()))
payroll = st.sidebar.number_input("Annual Payroll ($)", min_value=0.0, value=100000.0, step=1000.0)
exp_mod = st.sidebar.number_input("Experience Mod Factor", min_value=0.0, value=1.00, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("📊 Schedule Rating (%)")
prem_adj = st.sidebar.slider("Premises (-0.1 to +0.1)", -0.1, 0.1, 0.0, 0.01) / 100
pecul_adj = st.sidebar.slider("Class Peculiarities (-0.1 to +0.1)", -0.1, 0.1, 0.0, 0.01) / 100
med_adj = st.sidebar.slider("Medical Facilities (-0.05 to +0.05)", -0.05, 0.05, 0.0, 0.01) / 100
safe_adj = st.sidebar.slider("Safety Devices (-0.5 to 0.0)", -0.5, 0.0, 0.0, 0.01) / 100
train_adj = st.sidebar.slider("Selection & Training (-0.5 to +0.5)", -0.5, 0.5, 0.0, 0.01) / 100
mgmt_adj = st.sidebar.slider("Management Safety (-0.05 to +0.05)", -0.05, 0.05, 0.0, 0.01) / 100

st.sidebar.markdown("---")
drug_credit = st.sidebar.checkbox("Pre-employment Drug Screening (5%)")

# 3. Calculation Engine (Runs automatically on any input change)
manual_prem = (payroll / 100) * RATES[selected_code]
modified_prem = manual_prem * exp_mod
total_raw_adj = prem_adj + pecul_adj + med_adj + safe_adj + train_adj + mgmt_adj
applied_sched_adj = max(min(total_raw_adj, 0.25), -0.25)
standard_prem = modified_prem * (1.0 + applied_sched_adj)
drug_amt = (standard_prem * 0.05) if drug_credit else 0.0
EXPENSE_CONSTANT = 150.0
net_premium = (standard_prem - drug_amt) + EXPENSE_CONSTANT

# 4. Main Display: The "Live Quote"
st.title("🛡️ Workers' Comp Live Quote")

# Big Live Result at the top
st.markdown('<div class="quote-box">', unsafe_allow_html=True)
st.write("Estimated Net Premium Due:")
st.markdown(f'<p class="big-font">${net_premium:,.2f}</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Detailed Breakdown below
with st.expander("🔍 View Detailed Rating Exhibit", expanded=True):
    exhibit_data = [
        ["Manual Premium", f"${manual_prem:,.2f}"],
        ["Experience Modification", f"{exp_mod:.2f}"],
        ["Modified Premium (WM pg 297)", f"${modified_prem:,.2f}"],
        ["Schedule Adjustment (Capped)", f"{applied_sched_adj*100:+.3f}%"],
        ["Standard Premium", f"${standard_prem:,.2f}"],
        ["Drug Screening Credit", f"-${drug_amt:,.2f}"],
        ["Expense Constant", f"${EXPENSE_CONSTANT:,.2f}"],
        ["TOTAL NET PREMIUM", f"${net_premium:,.2f}"]
    ]
    df = pd.DataFrame(exhibit_data, columns=["Description", "Amount / Factor"])
    st.table(df)

st.download_button("Download Quote Summary", df.to_csv(index=False), "WC_Quote.csv", "text/csv")

