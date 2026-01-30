#!/usr/bin/env python
# coding: utf-8

# In[ ]:


def calculate_workers_comp():
    # 1. Rating Manual Data (Werner & Modlin Chapter 2)
    CLASS_RATES = {
        "8810": 0.49,  # Clerical
        "8825": 2.77,  # Food Service
        "8824": 3.99   # Health Care
    }
    
    # Rating constants from the manual
    EXP_MOD = 0.95        
    SCHEDULE_MOD = 0.90   
    DISCOUNT_MOD = 0.95   
    EXPENSE_CONSTANT = 250.00
    
    # Using a while loop to keep the calculator running
    while True:
        print("\n" + "="*45)
        print("   WORKERS' COMPENSATION RATE CALCULATOR")
        print("="*45)
        print(f"Available Class Codes: {', '.join(CLASS_RATES.keys())}")
        print("Type 'QUIT' at any prompt to exit.")
        print("-" * 45)
        
        try:
            # 1. Class Code Input
            code = input("Enter Class Code: ").strip().upper()
            if code == 'QUIT':
                break
            if code not in CLASS_RATES:
                print(f">> ERROR: '{code}' is not a valid class code. Please try again.")
                continue  # Returns to the start of the loop
            
            # 2. Payroll Input
            payroll_in = input("Enter Annual Payroll (Total $): ").strip().upper()
            if payroll_in == 'QUIT':
                break
            
            payroll = float(payroll_in)
            if payroll <= 0:
                print(">> ERROR: Payroll must be a positive amount.")
                continue

            # 3. Calculation Logic (Fundamental Insurance Equation)
            rate = CLASS_RATES[code]
            manual_premium = (payroll / 100) * rate
            modified_premium = manual_premium * EXP_MOD
            standard_premium = modified_premium * SCHEDULE_MOD
            net_premium = (standard_premium * DISCOUNT_MOD) + EXPENSE_CONSTANT
            
            # 4. Display Results
            print("\n--- RATING CALCULATION COMPLETED ---")
            print(f"Class Selected:    {code}")
            print(f"Manual Premium:    ${manual_premium:,.2f}")
            print(f"Standard Premium:  ${standard_premium:,.2f}")
            print(f"NET PREMIUM DUE:   ${net_premium:,.2f}")
            print("-" * 45)
            
            # 5. Loop Reset Prompt
            repeat = input("Perform another calculation? (Y/N): ").strip().upper()
            if repeat != 'Y':
                break

        except ValueError:
            print(">> ERROR: Invalid numeric input. Please enter numbers only for payroll.")
        except Exception as e:
            print(f">> AN UNEXPECTED ERROR OCCURRED: {e}")

    print("\nCalculator closed. Final rates logged.")

if __name__ == "__main__":
    calculate_workers_comp()

