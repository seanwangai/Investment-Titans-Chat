# Investment Titans Chat

A collaborative investment analysis platform powered by AI experts.

## Setup

1. Clone the repository 
```bash
git clone https://github.com/yourusername/expert-chat-streamlit.git
cd expert-chat-streamlit
```

2. Create virtual environment 
```bash
python -m venv .env
source .env/bin/activate  # On Windows: .env\Scripts\activate
```

3. Install dependencies 
```bash
pip install -r requirements.txt
```

4. Configure API keys
+ For local development:
  - Copy `config.example.py` to `config.py`
  - Update `config.py` with your API keys
+ - Create `.streamlit/secrets.toml` with your API keys
+ 
+ For Streamlit Cloud deployment:
+ - Go to your app's settings in Streamlit Cloud
+ - Add your secrets in the "Secrets" section:
+   ```toml
+   XAI_API_KEY = "your-xai-api-key"
+   XAI_API_BASE = "https://api.x.ai/v1"
+   ```
  
5. Run the application 
```bash
streamlit run app.py
```