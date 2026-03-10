#!/usr/bin/env python
# coding: utf-8

# In[2]:


import streamlit as st
import pandas as pd
import numpy as np

# Set up the page layout
st.set_page_config(page_title="Actuarial Pricing Engine", layout="wide")

st.title("🛡️ Actuarial Pricing & Ratemaking Engine")
st.markdown("""
This engine produces the indicated premium per exposure for the 2026 policy year based on historical experience. 
It utilizes **Chain Ladder Loss Development**, **Frequency/Severity Trending**, **Expense Loading**, and **Classical Credibility**.
""")

@st.cache_data
def load_data():
    # Ensure 'classification_ratemaking_project_data.csv' is in the same directory
    return pd.read_csv('classification_ratemaking_project_data.csv')

try:
    df = load_data()
    
    # --- SIDEBAR: INPUTS ---
    st.sidebar.header("Pricing Parameters")
    class_list = sorted(df['class_id'].unique())
    selected_class = st.sidebar.selectbox("Select Risk Class", options=class_list)
    
    # Allow user to refine the tail factor and credibility standard
    tail_factor = st.sidebar.slider("Tail Factor (60-to-Ult)", 1.0, 1.20, 1.05, 0.01)
    credibility_standard = st.sidebar.number_input("Full Credibility Standard (Claims)", value=1000)

    # --- CALCULATION LOGIC ---
    def calculate_indication(sel_class):
        class_data = df[df['class_id'] == sel_class].copy()
        all_data = df.copy()
        
        # 1. Loss Development (Chain Ladder)
        # Using Incurred Loss development columns
        inc_cols = ['incurred_loss_12', 'incurred_loss_24', 'incurred_loss_36', 'incurred_loss_48', 'incurred_loss_60']
        
        # Calculate Age-to-Age Factors (ATA) using all-class data for stability
        ata_factors = []
        for i in range(len(inc_cols)-1):
            ratio = all_data[inc_cols[i+1]].sum() / all_data[inc_cols[i]].sum()
            ata_factors.append(ratio)
            
        # Cumulative Development Factors (CDF)
        cdfs = [1.0] * 5
        cdfs[4] = tail_factor
        for i in range(3, -1, -1):
            cdfs[i] = ata_factors[i] * cdfs[i+1]
        
        # Apply CDFs to estimate Ultimate Losses based on current maturity
        def get_ultimate(row):
            age = row['incurred_age_available_months']
            idx = int(age/12) - 1
            if 0 <= idx < 5:
                return row[inc_cols[idx]] * cdfs[idx]
            return row['incurred_loss_60'] * tail_factor

        class_data['ultimate_loss'] = class_data.apply(get_ultimate, axis=1)
        
        # 2. Trending (Projection to mid-point of 2026 = 2026.5)
        class_data['years_to_trend'] = 2026.5 - (class_data['accident_year'] + 0.5)
        f_trend = class_data['selected_annual_frequency_trend'].iloc[0]
        s_trend = class_data['selected_annual_severity_trend'].iloc[0]
        total_trend = (1 + f_trend) * (1 + s_trend) - 1
        
        class_data['trend_factor'] = (1 + total_trend) ** class_data['years_to_trend']
        class_data['trended_ultimate_loss'] = class_data['ultimate_loss'] * class_data['trend_factor']
        
        # 3. Indicated Pure Premium (Loss Cost per Exposure)
        total_losses = class_data['trended_ultimate_loss'].sum()
        total_exp = class_data['earned_exposures'].sum()
        pure_premium = total_losses / total_exp
        
        # 4. Expense & Profit Loading
        latest = class_data.sort_values('accident_year').iloc[-1]
        lae_pct = latest['lae_provision_ratio_to_losses']
        v_exp = latest['variable_expense_ratio']
        f_exp = latest['fixed_expense_per_exposure']
        prof = latest['profit_and_contingency_ratio']
        
        # Premium Formula
        denom = (1 - v_exp - prof)
        class_indication = (pure_premium * (1 + lae_pct) + f_exp) / denom
        
        # 5. Credibility (Square Root Rule)
        total_claims = class_data['reported_claim_count'].sum()
        z = min(1.0, np.sqrt(total_claims / credibility_standard))
        
        # Complement of Credibility (Average premium of all classes)
        complement = all_data['current_avg_premium_per_exposure'].mean()
        
        final_premium = (z * class_indication) + ((1 - z) * complement)
        
        return {
            "final": final_premium, "class_ind": class_indication, "pure_prem": pure_premium,
            "z": z, "complement": complement, "total_losses": total_losses, "total_exp": total_exp,
            "ata": ata_factors, "cdfs": cdfs, "trends": (f_trend, s_trend), "claims": total_claims,
            "expenses": (lae_pct, v_exp, f_exp, prof), "data": class_data
        }

    results = calculate_indication(selected_class)

    # --- UI DASHBOARD ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Indicated Premium", f"${results['final']:.2f}")
    col2.metric("Credibility (Z)", f"{results['z']:.1%}")
    col3.metric("Pure Premium", f"${results['pure_prem']:.2f}")

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📊 Summary", "🔍 Actuarial Trace", "📈 Historical Experience"])

    with tab1:
        st.write(f"The final premium for Class **{selected_class}** is a blend of the indicated cost and the portfolio average.")
        st.table(pd.DataFrame({
            "Source": ["Class Experience", "Complement (All-Class)", "Weighted Total"],
            "Indicated Premium": [f"${results['class_ind']:.2f}", f"${results['complement']:.2f}", f"${results['final']:.2f}"],
            "Weighting": [f"{results['z']:.1%}", f"{1-results['z']:.1%}", "100.0%"]
        }))

    with tab2:
        st.subheader("Step-by-Step Indication Calculation")
        st.write("**1. Loss Development:**")
        st.write("Age-to-Age Factors:", pd.DataFrame([results['ata']], columns=["12-24", "24-36", "36-48", "48-60"]))
        st.write("CDFs (to Ultimate):", pd.DataFrame([results['cdfs']], columns=["12-Ult", "24-Ult", "36-Ult", "48-Ult", "60-Ult"]))
        
        st.write("**2. Expenses:**")
        lae, v_exp, f_exp, prof = results['expenses']
        st.latex(fr"\frac{{(PurePremium \times (1 + {lae})) + {f_exp}}}{{1 - {v_exp} - {prof}}} = \${results['class_ind']:.2f}")

    with tab3:
        st.write(f"Historical Trended Data for {selected_class}")
        st.dataframe(results['data'][['accident_year', 'earned_exposures', 'ultimate_loss', 'trend_factor', 'trended_ultimate_loss']].style.format({
            'ultimate_loss': '${:,.0f}', 'trended_ultimate_loss': '${:,.0f}', 'trend_factor': '{:.4f}'
        }))

except Exception as e:
    st.error(f"Error processing data: {e}")


# In[ ]:




