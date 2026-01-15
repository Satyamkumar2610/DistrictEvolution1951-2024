import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import os

def generate_static_visuals():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    transform_file = os.path.join(base_dir, 'data', 'processed', 'district_changes.csv')
    visuals_dir = os.path.join(base_dir, 'output', 'static')
    report_file = os.path.join(base_dir, 'output', 'reports', 'summary.md')
    
    if not os.path.exists(transform_file):
        print(f"Error: {transform_file} not found.")
        return

    print("Loading data...")
    df = pd.read_csv(transform_file)
    
    print("Generating visualizations...")
    states = df['filter_state'].unique()
    generated_states = []

    if not os.path.exists(visuals_dir):
        os.makedirs(visuals_dir)

    for state in states:
        print(f"Processing state: {state}")
        state_df = df[df['filter_state'] == state]
        
        G = nx.DiGraph()
        
        for _, row in state_df.iterrows():
            src = row['source_district']
            dst = row['dest_district']
            year = str(row['dest_year']) if pd.notna(row['dest_year']) else ""
            
            G.add_edge(src, dst, label=year)

        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G, seed=42, k=0.5)
        
        nx.draw(G, pos, with_labels=True, node_color='lightblue', 
                node_size=2000, font_size=8, font_weight='bold', 
                arrows=True, arrowsize=20)
        
        edge_labels = nx.get_edge_attributes(G, 'label')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
        
        plt.title(f"District Lineage - {state}")
        output_path = os.path.join(visuals_dir, f"{state}_lineage.png".replace(" ", "_"))
        plt.savefig(output_path)
        plt.close()
        generated_states.append(state)

    print("Creating report...")
    if not os.path.exists(os.path.dirname(report_file)):
        os.makedirs(os.path.dirname(report_file))

    with open(report_file, 'w') as f:
        f.write("# District Visualization Summary\n\n")
        f.write("Graphs were generated for the following states:\n\n")
        for state in sorted(generated_states):
            f.write(f"- {state}\n")
    
    print("Done!")

if __name__ == "__main__":
    generate_static_visuals()
