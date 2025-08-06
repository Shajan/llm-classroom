import os
from dotenv import load_dotenv
from openai import OpenAI

def main():
    # Load environment variables from .env file
    load_dotenv("../.env")
    
    # Get API key from environment variables
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # The question to ask
    question = "What is the capital of France?"
    
    try:
        # Send request to OpenAI API
        print(f"Asking OpenAI: {question}")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using a cost-effective model
            messages=[
                {"role": "user", "content": question}
            ],
            max_tokens=100,  # Limit response length for a simple question
            temperature=0.1  # Low temperature for factual responses
        )
        
        # Extract and display the answer
        answer = response.choices[0].message.content.strip()
        print(f"Answer: {answer}")
        
    except Exception as e:
        print(f"Error occurred while making the request: {e}")

if __name__ == "__main__":
    main()
