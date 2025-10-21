import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

COMPLETIONS_URL = "https://dl-ai-dev-app01-uv01.fortebank.com/openai/fx/completions"

def test_api_connection():
    """
    Tests the connection to the completions API and prints the raw response.
    """
    payload = json.dumps({
        "Model": "gpt-4.1",
        "Content": "This is a test.",
        "Temperature": 0.1,
        "MaxTokens": 50,
    })

    headers = {
        'Content-Type': 'application/json'
    }

    try:
        with requests.Session() as session:
            session.verify = False
            print("--- Sending request to API ---")
            response = session.post(COMPLETIONS_URL, headers=headers, data=payload)
            
            print(f"Status Code: {response.status_code}")
            print("--- Raw Response Content ---")
            print(response.text)
            print("--------------------------")

            response.raise_for_status()
            
            print("\n--- Response successfully parsed as JSON ---")
            print(response.json())
            print("------------------------------------------")


    except requests.exceptions.RequestException as e:
        print(f"\n--- Error calling completions API ---")
        print(e)
        print("-------------------------------------")
    except json.JSONDecodeError as e:
        print(f"\n--- Error decoding JSON from API response ---")
        print(e)
        print("---------------------------------------------")

if __name__ == "__main__":
    test_api_connection()
