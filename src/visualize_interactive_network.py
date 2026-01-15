import pandas as pd
from pyvis.network import Network
import os
import webbrowser

def create_interactive_graph(state_name, df, output_dir):
    state_df = df[df['filter_state'] == state_name].copy()
    
    if state_df.empty:
        print(f"No data found for state: {state_name}")
        return None

    net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', directed=True)
    
    district_info = {}
    
    for _, row in state_df.iterrows():
        src = row['source_district']
        dst = row['dest_district']
        year = str(row['dest_year']) if pd.notna(row['dest_year']) else "Unknown"
        
        if dst not in district_info:
            district_info[dst] = {'year': year, 'parent': src}
        
        if src not in district_info:
            district_info[src] = {'year': 'Pre-existing or Unknown', 'parent': '-'}

    for district, info in district_info.items():
        title_html = (
            f"<b>District:</b> {district}<br>"
            f"<b>Year Created:</b> {info['year']}<br>"
            f"<b>Parent District:</b> {info['parent']}"
        )
        net.add_node(district, label=district, title=title_html, color='#4caf50' if info['year'] != 'Pre-existing or Unknown' else '#ff9800')

    for _, row in state_df.iterrows():
        src = row['source_district']
        dst = row['dest_district']
        net.add_edge(src, dst, title=f"Split in {row['dest_year']}")

    output_filename = f"{state_name.replace(' ', '_')}_interactive.html"
    output_path = os.path.join(output_dir, output_filename)
    
    net.write_html(output_path)
    print(f"Graph generated: {output_path}")
    return output_path

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    transform_file = os.path.join(base_dir, 'data', 'processed', 'district_changes.csv')
    visuals_dir = os.path.join(base_dir, 'output', 'interactive')
    
    if not os.path.exists(transform_file):
        print(f"Error: {transform_file} not found. Please run etl.py first.")
        return

    print("Loading data...")
    try:
        df = pd.read_csv(transform_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if 'filter_state' not in df.columns:
        if 'state' in df.columns:
             df.rename(columns={'state': 'filter_state'}, inplace=True)
        else:
             print("Error: 'filter_state' column not found in data.")
             return

    unique_states = sorted(df['filter_state'].dropna().unique())

    print("Generating graphs for ALL states...")
    
    if not os.path.exists(visuals_dir):
        os.makedirs(visuals_dir)
        
    for state in unique_states:
        create_interactive_graph(state, df, visuals_dir)
    print(f"All graphs generated in {visuals_dir}")

if __name__ == "__main__":
    main()
