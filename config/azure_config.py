import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
AZURE_OPENAI_CONFIG = {
    "api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
    "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    "api_version": os.getenv("AZURE_OPENAI_API_VERSION", ""),
    "embedding_deployment": os.getenv("AZURE_EMBEDDING_DEPLOYMENT", ""),
    "gpt_deployment": os.getenv("AZURE_GPT_DEPLOYMENT", "")
}
 