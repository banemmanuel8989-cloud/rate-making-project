#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st

def run_app():
    # 1. Rating Manual Data (Werner & Modlin Chapter 2)
    CLASS_RATES = {
        "8810": 0.49,  # Clerical
        "8825": 2.77,  # Food Service
        "8824": 3.99   # Health Care
    }
    
    # Constants
    EXP_MOD_FIXED = 0.95        
    SCHEDULE_MOD = 0.90   
    DISCOUNT_MOD = 0.95   
    EXPENSE_CONSTANT = 250.00

    # UI Header
    st.title("🛡️ Workers' Comp Rate Calculator")
    st.markdown("### Wicked Good Insurance Company (WGIC)")
    st.info("Based on Werner & Modlin: Basic Ratemaking, Chapter 2")

    # Sidebar Inputs (Impervious to error via constrained widgets)
    st.sidebar.header("Policy Inputs")
    code = st.sidebar.selectbox("Select Class Code", list(CLASS_RATES.keys()))
    payroll = st.sidebar.number_input("Annual Payroll ($)", min_value=0.0, value=50000.0, step=1000.0)
    
    # Calculation Logic
    rate = CLASS_RATES[code]
    manual_premium = (payroll / 100) * rate
    modified_premium = manual_premium * EXP_MOD_FIXED
    standard_premium = modified_premium * SCHEDULE_MOD
    net_premium = (standard_premium * DISCOUNT_MOD) + EXPENSE_CONSTANT

    # Visual Output
    col1, col2 = st.columns(2)
    col1.metric("Manual Premium", f"${manual_premium:,.2f}")
    col2.metric("Net Premium Due", f"${net_premium:,.2f}", delta="-Step-by-step logic applied")

    with st.expander("View Detailed Rating Steps"):
        st.write(f"**Step 1:** Base Rate for {code} is {rate}")
        st.write(f"**Step 2:** Manual Premium ($payroll/100 * rate) = ${manual_premium:,.2f}")
        st.write(f"**Step 3:** Applying Experience Mod (0.95) = ${modified_premium:,.2f}")
        st.write(f"**Step 4:** Applying Schedule & Discount Mods = ${standard_premium * DISCOUNT_MOD:,.2f}")
        st.write(f"**Step 5:** Adding Expense Constant ($250) = **${net_premium:,.2f}**")

if __name__ == "__main__":
    run_app()

