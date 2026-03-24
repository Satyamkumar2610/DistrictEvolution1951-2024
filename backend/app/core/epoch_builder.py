from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Tuple, Optional, Set
from dataclasses import dataclass

if TYPE_CHECKING:
    from app.core.lineage_graph import LineageGraph

@dataclass
class Epoch:
    epoch_num: int
    year_start: int
    year_end: Optional[int]
    event_label: str
    active_cdks: List[str]
    leaf_cdks: List[str]
    is_virtual: bool


def build_epochs_from_graph(
    root_cdk: str,
    graph: LineageGraph,
    min_year: int = 1950,
) -> List[Epoch]:
    """
    Build epochs from a LineageGraph instance.

    Extracts the compatibility split_graph dict from the DAG and
    delegates to the core build_epochs() logic. This is the preferred
    entry point when a LineageGraph is already available.
    """
    compat_graph = graph.get_split_graph_compat()
    return build_epochs(root_cdk, compat_graph, min_year=min_year)


def build_epochs(
    root_cdk: str,
    split_graph: Dict[str, List[Tuple[List[str], int]]],
    min_year: int = 1950
) -> List[Epoch]:
    """
    Reverse-engineers a chronological list of epochs for a district's lineage.
    
    split_graph: { parent_cdk: [ ( [child1, child2], split_year ), ... ] }
    """
    
    # 1. Discover all splits in the subtree via BFS to gather split years
    # and to recursively find all leaf CDKs.
    queue = [root_cdk]
    all_splits: List[Tuple[str, List[str], int]] = []
    
    leaf_cdks: Set[str] = set()
    visited: Set[str] = set()
    
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        
        splits = split_graph.get(curr, [])
        if not splits:
            leaf_cdks.add(curr)
        else:
            for children, s_year in splits:
                all_splits.append((curr, children, s_year))
                queue.extend(children)
                
    leaf_cdks_list = sorted(list(leaf_cdks))
    
    # Process chronologically
    all_splits.sort(key=lambda x: x[2])  # sort by split_year
    
    # Identify unique split years
    split_years = sorted(list(set(s[2] for s in all_splits)))
    
    epochs: List[Epoch] = []
    epoch_num = 1
    
    active_cdks: Set[str] = {root_cdk}
    current_year = min_year
    
    # Determine if root is virtual. Virtual if it splits BEFORE we even start counting 
    is_virtual = False
    if split_years and split_years[0] <= min_year:
        is_virtual = True

    if not split_years:
        # No splits
        epochs.append(Epoch(
            epoch_num=1,
            year_start=min_year,
            year_end=None,
            event_label=f"Unchanged since {min_year}",
            active_cdks=[root_cdk],
            leaf_cdks=leaf_cdks_list,
            is_virtual=False
        ))
        return epochs

    # Loop through each distinct split year
    for i, s_year in enumerate(split_years):
        if s_year > current_year:
            # Create an epoch for [current_year, s_year - 1]
            epochs.append(Epoch(
                epoch_num=epoch_num,
                year_start=current_year,
                year_end=s_year - 1,
                event_label="Stable period" if epoch_num == 1 else "Post-split stable period",
                active_cdks=sorted(list(active_cdks)),
                leaf_cdks=leaf_cdks_list,
                is_virtual=is_virtual
            ))
            epoch_num += 1
        
        # Now apply ALL splits that happened in s_year
        splits_this_year = [s for s in all_splits if s[2] == s_year]
        for parent, children, _ in splits_this_year:
            if parent in active_cdks:
                active_cdks.remove(parent)
                active_cdks.update(children)
        
        current_year = max(current_year, s_year)

    # Final epoch (from the last split year to present)
    splits_last_year = [s for s in all_splits if s[2] == split_years[-1]]
    event_labels = []
    
    for parent, children, _ in splits_last_year:
        event_labels.append(_format_event_label(parent, children))
            
    final_label = " | ".join(event_labels) if event_labels else "Final state"
    
    epochs.append(Epoch(
        epoch_num=epoch_num,
        year_start=current_year,
        year_end=None,
        event_label=final_label,
        active_cdks=sorted(list(active_cdks)),
        leaf_cdks=leaf_cdks_list,
        is_virtual=is_virtual
    ))

    # Fix up epoch event labels: epoch N's label should be the split that started epoch N.
    for i, ep in enumerate(epochs):
        if i == 0:
            ep.event_label = "Initial state"
        else:
            splits_started_this = [s for s in all_splits if s[2] == ep.year_start]
            lbls = []
            for p, c, _ in splits_started_this:
                lbls.append(_format_event_label(p, c))
            ep.event_label = " | ".join(lbls) if lbls else f"Split in {ep.year_start}"

    return epochs


def _format_event_label(parent: str, children: List[str]) -> str:
    """Format an event label, detecting renames (1:1 transitions)."""
    if len(children) == 1 and children[0] != parent:
        return f"{parent} → {children[0]} (renamed)"
    elif len(children) <= 3:
        return f"{parent} → {' + '.join(children)}"
    else:
        return f"{parent} → {len(children)} districts"

