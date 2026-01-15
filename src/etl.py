import pandas as pd
import os

def process_district_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, 'data', 'raw', 'district_proliferation_1951_2024.xlsx')
    transform_output = os.path.join(base_dir, 'data', 'processed', 'district_changes.csv')

    print(f"Reading {input_file}...")
    try:
        df = pd.read_excel(input_file)
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        return

    df.columns = df.columns.str.strip()
    
    print("Filtering data...")
    str_cols = ['source_district', 'dest_district', 'filter_state']
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            
    filtered_df = df[df['source_district'] != df['dest_district']].copy()
    
    print(f"Saving transformed data to {transform_output}...")
    filtered_df.to_csv(transform_output, index=False)
    return True

if __name__ == "__main__":
    process_district_data()
