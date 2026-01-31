#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import pandas as pd

# Page configuration
st.set_page_config(page_title="WC Rate Calculator", page_icon="🛡️", layout="wide")

# Custom CSS for a professional look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e1e4e8; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ Workers' Compensation Rate Calculator: Project Edition")
st.caption("Reference: Werner & Modlin [WM] | Standard Schedule Rating Cap: +/- 25%")

# --- SIDEBAR INPUTS ---
st.sidebar.header("📋 Policy Information")

# Table 1: Manual Rates
RATES = {"8810": 0.45, "8824": 3.50, "8825": 2.65, "5183": 5.12}
code = st.sidebar.selectbox("Select Class Code", list(RATES.keys()))
payroll = st.sidebar.number_input("Annual Payroll ($)", min_value=0.0, value=100000.0, step=1000.0)
exp_mod = st.sidebar.number_input("Experience Modification Factor", min_value=0.0, value=1.00, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("📊 Schedule Rating Inputs")
# Collecting percentage inputs as slider/numbers
prem_adj = st.sidebar.slider("Premises (-0.1% to +0.1%)", -0.1, 0.1, 0.0, 0.01) / 100
pecul_adj = st.sidebar.slider("Class Peculiarities (-0.1% to +0.1%)", -0.1, 0.1, 0.0, 0.01) / 100
med_adj = st.sidebar.slider("Medical Facilities (-0.05% to +0.05%)", -0.05, 0.05, 0.0, 0.01) / 100
safe_adj = st.sidebar.slider("Safety Devices (-0.5% to 0.0%)", -0.5, 0.0, 0.0, 0.01) / 100
train_adj = st.sidebar.slider("Selection & Training (-0.5% to +0.5%)", -0.5, 0.5, 0.0, 0.01) / 100
mgmt_adj = st.sidebar.slider("Management Safety (-0.05% to +0.05%)", -0.05, 0.05, 0.0, 0.01) / 100

st.sidebar.markdown("---")
st.sidebar.header("✅ Program Credits")
drug_credit_eligible = st.sidebar.radio("Pre-employment Drug Screening (5% Credit)?", ["No", "Yes"]) == "Yes"
eap_eligible = st.sidebar.checkbox("Employee Assistant Program (0% Credit)")
rtw_eligible = st.sidebar.checkbox("Return to Work Program (0% Credit)")

# --- CALCULATION LOGIC ---
# Step 1: Manual Premium
manual_prem = (payroll / 100) * RATES[code]

# Step 2: Modified Premium (Experience Mod applies to Manual per WM pg 297)
modified_prem = manual_prem * exp_mod

# Step 3: Standard Premium (Apply Capped Schedule Mod)
raw_adj_sum = prem_adj + pecul_adj + med_adj + safe_adj + train_adj + mgmt_adj
applied_adj = max(min(raw_adj_sum, 0.25), -0.25)
standard_prem = modified_prem * (1.0 + applied_adj)

# Step 4: Apply Drug Screening Credit (5%)
drug_credit_amt = (standard_prem * 0.05) if drug_credit_eligible else 0.0

# Step 5: Final Net Premium
EXPENSE_CONSTANT = 150.00
net_premium = (standard_prem - drug_credit_amt) + EXPENSE_CONSTANT

# --- UI DASHBOARD ---
col1, col2, col3 = st.columns(3)
col1.metric("Manual Premium", f"${manual_prem:,.2f}")
col2.metric("Standard Premium", f"${standard_prem:,.2f}")
col3.metric("Net Premium Due", f"${net_premium:,.2f}", delta_color="inverse")

st.markdown("### 📝 Premium Calculation Exhibit")

# Building the display table
exhibit_data = {
    "Description": [
        "Manual Premium",
        "Experience Modification",
        "Modified Premium (Manual x Mod)",
        "Schedule Adjustment (Capped at 25%)",
        "Standard Premium",
        "Drug Screening Credit (5%)",
        "EAP / RTW Programs (0%)",
        "Expense Constant",
        "NET PREMIUM DUE"
    ],
    "Calculation / Factor": [
        f"${manual_prem:,.2f}",
        f"{exp_mod:.2f}",
        f"${modified_prem:,.2f}",
        f"{applied_adj*100:.3f}%",
        f"${standard_prem:,.2f}",
        f"-${drug_credit_amt:,.2f}",
        "Included" if (eap_eligible or rtw_eligible) else "N/A",
        f"${EXPENSE_CONSTANT:,.2f}",
        f"${net_premium:,.2f}"
    ]
}

df = pd.DataFrame(exhibit_data)
st.table(df)

# Download Button for the Exhibit
if st.button("Generate Quote Report"):
    report_text = df.to_string(index=False)
    st.download_button("Download Report (.txt)", report_text, file_name="WC_Premium_Quote.txt")


# In[ ]:




