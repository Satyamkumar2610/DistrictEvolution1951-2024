import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Tree
import os

def build_tree_structure(state_name, df_changes):
    state_df = df_changes[df_changes['filter_state'] == state_name]
    
    adj_list = {}
    for _, row in state_df.iterrows():
        parent = row['source_district']
        child = row['dest_district']
        year = str(row['dest_year']) if pd.notna(row['dest_year']) else ""
        
        if parent not in adj_list:
            adj_list[parent] = []
        
        adj_list[parent].append({"name": child, "value": year})

    all_children = set(state_df['dest_district'])
    all_parents = set(adj_list.keys())
    roots = list(all_parents - all_children)
    
    if not roots:
        if all_parents:
            roots = list(all_parents)[:1]
        else:
            return []

    def get_children(node_name, visited):
        if node_name in visited:
             return {"name": f"{node_name} (Cycle)"}
        
        new_visited = visited | {node_name}
        
        node_data = {"name": node_name}
        children_list = adj_list.get(node_name, [])
        
        if children_list:
            children_data = []
            for child in children_list:
                children_data.append(get_children(child['name'], new_visited))
            node_data["children"] = children_data
            
        return node_data

    if len(roots) > 1:
        data = [{"name": state_name, "children": [get_children(root, set()) for root in roots]}]
    else:
        data = [get_children(roots[0], set())]
    
    return data

def generate_professional_chart(state_name, df_changes, output_dir):
    try:
        data = build_tree_structure(state_name, df_changes)
        if not data:
            print(f"Skipping {state_name}: No valid tree structure found.")
            return

        c = (
            Tree()
            .add(
                "",
                data,
                collapse_interval=2,
                layout="orthogonal",
                orient="LR",
                symbol="circle",
                symbol_size=8,
                itemstyle_opts=opts.ItemStyleOpts(
                    color="#006699",
                    border_color="#fff",
                    border_width=1.5
                ),
                label_opts=opts.LabelOpts(
                    position="right",
                    vertical_align="middle",
                    font_size=10,
                    font_family="Arial"
                ),
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title=f"District Lineage: {state_name}"),
                tooltip_opts=opts.TooltipOpts(trigger="item", formatter="{b}")
            )
        )
        
        output_path = os.path.join(output_dir, f"{state_name.replace(' ', '_')}_Lineage.html")
        c.render(output_path)
        print(f"Generated Professional Tree for: {state_name}")
        
    except Exception as e:
        print(f"Could not generate for {state_name} due to data complexity: {e}")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    transform_file = os.path.join(base_dir, 'data', 'processed', 'district_changes.csv')
    output_dir = os.path.join(base_dir, 'output', 'professional')
    
    if not os.path.exists(transform_file):
        print(f"Error: {transform_file} not found. Please run etl.py first.")
        return

    print("Loading data...")
    df = pd.read_csv(transform_file)
    
    if 'filter_state' not in df.columns:
        if 'state' in df.columns:
             df.rename(columns={'state': 'filter_state'}, inplace=True)
    
    states = df['filter_state'].dropna().unique()
    print(f"Found {len(states)} states. Generating charts...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for state in states:
        generate_professional_chart(state, df, output_dir)

if __name__ == "__main__":
    main()
