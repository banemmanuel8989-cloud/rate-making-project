#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Set page configuration
st.set_page_config(
    page_title="Insurance Pricing Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #424242;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
    }
    .highlight {
        background-color: #e3f2fd;
        padding: 0.5rem;
        border-radius: 5px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

class PricingEngine:
    def __init__(self, data):
        """
        Initialize the pricing engine with data
        """
        self.df = data.copy()
        self.classes = sorted(self.df['class_id'].unique())
        self.tail_factor = 1.02  # Selected tail factor (2% development beyond 60 months)
        
        # Store results
        self.ultimate_losses = {}
        self.loss_development_factors = {}
        self.development_triangles = {}
        
    def create_development_triangles(self, loss_type='paid'):
        """
        Create loss development triangles for each class
        """
        triangles = {}
        
        for class_id in self.classes:
            class_data = self.df[self.df['class_id'] == class_id].sort_values('accident_year')
            
            # Create development triangle
            triangle_data = []
            for _, row in class_data.iterrows():
                accident_year = row['accident_year']
                row_data = {'Accident Year': accident_year}
                
                # Add losses at each development age
                for age in [12, 24, 36, 48, 60]:
                    col_name = f'{loss_type}_loss_{age}'
                    if col_name in row and not pd.isna(row[col_name]):
                        row_data[f'{age} months'] = row[col_name]
                    else:
                        row_data[f'{age} months'] = np.nan
                
                triangle_data.append(row_data)
            
            triangles[class_id] = pd.DataFrame(triangle_data)
        
        return triangles
    
    def calculate_age_to_age_factors(self, loss_type='paid'):
        """
        Calculate age-to-age factors using chain ladder method
        """
        triangles = self.create_development_triangles(loss_type)
        ldfs = {}
        factor_details = {}
        
        for class_id, triangle in triangles.items():
            # Sort by accident year
            triangle = triangle.sort_values('Accident Year')
            
            # Calculate age-to-age factors
            ages = [12, 24, 36, 48, 60]
            factors = []
            factor_matrix = []
            
            for i in range(len(ages) - 1):
                current_age = f'{ages[i]} months'
                next_age = f'{ages[i+1]} months'
                
                # Get values for current and next age
                current_values = triangle[current_age].values
                next_values = triangle[next_age].values
                
                # Calculate factors where both values exist
                valid_pairs = []
                for j in range(len(current_values) - 1):  # -1 because next year needed
                    if not pd.isna(current_values[j]) and not pd.isna(next_values[j]):
                        factor = next_values[j] / current_values[j]
                        valid_pairs.append(factor)
                        factor_matrix.append({
                            'Class': class_id,
                            'From Age': ages[i],
                            'To Age': ages[i+1],
                            'Accident Year': triangle.iloc[j]['Accident Year'],
                            'Factor': factor
                        })
                
                # Use arithmetic average
                if valid_pairs:
                    avg_factor = np.mean(valid_pairs)
                    factors.append(avg_factor)
                else:
                    factors.append(np.nan)
            
            ldfs[class_id] = factors
            factor_details[class_id] = pd.DataFrame(factor_matrix) if factor_matrix else pd.DataFrame()
        
        return ldfs, factor_details, triangles
    
    def estimate_ultimate_losses(self):
        """
        Estimate ultimate losses for each class and accident year
        """
        # Calculate factors for both paid and incurred
        paid_factors, paid_factor_details, paid_triangles = self.calculate_age_to_age_factors('paid')
        incurred_factors, incurred_factor_details, incurred_triangles = self.calculate_age_to_age_factors('incurred')
        
        self.loss_development_factors = {
            'paid': paid_factors,
            'incurred': incurred_factors,
            'paid_details': paid_factor_details,
            'incurred_details': incurred_factor_details
        }
        
        self.development_triangles = {
            'paid': paid_triangles,
            'incurred': incurred_triangles
        }
        
        for class_id in self.classes:
            class_data = self.df[self.df['class_id'] == class_id].copy()
            class_ultimates = []
            
            for idx, row in class_data.iterrows():
                accident_year = row['accident_year']
                
                # Get latest paid and incurred values based on available age
                latest_age = row['paid_age_available_months']
                latest_paid = row[f'paid_loss_{latest_age}']
                latest_incurred = row[f'incurred_loss_{latest_age}']
                
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
                    
                    # Project ultimate loss
                    paid_ultimate = latest_paid * cum_factor if latest_paid else np.nan
                    incurred_ultimate = latest_incurred * cum_factor if latest_incurred else np.nan
                    
                    # Use the more conservative estimate
                    if not pd.isna(incurred_ultimate) and not pd.isna(paid_ultimate):
                        ultimate = max(paid_ultimate, incurred_ultimate)
                    elif not pd.isna(incurred_ultimate):
                        ultimate = incurred_ultimate
                    else:
                        ultimate = paid_ultimate
                    
                    # Calculate loss ratio
                    loss_ratio = ultimate / row['earned_premium'] if row['earned_premium'] > 0 else np.nan
                    
                    class_ultimates.append({
                        'class_id': class_id,
                        'accident_year': accident_year,
                        'latest_paid': latest_paid,
                        'latest_incurred': latest_incurred,
                        'latest_age': latest_age,
                        'ultimate_loss': ultimate,
                        'earned_exposures': row['earned_exposures'],
                        'earned_premium': row['earned_premium'],
                        'reported_claim_count': row['reported_claim_count'],
                        'loss_ratio': loss_ratio
                    })
            
            self.ultimate_losses[class_id] = pd.DataFrame(class_ultimates)
        
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
            
            # Calculate frequency and severity
            class_ultimates['frequency'] = class_ultimates['reported_claim_count'] / class_ultimates['earned_exposures']
            class_ultimates['avg_severity'] = class_ultimates['ultimate_loss'] / class_ultimates['reported_claim_count']
            
            # Project frequency and severity
            class_ultimates['trended_frequency'] = class_ultimates['frequency'] * (1 + trend_rate) ** class_ultimates['trend_years']
            class_ultimates['trended_severity'] = class_ultimates['avg_severity'] * (1 + severity_trend) ** class_ultimates['trend_years']
            
            # Calculate trended loss cost
            class_ultimates['trended_loss_cost'] = class_ultimates['trended_frequency'] * class_ultimates['trended_severity']
            
            trended_results[class_id] = class_ultimates
        
        return trended_results
    
    def calculate_credibility(self, class_id, class_ultimates):
        """
        Calculate credibility using limited fluctuation credibility theory
        """
        total_claims = class_ultimates['reported_claim_count'].sum()
        
        # Full credibility at 1082 claims (5% tolerance with 90% confidence)
        full_credibility_claims = 1082
        
        if total_claims >= full_credibility_claims:
            z = 1.0
        else:
            z = np.sqrt(total_claims / full_credibility_claims)
        
        # Cap at 1.0
        z = min(z, 1.0)
        
        return z, total_claims
    
    def calculate_indicated_premium(self, class_id, variable_expense_ratio=0.24, 
                                     profit_contingency_ratio=0.05, fixed_expense_per_exposure=55,
                                     lae_ratio=0.1, policy_year=2026):
        """
        Calculate indicated premium per exposure for a specific class
        """
        # Get trended losses for this class
        trended_results = self.calculate_trended_losses(policy_year_start=policy_year, policy_year_end=policy_year)
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
        z, total_claims = self.calculate_credibility(class_id, class_trended)
        
        # Credibility-weighted loss cost
        credible_loss_cost = z * avg_loss_cost_class + (1 - z) * avg_loss_cost_all
        
        # Add LAE
        loss_with_lae = credible_loss_cost * (1 + lae_ratio)
        
        # Calculate indicated premium using pure premium method
        indicated_premium = (loss_with_lae + fixed_expense_per_exposure) / (1 - variable_expense_ratio - profit_contingency_ratio)
        
        # Get current premium
        current_premium = self.df[self.df['class_id'] == class_id]['current_avg_premium_per_exposure'].iloc[0]
        
        # Calculate premium trend (if needed for on-level factor)
        premium_trend = (1 + 0.02) ** (policy_year - 2024)  # Assuming 2% annual premium trend
        
        # Store results
        result = {
            'class_id': class_id,
            'class_description': self.df[self.df['class_id'] == class_id]['class_description'].iloc[0],
            'total_exposures': total_exposures_class,
            'total_claims': total_claims,
            'avg_loss_cost_class': avg_loss_cost_class,
            'avg_loss_cost_all': avg_loss_cost_all,
            'credibility_z': z,
            'credible_loss_cost': credible_loss_cost,
            'loss_with_lae': loss_with_lae,
            'fixed_expense': fixed_expense_per_exposure,
            'variable_expense_ratio': variable_expense_ratio,
            'profit_contingency_ratio': profit_contingency_ratio,
            'indicated_premium_per_exposure': indicated_premium,
            'current_avg_premium': current_premium,
            'indicated_change': (indicated_premium / current_premium - 1) * 100,
            'on_level_premium': current_premium * premium_trend,
            'policy_year': policy_year
        }
        
        return result

# Load and prepare data
@st.cache_data
def load_data():
    """Load and prepare the data"""
    data = pd.read_csv('classification_ratemaking_project_data.csv')
    return data

def main():
    # Header
    st.markdown('<h1 class="main-header">📊 Insurance Pricing Engine</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Class Ratemaking with Loss Development Triangles</p>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner('Loading data...'):
        data = load_data()
    
    # Initialize engine
    engine = PricingEngine(data)
    
    # Calculate ultimate losses
    with st.spinner('Calculating ultimate losses...'):
        engine.estimate_ultimate_losses()
    
    # Sidebar for inputs
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/insurance--v1.png", width=100)
        st.markdown("## ⚙️ Parameters")
        
        # Class selection
        selected_class = st.selectbox(
            "Select Risk Class",
            options=engine.classes,
            format_func=lambda x: f"Class {x} - {data[data['class_id']==x]['class_description'].iloc[0]}"
        )
        
        st.markdown("---")
        
        # Policy year
        policy_year = st.number_input("Policy Year", min_value=2026, max_value=2027, value=2026)
        
        st.markdown("---")
        st.markdown("### 📈 Trend Assumptions")
        frequency_trend = st.number_input("Annual Frequency Trend", value=0.012, format="%.3f")
        severity_trend = st.number_input("Annual Severity Trend", value=0.055, format="%.3f")
        
        st.markdown("---")
        st.markdown("### 💰 Expense Parameters")
        lae_ratio = st.number_input("LAE Ratio to Losses", value=0.10, format="%.2f")
        variable_expense = st.number_input("Variable Expense Ratio", value=0.24, format="%.2f")
        fixed_expense = st.number_input("Fixed Expense per Exposure", value=55.0, format="%.2f")
        profit_ratio = st.number_input("Profit & Contingency Ratio", value=0.05, format="%.2f")
        
        st.markdown("---")
        st.markdown("### 🔧 Development Parameters")
        tail_factor = st.number_input("Tail Factor", value=1.02, format="%.3f")
        engine.tail_factor = tail_factor
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Premium Indication", 
        "📊 Loss Development Triangles", 
        "📈 Age-to-Age Factors",
        "📉 Ultimate Loss Estimates",
        "📑 Summary All Classes"
    ])
    
    with tab1:
        st.markdown(f"## Premium Indication for Class {selected_class}")
        
        # Calculate indication
        result = engine.calculate_indicated_premium(
            selected_class,
            variable_expense_ratio=variable_expense,
            profit_contingency_ratio=profit_ratio,
            fixed_expense_per_exposure=fixed_expense,
            lae_ratio=lae_ratio,
            policy_year=policy_year
        )
        
        # Display key metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Indicated Premium",
                f"${result['indicated_premium_per_exposure']:.2f}",
                delta=f"{result['indicated_change']:.1f}%"
            )
        
        with col2:
            st.metric("Current Premium", f"${result['current_avg_premium']:.2f}")
        
        with col3:
            st.metric("Credibility", f"{result['credibility_z']:.3f}")
        
        with col4:
            st.metric("Total Claims", f"{result['total_claims']:,.0f}")
        
        # Detailed calculation
        st.markdown("### 📝 Detailed Calculation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Loss Cost Development")
            loss_data = pd.DataFrame({
                'Component': ['Class Loss Cost', 'All-Class Loss Cost', 'Credibility Z', 'Credible Loss Cost'],
                'Value': [
                    f"${result['avg_loss_cost_class']:.2f}",
                    f"${result['avg_loss_cost_all']:.2f}",
                    f"{result['credibility_z']:.3f}",
                    f"${result['credible_loss_cost']:.2f}"
                ]
            })
            st.dataframe(loss_data, use_container_width=True)
        
        with col2:
            st.markdown("#### Premium Build-up")
            premium_data = pd.DataFrame({
                'Component': ['Loss + LAE', 'Fixed Expense', 'Variable Expense', 'Profit', 'Final Premium'],
                'Value': [
                    f"${result['loss_with_lae']:.2f}",
                    f"${result['fixed_expense']:.2f}",
                    f"{result['variable_expense_ratio']*100:.0f}%",
                    f"{result['profit_contingency_ratio']*100:.0f}%",
                    f"${result['indicated_premium_per_exposure']:.2f}"
                ]
            })
            st.dataframe(premium_data, use_container_width=True)
        
        # Formula
        st.markdown("#### 🧮 Rate Formula")
        st.latex(rf"Premium = \frac{{{result['loss_with_lae']:.2f} + {result['fixed_expense']:.2f}}}{{1 - 0.24 - 0.05}} = {result['indicated_premium_per_exposure']:.2f}")
        
        # Historical loss ratios
        st.markdown("### 📊 Historical Loss Ratios by Accident Year")
        class_ultimates = engine.ultimate_losses[selected_class]
        
        fig = px.bar(
            class_ultimates,
            x='accident_year',
            y='loss_ratio',
            title=f'Loss Ratios - Class {selected_class}',
            labels={'accident_year': 'Accident Year', 'loss_ratio': 'Loss Ratio'},
            color='loss_ratio',
            color_continuous_scale='RdYlGn_r'
        )
        fig.add_hline(y=0.7, line_dash="dash", line_color="red", annotation_text="Target 70%")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.markdown("## Loss Development Triangles")
        
        triangle_type = st.radio("Select Triangle Type", ['Paid Losses', 'Incurred Losses'], horizontal=True)
        loss_type = 'paid' if triangle_type == 'Paid Losses' else 'incurred'
        
        # Get triangles
        triangles = engine.development_triangles[loss_type]
        
        # Display triangle for selected class
        st.markdown(f"### {triangle_type} Triangle - Class {selected_class}")
        
        if selected_class in triangles:
            triangle_df = triangles[selected_class].copy()
            
            # Format for display
            display_df = triangle_df.round(0).astype(str)
            for col in display_df.columns:
                if col != 'Accident Year':
                    display_df[col] = display_df[col].str.replace('nan', '--')
            
            st.dataframe(display_df, use_container_width=True)
            
            # Heatmap visualization
            st.markdown("### 🔥 Development Heatmap")
            
            # Prepare data for heatmap
            heatmap_data = triangle_df.set_index('Accident Year')
            heatmap_data = heatmap_data.apply(pd.to_numeric, errors='coerce')
            
            fig = go.Figure(data=go.Heatmap(
                z=heatmap_data.values,
                x=heatmap_data.columns,
                y=heatmap_data.index,
                colorscale='Viridis',
                text=heatmap_data.values.round(0),
                texttemplate='%{text:,.0f}',
                textfont={"size": 10},
                hoverongaps=False
            ))
            
            fig.update_layout(
                title=f'{triangle_type} Development - Class {selected_class}',
                xaxis_title='Development Age',
                yaxis_title='Accident Year',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.markdown("## Age-to-Age Development Factors")
        
        factor_type = st.radio("Select Factor Type", ['Paid Factors', 'Incurred Factors'], horizontal=True)
        factor_key = 'paid' if factor_type == 'Paid Factors' else 'incurred'
        
        # Display factor details
        st.markdown(f"### {factor_type} - Class {selected_class}")
        
        if selected_class in engine.loss_development_factors[f'{factor_key}_details']:
            factor_df = engine.loss_development_factors[f'{factor_key}_details'][selected_class]
            
            if not factor_df.empty:
                # Calculate averages
                avg_factors = factor_df.groupby(['From Age', 'To Age'])['Factor'].agg(['mean', 'count']).reset_index()
                avg_factors.columns = ['From Age', 'To Age', 'Average Factor', 'Number of Observations']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Individual Factors by Year")
                    st.dataframe(factor_df, use_container_width=True)
                
                with col2:
                    st.markdown("#### Average Factors")
                    st.dataframe(avg_factors, use_container_width=True)
                
                # Visualization
                fig = px.box(
                    factor_df,
                    x='To Age',
                    y='Factor',
                    color='From Age',
                    title=f'{factor_type} Distribution by Development Interval',
                    points='all'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No factor data available for this class")
    
    with tab4:
        st.markdown("## Ultimate Loss Estimates")
        
        # Display ultimate losses for selected class
        st.markdown(f"### Ultimate Losses - Class {selected_class}")
        
        if selected_class in engine.ultimate_losses:
            ultimates_df = engine.ultimate_losses[selected_class].copy()
            
            # Format for display
            display_ultimates = ultimates_df[['accident_year', 'latest_age', 'ultimate_loss', 'loss_ratio']].copy()
            display_ultimates['ultimate_loss'] = display_ultimates['ultimate_loss'].apply(lambda x: f"${x:,.0f}")
            display_ultimates['loss_ratio'] = display_ultimates['loss_ratio'].apply(lambda x: f"{x:.1%}")
            
            st.dataframe(display_ultimates, use_container_width=True)
            
            # Chart of ultimate losses
            fig = px.line(
                ultimates_df,
                x='accident_year',
                y='ultimate_loss',
                title='Ultimate Loss Trend',
                markers=True
            )
            fig.update_layout(yaxis_title='Ultimate Loss ($)', xaxis_title='Accident Year')
            st.plotly_chart(fig, use_container_width=True)
            
            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Ultimate Loss", f"${ultimates_df['ultimate_loss'].sum():,.0f}")
            with col2:
                st.metric("Average Loss Ratio", f"{ultimates_df['loss_ratio'].mean():.1%}")
            with col3:
                st.metric("Total Earned Premium", f"${ultimates_df['earned_premium'].sum():,.0f}")
    
    with tab5:
        st.markdown("## Summary - All Classes")
        
        # Calculate indications for all classes
        all_results = []
        for class_id in engine.classes:
            result = engine.calculate_indicated_premium(
                class_id,
                variable_expense_ratio=variable_expense,
                profit_contingency_ratio=profit_ratio,
                fixed_expense_per_exposure=fixed_expense,
                lae_ratio=lae_ratio,
                policy_year=policy_year
            )
            all_results.append(result)
        
        summary_df = pd.DataFrame(all_results)
        
        # Display summary table
        display_summary = summary_df[[
            'class_id', 'class_description', 'current_avg_premium', 
            'indicated_premium_per_exposure', 'indicated_change', 
            'credibility_z', 'total_claims'
        ]].copy()
        
        display_summary['current_avg_premium'] = display_summary['current_avg_premium'].apply(lambda x: f"${x:.2f}")
        display_summary['indicated_premium_per_exposure'] = display_summary['indicated_premium_per_exposure'].apply(lambda x: f"${x:.2f}")
        display_summary['indicated_change'] = display_summary['indicated_change'].apply(lambda x: f"{x:.1f}%")
        display_summary['credibility_z'] = display_summary['credibility_z'].apply(lambda x: f"{x:.3f}")
        
        st.dataframe(display_summary, use_container_width=True)
        
        # Comparison chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Current Premium',
            x=summary_df['class_id'],
            y=summary_df['current_avg_premium'],
            marker_color='lightblue'
        ))
        fig.add_trace(go.Bar(
            name='Indicated Premium',
            x=summary_df['class_id'],
            y=summary_df['indicated_premium_per_exposure'],
            marker_color='coral'
        ))
        
        fig.update_layout(
            title='Current vs Indicated Premium by Class',
            xaxis_title='Class',
            yaxis_title='Premium per Exposure ($)',
            barmode='group',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Download button for summary
        csv = summary_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Summary CSV",
            data=csv,
            file_name=f"premium_indications_{policy_year}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()


# In[ ]:





# In[ ]:




