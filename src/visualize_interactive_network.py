import pandas as pd
from pyvis.network import Network
import os
import webbrowser

def create_interactive_graph(state_name, df, output_dir):
    state_df = df[df['filter_state'] == state_name].copy()
    
    if state_df.empty:
        print(f"No data found for state: {state_name}")
        return None

    # --- CONFIGURATION ---
    # Premium Colors
    COLOR_BG = "#ffffff"       # Clean white background for report style
    COLOR_NODE_ORIGIN = "#1f77b4"  # Muted Blue
    COLOR_NODE_NEW = "#ff7f0e"     # Safety Orange
    COLOR_EDGE = "#bdc3c7"         # Silver
    COLOR_TEXT = "#333333"         # Dark Grey

    net = Network(height='600px', width='100%', bgcolor=COLOR_BG, font_color=COLOR_TEXT, directed=True)
    
    # Use Hierarchical Layout for "Lineage" feel
    net.hrepulsion(node_distance=150, central_gravity=0.0, spring_length=150, spring_strength=0.05, damping=0.09)
    # The 'layout' option in set_options is key for hierarchy
    options = """
    var options = {
      "nodes": {
        "borderWidth": 2,
        "shadow": true,
        "font": {
            "size": 16,
            "face": "Segoe UI, Roboto, Helvetica, Arial, sans-serif"
        }
      },
      "edges": {
        "color": {
            "color": "#bdc3c7",
            "highlight": "#2c3e50"
        },
        "smooth": {
            "type": "cubicBezier",
            "forceDirection": "vertical",
            "roundness": 0.4
        },
        "arrows": {
            "to": {
                "enabled": true,
                "scaleFactor": 1
            }
        }
      },
      "layout": {
        "hierarchical": {
          "enabled": true,
          "levelSeparation": 150,
          "nodeSpacing": 200,
          "treeSpacing": 200,
          "blockShifting": true,
          "edgeMinimization": true,
          "parentCentralization": true,
          "direction": "UD",        
          "sortMethod": "directed"  
        }
      },
      "interaction": {
        "navigationButtons": true,
        "zoomView": true,
        "dragView": true
      },
      "physics": {
        "hierarchicalRepulsion": {
          "centralGravity": 0,
          "springLength": 100,
          "springConstant": 0.01,
          "nodeDistance": 120,
          "damping": 0.09
        },
        "solver": "hierarchicalRepulsion",
        "stabilization": {
           "enabled": true,
           "iterations": 1000
        }
      }
    }
    """
    net.set_options(options)
    
    district_info = {}
    
    # Pre-process nodes to determine "levels" if manually needed, 
    # but PyVis hierarchical layout handles this with 'directed' sortMethod usually.
    
    for _, row in state_df.iterrows():
        src = row['source_district']
        dst = row['dest_district']
        year = str(row['dest_year']) if pd.notna(row['dest_year']) else "Unknown"
        
        if dst not in district_info:
            district_info[dst] = {'year': year, 'parent': src, 'type': 'new'}
        
        if src not in district_info:
            district_info[src] = {'year': 'Pre-existing or Unknown', 'parent': '-', 'type': 'origin'}

    for district, info in district_info.items():
        is_origin = info['type'] == 'origin'
        
        # Tooltip with HTML
        title_html = (
            f"<div style='background: white; padding: 8px; border-radius: 4px; border: 1px solid #ccc;'>"
            f"<b style='font-size: 14px; color: #333;'>{district}</b><br><hr style='margin: 4px 0;'>"
            f"<b>Formed:</b> {info['year']}<br>"
            f"<b>Parent:</b> {info['parent']}"
            f"</div>"
        )
        
        # Visual style
        color = COLOR_NODE_ORIGIN if is_origin else COLOR_NODE_NEW
        size = 25 if is_origin else 20
        
        net.add_node(
            district, 
            label=district, 
            title=title_html, 
            color=color,
            size=size
        )

    for _, row in state_df.iterrows():
        src = row['source_district']
        dst = row['dest_district']
        yr = str(int(row['dest_year'])) if pd.notna(row['dest_year']) else "?"
        net.add_edge(src, dst, label=str(yr)) # Label on edge can be year

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
