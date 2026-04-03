import pytest
import json
import os
from unittest.mock import MagicMock
from execution.signal_generator import SignalGenerator

@pytest.fixture
def temp_config(tmp_path):
    config = {
        "IND": {"Broad_Market": "INDA"},
        "USA": {"Broad_Market": "SPY"},
        "CHN": {"Broad_Market": "MCHI"}
    }
    config_file = tmp_path / "etf_mapping.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)

def test_generate_signals(temp_config):
    # Mock RAG engine
    mock_rag_engine = MagicMock()
    mock_rag_engine.get_trade_recommendations.return_value = {
        "buy_candidates": ["IND", "USA"],
        "sell_candidates": ["CHN"]
    }

    generator = SignalGenerator(mock_rag_engine, temp_config)
    signals = generator.generate_signals()

    expected_signals = [
        {'ticker': 'INDA', 'action': 'BUY', 'weight': 0.05},
        {'ticker': 'SPY', 'action': 'BUY', 'weight': 0.05},
        {'ticker': 'MCHI', 'action': 'SELL', 'weight': 0.05}
    ]

    assert len(signals) == 3
    assert signals == expected_signals

def test_generate_signals_missing_country(temp_config):
    # Mock RAG engine with a country not in config
    mock_rag_engine = MagicMock()
    mock_rag_engine.get_trade_recommendations.return_value = {
        "buy_candidates": ["IND", "BRA"],  # BRA not in temp_config
        "sell_candidates": []
    }

    generator = SignalGenerator(mock_rag_engine, temp_config)
    signals = generator.generate_signals()

    expected_signals = [
        {'ticker': 'INDA', 'action': 'BUY', 'weight': 0.05}
    ]

    assert len(signals) == 1
    assert signals == expected_signals

def test_generate_signals_none_ticker(tmp_path):
    # Config with "None" ticker
    config = {
        "IND": {"Broad_Market": "None"}
    }
    config_file = tmp_path / "etf_mapping_none.json"
    config_file.write_text(json.dumps(config))

    mock_rag_engine = MagicMock()
    mock_rag_engine.get_trade_recommendations.return_value = {
        "buy_candidates": ["IND"],
        "sell_candidates": []
    }

    generator = SignalGenerator(mock_rag_engine, str(config_file))
    signals = generator.generate_signals()

    assert len(signals) == 0
