from transformers import pipeline


class FinancialSentimentAnalyzer:
    def __init__(self, model_name="yiyanghkust/finbert-tone"):
        # You could use "ProsusAI/finbert" or others, but "yiyanghkust/finbert-tone"
        # is a standard option for financial sentiment.
        self.sentiment_pipeline = pipeline("sentiment-analysis", model=model_name)

    def analyze_headlines(self, text_list):
        """
        Takes a list of strings (headlines/URLs), passes them through the
        FinBERT pipeline, and returns a list of dictionaries with label and score.
        """
        if not text_list:
            return []

        # Filter out empty or None strings, mapping their original indices
        valid_texts = []
        valid_indices = []

        for idx, text in enumerate(text_list):
            if text and str(text).strip():
                valid_texts.append(str(text))
                valid_indices.append(idx)

        # Initialize results list with default neutral scores
        results = [{"label": "neutral", "score": 0.0} for _ in range(len(text_list))]

        # If there are no valid texts, return immediately
        if not valid_texts:
            return results

        # Run pipeline on valid texts
        # truncation=True and max_length=512 handle sequences longer than the limit
        pipeline_results = self.sentiment_pipeline(
            valid_texts, truncation=True, max_length=512
        )

        # Re-map the pipeline results back to their original positions
        for i, res in enumerate(pipeline_results):
            original_idx = valid_indices[i]
            results[original_idx] = res

        return results
