#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class PricingEngine:
    def __init__(self, data_file):
        """
        Initialize the pricing engine with the CSV data
        """
        self.df = pd.read_csv(data_file)
        self.classes = self.df['class_id'].unique()
        self.all_class_df = self.df.copy()
        self.tail_factor = 1.02  # Selected tail factor (2% development beyond 60 months)
        
        # Store results
        self.ultimate_losses = {}
        self.loss_ratios = {}
        self.indicated_premiums = {}
        
    def calculate_age_to_age_factors(self, loss_type='paid'):
        """
        Calculate age-to-age factors using chain ladder method
        """
        ldfs = {}
        
        for class_id in self.classes:
            class_data = self.df[self.df['class_id'] == class_id].copy()
            
            # Create development triangle
            dev_triangle = {}
            for col in [f'{loss_type}_loss_12', f'{loss_type}_loss_24', f'{loss_type}_loss_36', 
                       f'{loss_type}_loss_48', f'{loss_type}_loss_60']:
                if col in class_data.columns:
                    age = int(col.split('_')[-1])
                    dev_triangle[age] = class_data[col].values
            
            dev_df = pd.DataFrame(dev_triangle)
            
            # Calculate age-to-age factors
            factors = []
            for i in range(len(dev_df.columns) - 1):
                current_age = dev_df.columns[i]
                next_age = dev_df.columns[i + 1]
                
                # Select only complete pairs (both ages have data)
                mask = ~(dev_df[current_age].isna() | dev_df[next_age].isna())
                if mask.sum() > 0:
                    factor = (dev_df.loc[mask, next_age] / dev_df.loc[mask, current_age]).mean()
                    factors.append(factor)
                else:
                    factors.append(np.nan)
            
            ldfs[class_id] = factors
        
        return ldfs
    
    def estimate_ultimate_losses(self):
        """
        Estimate ultimate losses for each class and accident year
        using chain ladder method with arithmetic average age-to-age factors
        """
        paid_factors = self.calculate_age_to_age_factors('paid')
        incurred_factors = self.calculate_age_to_age_factors('incurred')
        
        for class_id in self.classes:
            class_data = self.df[self.df['class_id'] == class_id].copy()
            class_ultimates = []
            
            for idx, row in class_data.iterrows():
                accident_year = row['accident_year']
                
                # Get latest paid and incurred values
                paid_12 = row['paid_loss_12']
                paid_24 = row['paid_loss_24'] if not pd.isna(row['paid_loss_24']) else paid_12
                paid_36 = row['paid_loss_36'] if not pd.isna(row['paid_loss_36']) else paid_24
                paid_48 = row['paid_loss_48'] if not pd.isna(row['paid_loss_48']) else paid_36
                paid_60 = row['paid_loss_60'] if not pd.isna(row['paid_loss_60']) else paid_48
                
                incurred_12 = row['incurred_loss_12']
                incurred_24 = row['incurred_loss_24'] if not pd.isna(row['incurred_loss_24']) else incurred_12
                incurred_36 = row['incurred_loss_36'] if not pd.isna(row['incurred_loss_36']) else incurred_24
                incurred_48 = row['incurred_loss_48'] if not pd.isna(row['incurred_loss_48']) else incurred_36
                incurred_60 = row['incurred_loss_60'] if not pd.isna(row['incurred_loss_60']) else incurred_48
                
                # Determine latest age and value
                latest_paid = None
                latest_incurred = None
                latest_age = row['paid_age_available_months']
                
                if latest_age == 12:
                    latest_paid = paid_12
                    latest_incurred = incurred_12
                elif latest_age == 24:
                    latest_paid = paid_24
                    latest_incurred = incurred_24
                elif latest_age == 36:
                    latest_paid = paid_36
                    latest_incurred = incurred_36
                elif latest_age == 48:
                    latest_paid = paid_48
                    latest_incurred = incurred_48
                elif latest_age == 60:
                    latest_paid = paid_60
                    latest_incurred = incurred_60
                
                # Project to ultimate using factors
                if class_id in paid_factors and len(paid_factors[class_id]) > 0:
                    # Calculate cumulative factor to ultimate
                    cum_factor = 1.0
                    ages = [12, 24, 36, 48, 60]
                    age_idx = ages.index(latest_age)
                    
                    for i in range(age_idx, len(paid_factors[class_id])):
                        if not pd.isna(paid_factors[class_id][i]):
                            cum_factor *= paid_factors[class_id][i]
                    
                    # Apply tail factor
                    cum_factor *= self.tail_factor
                    
                    # Project ultimate loss (use minimum of paid and incurred projections)
                    paid_ultimate = latest_paid * cum_factor if latest_paid else np.nan
                    incurred_ultimate = latest_incurred * cum_factor if latest_incurred else np.nan
                    
                    # Use incurred if available and credible, otherwise use paid
                    if not pd.isna(incurred_ultimate) and incurred_ultimate > 0:
                        ultimate = max(paid_ultimate, incurred_ultimate) if not pd.isna(paid_ultimate) else incurred_ultimate
                    else:
                        ultimate = paid_ultimate if not pd.isna(paid_ultimate) else np.nan
                    
                    class_ultimates.append({
                        'class_id': class_id,
                        'accident_year': accident_year,
                        'latest_paid': latest_paid,
                        'latest_incurred': latest_incurred,
                        'latest_age': latest_age,
                        'ultimate_loss': ultimate,
                        'earned_exposures': row['earned_exposures'],
                        'earned_premium': row['earned_premium'],
                        'reported_claim_count': row['reported_claim_count']
                    })
            
            self.ultimate_losses[class_id] = pd.DataFrame(class_ultimates)
        
        # Calculate all-class ultimates
        all_class_ultimates = []
        for class_id in self.classes:
            all_class_ultimates.append(self.ultimate_losses[class_id])
        
        self.all_class_ultimates = pd.concat(all_class_ultimates, ignore_index=True)
        
        return self.ultimate_losses
    
    def calculate_trended_losses(self, trend_rate=0.012, severity_trend=0.055, 
                                  policy_year_start=2026, policy_year_end=2026):
        """
        Project losses to future policy year using frequency and severity trends
        """
        trended_results = {}
        
        for class_id in self.classes:
            class_ultimates = self.ultimate_losses[class_id].copy()
            
            # Calculate average accident date (mid-year)
            class_ultimates['avg_accident_date'] = class_ultimates['accident_year'] + 0.5
            
            # Policy period mid-point
            policy_mid = (policy_year_start + policy_year_end) / 2
            
            # Calculate trend period in years
            class_ultimates['trend_years'] = policy_mid - class_ultimates['avg_accident_date']
            
            # Apply compound trends
            # Frequency trend applied to claim count, severity trend to average severity
            class_ultimates['frequency'] = class_ultimates['reported_claim_count'] / class_ultimates['earned_exposures']
            class_ultimates['avg_severity'] = class_ultimates['ultimate_loss'] / class_ultimates['reported_claim_count']
            
            # Project frequency and severity
            class_ultimates['trended_frequency'] = class_ultimates['frequency'] * (1 + trend_rate) ** class_ultimates['trend_years']
            class_ultimates['trended_severity'] = class_ultimates['avg_severity'] * (1 + severity_trend) ** class_ultimates['trend_years']
            
            # Calculate trended loss cost
            class_ultimates['trended_loss_cost'] = class_ultimates['trended_frequency'] * class_ultimates['trended_severity']
            
            trended_results[class_id] = class_ultimates
        
        return trended_results
    
    def calculate_credibility(self, class_id, class_ultimates, all_class_ultimates):
        """
        Calculate credibility using limited fluctuation credibility theory
        Based on expected claim count
        """
        # Calculate total exposures and claims for the class
        total_exposures = class_ultimates['earned_exposures'].sum()
        total_claims = class_ultimates['reported_claim_count'].sum()
        
        # Credibility based on expected claim count (full credibility at 1082 claims for 5% with 90% confidence)
        # Z = sqrt(expected claims / 1082)
        full_credibility_claims = 1082  # Based on Poisson assumption for 5% tolerance with 90% confidence
        
        if total_claims >= full_credibility_claims:
            z = 1.0
        else:
            z = np.sqrt(total_claims / full_credibility_claims)
        
        # Cap at 1.0
        z = min(z, 1.0)
        
        return z
    
    def calculate_indicated_premium(self, class_id, variable_expense_ratio=0.24, 
                                     profit_contingency_ratio=0.05, fixed_expense_per_exposure=55,
                                     lae_ratio=0.1):
        """
        Calculate indicated premium per exposure for a specific class
        """
        # Get trended losses for this class
        trended_results = self.calculate_trended_losses()
        class_trended = trended_results[class_id]
        
        # Calculate all-class trended losses
        all_class_trended = pd.concat([trended_results[c] for c in self.classes], ignore_index=True)
        
        # Calculate average loss cost for class (weighted by exposures)
        total_exposures_class = class_trended['earned_exposures'].sum()
        total_trended_loss_class = (class_trended['trended_loss_cost'] * class_trended['earned_exposures']).sum()
        avg_loss_cost_class = total_trended_loss_class / total_exposures_class if total_exposures_class > 0 else 0
        
        # Calculate average loss cost for all classes combined
        total_exposures_all = all_class_trended['earned_exposures'].sum()
        total_trended_loss_all = (all_class_trended['trended_loss_cost'] * all_class_trended['earned_exposures']).sum()
        avg_loss_cost_all = total_trended_loss_all / total_exposures_all if total_exposures_all > 0 else 0
        
        # Calculate credibility
        z = self.calculate_credibility(class_id, class_trended, all_class_trended)
        
        # Credibility-weighted loss cost
        credible_loss_cost = z * avg_loss_cost_class + (1 - z) * avg_loss_cost_all
        
        # Add LAE
        loss_with_lae = credible_loss_cost * (1 + lae_ratio)
        
        # Calculate indicated premium using pure premium method
        # Premium = (Loss + LAE + Fixed Expenses) / (1 - Variable Expense Ratio - Profit/Contingency Ratio)
        indicated_premium = (loss_with_lae + fixed_expense_per_exposure) / (1 - variable_expense_ratio - profit_contingency_ratio)
        
        # Store results
        result = {
            'class_id': class_id,
            'class_description': self.df[self.df['class_id'] == class_id]['class_description'].iloc[0],
            'total_exposures': total_exposures_class,
            'total_claims': class_trended['reported_claim_count'].sum(),
            'avg_loss_cost_class': avg_loss_cost_class,
            'avg_loss_cost_all': avg_loss_cost_all,
            'credibility_z': z,
            'credible_loss_cost': credible_loss_cost,
            'loss_with_lae': loss_with_lae,
            'fixed_expense': fixed_expense_per_exposure,
            'variable_expense_ratio': variable_expense_ratio,
            'profit_contingency_ratio': profit_contingency_ratio,
            'indicated_premium_per_exposure': indicated_premium,
            'current_avg_premium': self.df[self.df['class_id'] == class_id]['current_avg_premium_per_exposure'].iloc[0],
            'indicated_change': (indicated_premium / self.df[self.df['class_id'] == class_id]['current_avg_premium_per_exposure'].iloc[0] - 1) * 100
        }
        
        self.indicated_premiums[class_id] = result
        return result
    
    def display_class_premium(self, class_id):
        """
        Display detailed premium indication for a selected class
        """
        if class_id not in self.indicated_premiums:
            result = self.calculate_indicated_premium(class_id)
        else:
            result = self.indicated_premiums[class_id]
        
        print("\n" + "="*80)
        print(f"PREMIUM INDICATION FOR CLASS {class_id}: {result['class_description']}")
        print("="*80)
        print(f"\nEXPERIENCE SUMMARY:")
        print(f"  Total Exposures (2020-2024): {result['total_exposures']:,.0f}")
        print(f"  Total Reported Claims: {result['total_claims']:,.0f}")
        print(f"  Average Claim Frequency: {result['total_claims']/result['total_exposures']:.4f}")
        
        print(f"\nLOSS COST CALCULATION:")
        print(f"  Class Average Loss Cost (trended): ${result['avg_loss_cost_class']:.2f}")
        print(f"  All-Class Average Loss Cost (trended): ${result['avg_loss_cost_all']:.2f}")
        print(f"  Credibility Factor (Z): {result['credibility_z']:.3f}")
        print(f"  Credibility-Weighted Loss Cost: ${result['credible_loss_cost']:.2f}")
        
        print(f"\nEXPENSE AND PROFIT LOADING:")
        print(f"  Loss & LAE (with {self.df['lae_provision_ratio_to_losses'].iloc[0]*100:.0f}% LAE): ${result['loss_with_lae']:.2f}")
        print(f"  Fixed Expense per Exposure: ${result['fixed_expense']:.2f}")
        print(f"  Variable Expense Ratio: {result['variable_expense_ratio']*100:.0f}%")
        print(f"  Profit & Contingency Ratio: {result['profit_contingency_ratio']*100:.0f}%")
        
        print(f"\nINDICATED PREMIUM:")
        print(f"  Indicated Premium per Exposure: ${result['indicated_premium_per_exposure']:.2f}")
        print(f"  Current Average Premium: ${result['current_avg_premium']:.2f}")
        print(f"  Indicated Change: {result['indicated_change']:.1f}%")
        
        print("\nRATE LEVEL INDICATION FORMULA:")
        print(f"  Premium = (Loss + LAE + Fixed) / (1 - Variable - Profit)")
        print(f"  = (${result['loss_with_lae']:.2f} + ${result['fixed_expense']:.2f}) / (1 - 0.24 - 0.05)")
        print(f"  = ${result['loss_with_lae'] + result['fixed_expense']:.2f} / 0.71")
        print(f"  = ${result['indicated_premium_per_exposure']:.2f}")
        
        return result
    
    def calculate_all_class_indications(self):
        """
        Calculate indications for all classes
        """
        print("\n" + "="*80)
        print("SUMMARY OF INDICATED PREMIUMS FOR ALL CLASSES")
        print("="*80)
        
        summary_data = []
        for class_id in self.classes:
            result = self.calculate_indicated_premium(class_id)
            summary_data.append({
                'Class': class_id,
                'Description': result['class_description'],
                'Current Premium': f"${result['current_avg_premium']:.2f}",
                'Indicated Premium': f"${result['indicated_premium_per_exposure']:.2f}",
                'Change': f"{result['indicated_change']:.1f}%",
                'Credibility': f"{result['credibility_z']:.3f}",
                'Class Loss Cost': f"${result['avg_loss_cost_class']:.2f}"
            })
        
        summary_df = pd.DataFrame(summary_data)
        print(summary_df.to_string(index=False))
        
        return summary_df

