import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import os
import sys

def generate_plotly_graph(state_name, df, save_dir=None):
    state_df = df[df['filter_state'] == state_name].copy()
    
    if state_df.empty:
        print(f"No data found for state: {state_name}")
        return

    G = nx.DiGraph()
    district_years = {}
    
    def parse_year(val):
        try:
            return int(float(str(val)))
        except:
            return None

    for _, row in state_df.iterrows():
        src = row['source_district']
        dst = row['dest_district']
        year_val = parse_year(row['dest_year'])
        
        G.add_edge(src, dst)
        
        if year_val:
            district_years[dst] = year_val
            
    known_years = [y for y in district_years.values() if y is not None]
    base_year = min(known_years) - 5 if known_years else 1950
    
    for node in G.nodes():
        if node not in district_years:
            district_years[node] = base_year

    if len(G.nodes) == 0:
        print("Graph has no nodes.")
        return

    pos = {}
    nodes_by_year = {}
    for node, year in district_years.items():
        if year not in nodes_by_year:
            nodes_by_year[year] = []
        nodes_by_year[year].append(node)
        
    sorted_years = sorted(nodes_by_year.keys())
    
    for year in sorted_years:
        nodes = nodes_by_year[year]
        nodes.sort()
        count = len(nodes)
        
        if count == 1:
            ys = [0]
        else:
            ys = [i - (count - 1) / 2 for i in range(count)]
            
        for node, y in zip(nodes, ys):
            pos[node] = (year, y)

    edge_x = []
    edge_y = []
    
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines')

    node_x = []
    node_y = []
    node_text = []
    node_color_values = []
    
    degrees = dict(G.degree)
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        year = district_years.get(node, "Unknown")
        parents = list(G.predecessors(node))
        
        info = (f"<b>{node}</b><br>"
                f"Formed: {year}<br>"
                f"Parent: {', '.join(parents) if parents else 'Original'}")
        
        node_text.append(info)
        node_color_values.append(year)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            showscale=True,
            colorscale='Viridis',
            reversescale=False,
            color=node_color_values,
            size=25,
            colorbar=dict(
                thickness=15,
                title=dict(
                    text='Year of Formation',
                    side='right'
                ),
                xanchor='left'
            ),
            line_width=1,
            line_color='white'))
            
    node_trace.text = node_text

    fig = go.Figure(data=[edge_trace, node_trace],
                layout=go.Layout(
                    title=dict(
                        text=f'District Evolution Timeline - {state_name}',
                        font=dict(size=20, family="Arial")
                    ),
                    showlegend=False,
                    hovermode='closest',
                    plot_bgcolor='white',
                    margin=dict(b=40,l=40,r=40,t=60),
                    xaxis=dict(
                        showgrid=True, 
                        gridcolor='#eee',
                        zeroline=False, 
                        showticklabels=True,
                        title="Year"
                    ),
                    yaxis=dict(
                        showgrid=False, 
                        zeroline=False, 
                        showticklabels=False,
                        visible=False
                    ))
                )
    
    if save_dir:
        output_path = os.path.join(save_dir, f"{state_name.replace(' ', '_')}_Timeline.html")
        fig.write_html(output_path)
        print(f"Saved: {output_path}")
    else:
        print(f"Opening Plotly graph for {state_name}...")
        fig.show()

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
        print(f"Error reading SCV: {e}")
        return

    if 'filter_state' not in df.columns:
         if 'state' in df.columns:
             df.rename(columns={'state': 'filter_state'}, inplace=True)
         else:
             print("Error: Could not find state column.")
             return

    unique_states = sorted(df['filter_state'].dropna().unique())
    
    print("\nStarting Batch Process for All States...")
    if not os.path.exists(visuals_dir):
        os.makedirs(visuals_dir)

    for state in unique_states:
        generate_plotly_graph(state, df, save_dir=visuals_dir)
    print(f"All graphs saved to {visuals_dir}")

if __name__ == "__main__":
    main()
