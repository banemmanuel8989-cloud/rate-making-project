#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np

# 1. Load Data
df = pd.read_csv('classification_ratemaking_project_data.csv')

def run_pricing_engine(selected_class):
    # Filter for the selected class and the "All Class" aggregate for credibility
    class_data = df[df['class_id'] == selected_class].copy()
    all_data = df.copy()
    
    # --- STEP 1: LOSS DEVELOPMENT (Chain Ladder) ---
    # We will use Incurred Loss development. 
    # Factors: 12-24, 24-36, 36-48, 48-60.
    inc_cols = ['incurred_loss_12', 'incurred_loss_24', 'incurred_loss_36', 'incurred_loss_48', 'incurred_loss_60']
    
    def get_ldfs(data):
        factors = []
        for i in range(len(inc_cols)-1):
            # Arithmetic average of age-to-age factors
            ratio = data[inc_cols[i+1]] / data[inc_cols[i]]
            factors.append(ratio.mean())
        return factors

    ldfs = get_ldfs(all_data) # Use all-class for stable development factors
    tail_factor = 1.05 # Appropriately chosen tail
    
    # Cumulative Development Factors (CDF)
    cdfs = [np.prod(ldfs[i:]) * tail_factor for i in range(len(ldfs))] + [tail_factor]
    
    # Apply CDFs based on available months
    def calc_ultimate(row):
        age = row['incurred_age_available_months']
        if age == 12: return row['incurred_loss_12'] * cdfs[0]
        if age == 24: return row['incurred_loss_24'] * cdfs[1]
        if age == 36: return row['incurred_loss_36'] * cdfs[2]
        if age == 48: return row['incurred_loss_48'] * cdfs[3]
        return row['incurred_loss_60'] * cdfs[4]

    class_data['ultimate_loss'] = class_data.apply(calc_ultimate, axis=1)
    
    # --- STEP 2: TRENDING ---
    # Projection to mid-point of 2026 (2026.5)
    class_data['years_to_trend'] = 2026.5 - (class_data['accident_year'] + 0.5)
    freq_trend = class_data['selected_annual_frequency_trend'].iloc[0]
    sev_trend = class_data['selected_annual_severity_trend'].iloc[0]
    total_trend = (1 + freq_trend) * (1 + sev_trend) - 1
    
    class_data['trended_ultimate_loss'] = class_data['ultimate_loss'] * ((1 + total_trend) ** class_data['years_to_trend'])
    
    # --- STEP 3: INDICATED LOSS COST (PURE PREMIUM) ---
    total_trended_losses = class_data['trended_ultimate_loss'].sum()
    total_exposures = class_data['earned_exposures'].sum()
    pure_premium = total_trended_losses / total_exposures
    
    # --- STEP 4: EXPENSES AND PROFIT ---
    # Using the most recent year's assumptions
    latest = class_data.sort_values('accident_year').iloc[-1]
    lae_pct = latest['lae_provision_ratio_to_losses']
    var_exp = latest['variable_expense_ratio']
    fixed_exp = latest['fixed_expense_per_exposure']
    profit = latest['profit_and_contingency_ratio']
    
    # Indicated Premium Formula: (Pure Premium * (1 + LAE) + Fixed Expense) / (1 - Var Expense - Profit)
    indicated_premium_class = (pure_premium * (1 + lae_pct) + fixed_exp) / (1 - var_exp - profit)
    
    # --- STEP 5: CREDIBILITY ---
    # Simple Square Root Rule (Full credibility at 1000 claims)
    total_claims = class_data['reported_claim_count'].sum()
    z = min(1.0, np.sqrt(total_claims / 1000))
    
    # Complement: Indicated premium for ALL classes combined
    # (Simplified for this engine: using the current average premium as the complement)
    complement = all_data['current_avg_premium_per_exposure'].mean()
    
    final_premium = (z * indicated_premium_class) + ((1 - z) * complement)
    
    # --- OUTPUT TRACE ---
    print(f"--- PRICING INDICATION FOR CLASS {selected_class} ---")
    print(f"Total Trended Ultimate Losses: ${total_trended_losses:,.0f}")
    print(f"Total Earned Exposures: {total_exposures:,.0f}")
    print(f"Pure Premium: ${pure_premium:.2f}")
    print(f"Credibility (Z): {z:.2%}")
    print(f"Indicated Premium (Class): ${indicated_premium_class:.2f}")
    print(f"Complement of Credibility: ${complement:.2f}")
    print(f"FINAL INDICATED PREMIUM PER EXPOSURE: ${final_premium:.2f}")

# Example Menu Selection
run_pricing_engine('A')


# In[ ]:




