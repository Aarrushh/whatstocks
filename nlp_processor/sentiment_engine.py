from transformers import pipeline

class SentimentEngine:
    def __init__(self):
        """
        Initialize the ProsusAI/finbert model using the Hugging Face pipeline API.
        The model is configured to run on the CPU (device=-1) to maintain
        zero-cost deployment requirements on free-tier servers.
        """
        self.pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            device=-1
        )

    def analyze(self, text):
        """
        Analyze the sentiment of a given text string.
        """
        return self.pipeline(text)

def main():
    # Running this script directly will initialize the model
    # and download/cache it locally if it hasn't been already.
    print("Initializing SentimentEngine and downloading FinBERT model...")
    engine = SentimentEngine()
    print("Model initialized successfully!")

    # Test a simple sentence
    test_sentence = "The company reported better than expected earnings for the quarter."
    print(f"Testing sentiment analysis on: '{test_sentence}'")
    result = engine.analyze(test_sentence)
    print(f"Result: {result}")

if __name__ == '__main__':
    main()