# Main execution
def main():
    """
    Main function to run the pricing engine
    """
    print("="*80)
    print("INSURANCE PRICING ENGINE - CLASS RATEMAKING")
    print("="*80)
    
    # Initialize the pricing engine
    engine = PricingEngine('classification_ratemaking_project_data.csv')
    
    # Calculate ultimate losses
    print("\nStep 1: Estimating ultimate losses using chain ladder method...")
    engine.estimate_ultimate_losses()
    
    # Display ultimate loss estimates
    print("\nUltimate Loss Estimates by Class and Accident Year:")
    for class_id in engine.classes:
        print(f"\nClass {class_id}:")
        ultimates = engine.ultimate_losses[class_id]
        for _, row in ultimates.iterrows():
            print(f"  AY {int(row['accident_year'])}: Latest Age {row['latest_age']} months, "
                  f"Ultimate Loss ${row['ultimate_loss']:,.0f}")
    
    print("\n" + "="*80)
    print("Step 2: Interactive Class Selection")
    print("="*80)
    print("\nAvailable Risk Classes:")
    for i, class_id in enumerate(engine.classes):
        desc = engine.df[engine.df['class_id'] == class_id]['class_description'].iloc[0]
        print(f"  {i+1}. Class {class_id}: {desc}")
    
    # Interactive selection
    while True:
        try:
            print("\n" + "-"*40)
            selection = input("Select a class by ID (A-F) or 'all' for summary, 'quit' to exit: ").strip().upper()
            
            if selection == 'QUIT':
                break
            elif selection == 'ALL':
                engine.calculate_all_class_indications()
            elif selection in engine.classes:
                engine.display_class_premium(selection)
            else:
                print("Invalid selection. Please choose a valid class ID (A-F), 'all', or 'quit'.")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()


# In[ ]:




