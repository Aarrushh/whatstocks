import json

class SignalGenerator:
    def __init__(self, rag_engine, config_path):
        """
        Initialize SignalGenerator.

        Args:
            rag_engine: An instance of RAGQueryEngine or similar with get_trade_recommendations method.
            config_path: Path to the ETF mapping JSON configuration file.
        """
        self.rag_engine = rag_engine
        self.config_path = config_path

    def _load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def generate_signals(self):
        """
        Generates trade signals by mapping country recommendations to ETFs.

        Returns:
            list: A list of signal dictionaries with ticker, action, and weight.
        """
        recommendations = self.rag_engine.get_trade_recommendations()
        config = self._load_config()

        signals = []
        base_weight = 0.05

        buy_candidates = recommendations.get('buy_candidates', [])
        sell_candidates = recommendations.get('sell_candidates', [])

        for country_code in buy_candidates:
            if country_code in config:
                ticker = config[country_code].get('Broad_Market')
                if ticker and ticker != "None":
                    signals.append({
                        'ticker': ticker,
                        'action': 'BUY',
                        'weight': base_weight
                    })

        for country_code in sell_candidates:
            if country_code in config:
                ticker = config[country_code].get('Broad_Market')
                if ticker and ticker != "None":
                    signals.append({
                        'ticker': ticker,
                        'action': 'SELL',
                        'weight': base_weight
                    })

        return signals
