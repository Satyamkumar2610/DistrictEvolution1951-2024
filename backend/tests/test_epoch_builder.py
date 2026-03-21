import pytest
from app.core.epoch_builder import build_epochs, Epoch

def test_epoch_builder_single_node():
    graph = {}
    epochs = build_epochs("A", graph, min_year=1960)
    
    assert len(epochs) == 1
    assert epochs[0].year_start == 1960
    assert epochs[0].year_end is None
    assert epochs[0].active_cdks == ["A"]
    assert epochs[0].leaf_cdks == ["A"]

def test_epoch_builder_two_level_split():
    # A splits into B and C in 1980
    graph = {
        "A": [(["B", "C"], 1980)]
    }
    epochs = build_epochs("A", graph, min_year=1960)
    
    assert len(epochs) == 2
    
    assert epochs[0].year_start == 1960
    assert epochs[0].year_end == 1979
    assert epochs[0].active_cdks == ["A"]
    assert epochs[0].leaf_cdks == ["B", "C"]
    
    assert epochs[1].year_start == 1980
    assert epochs[1].year_end is None
    assert epochs[1].active_cdks == ["B", "C"]
    assert "A" in epochs[1].event_label

def test_epoch_builder_three_level_split():
    # A -> B, C in 1980
    # C -> D, E in 2000
    graph = {
        "A": [(["B", "C"], 1980)],
        "C": [(["D", "E"], 2000)]
    }
    epochs = build_epochs("A", graph, min_year=1960)
    
    assert len(epochs) == 3
    
    # Epoch 1
    assert epochs[0].year_start == 1960
    assert epochs[0].year_end == 1979
    assert epochs[0].active_cdks == ["A"]
    assert epochs[0].leaf_cdks == ["B", "D", "E"]
    
    # Epoch 2
    assert epochs[1].year_start == 1980
    assert epochs[1].year_end == 1999
    assert epochs[1].active_cdks == ["B", "C"]
    assert "A" in epochs[1].event_label
    
    # Epoch 3
    assert epochs[2].year_start == 2000
    assert epochs[2].year_end is None
    assert epochs[2].active_cdks == ["B", "D", "E"]
    assert "C" in epochs[2].event_label

def test_epoch_virtual_flag():
    # A splits in 1950, before min_year 1960
    graph = {
        "A": [(["B", "C"], 1950)]
    }
    epochs = build_epochs("A", graph, min_year=1960)
    
    assert len(epochs) == 1
    assert epochs[0].year_start == 1960
    assert epochs[0].year_end is None
    assert epochs[0].active_cdks == ["B", "C"]
    assert epochs[0].is_virtual == True
