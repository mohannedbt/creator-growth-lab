import os
from dotenv import load_dotenv
from google import genai
import time

# 1. Load the variables from your .env file
load_dotenv()

# 2. Retrieve the key (ensure the string matches what is inside your .env)
api_key = os.getenv("GEMINI_API_KEY")

# 3. Initialize the client
# If api_key is None here, it means the .env file wasn't found or the key name is different
client = genai.Client(api_key=api_key)

def get_generic_topic_label(titles):
    """
    Calls the Gemini API using the genai client to get a generic topic label for a list of titles.
    The prompt is designed to guide the LLM to generate a broad, human-readable label.
    """

    # Get the API key from an environment variable (ensure the API key is securely set)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Assuming you've set your API key as an environment variable


    # Construct the context and prompt for the LLM
    context = (
        "Given the following video titles, generate a broad, human-readable label "
        "that describes the content topic. The label should be unique, specific, and avoid generic terms."
        " Do not create labels that are too broad or commonly used. The goal is to describe the content of the titles."
    )
    titles_str = "\n".join(titles)  # Joining titles into a string, each on a new line

    prompt = f"{context}\n\nTitles:\n{titles_str}\n\nLabel:"

    try:
        time.sleep(2)  # To avoid hitting rate limits
        # Make the API call to generate content (topic label)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",  # Specify the model
            contents=prompt
        )

        # Get the generated label from the response and return it
        label = response.text.strip()  # Ensure there are no leading/trailing spaces
        return label

    except Exception as e:
        # In case of error, print the error and return a default label
        print(f"Error generating label: {str(e)}")
        return "Misc"  # Fallback label in case of error


