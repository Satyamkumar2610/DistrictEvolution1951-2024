import os
import sys

def main():
    print("Starting District Evolution Pipeline...")
    
    print("\n[1/5] Running ETL...")
    exit_code = os.system(f"{sys.executable} src/etl.py")
    if exit_code != 0:
        print("ETL failed. Exiting.")
        return

    print("\n[2/5] Generating Static Visuals...")
    os.system(f"{sys.executable} src/visualize_static.py")

    print("\n[3/5] Generating Interactive Network Graphs...")
    os.system(f"{sys.executable} src/visualize_interactive_network.py")
    
    print("\n[4/5] Generating Interactive Timelines...")
    os.system(f"{sys.executable} src/visualize_interactive_timeline.py")
    
    print("\n[5/5] Generating Professional Trees...")
    os.system(f"{sys.executable} src/visualize_professional_tree.py")
    
    print("\nPipeline Complete!")

if __name__ == "__main__":
    main()
