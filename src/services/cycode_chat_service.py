import requests
import json

class CycodeChatService:
    BASE_URL = "https://needlessly-faithful-gopher.ngrok-free.app/v3/chat"

    def __init__(self):
        pass

    def post_chat(self, prompt: str, target: str = "auto", max_new_tokens: int = 512, session_id: str = None, messages: list = None, stream: bool = False, use_memory: bool = True):
        """
        Sends a chat message to the Cycode API.

        Args:
            prompt (str): The user's prompt.
            target (str): The target for the chat (default: "auto").
            max_new_tokens (int): Maximum number of new tokens to generate (default: 512).
            session_id (str, optional): Session ID for the chat.
            messages (list, optional): List of previous messages in the chat.
            stream (bool): Whether to stream the response (default: False).
            use_memory (bool): Whether to use memory for the chat (default: True).

        Returns:
            dict: The JSON response from the API, or None if an error occurs.
        """
        payload = {
            "prompt": prompt,
            "target": target,
            "max_new_tokens": max_new_tokens,
            "stream": stream,
            "use_memory": use_memory
        }
        if session_id:
            payload["session_id"] = session_id
        if messages:
            payload["messages"] = messages

        try:
            response = requests.post(self.BASE_URL, json=payload)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error posting chat: {e}")
            return None

    def post_chat_stream(self, prompt: str, target: str = "auto", max_new_tokens: int = 512, session_id: str = None, messages: list = None, use_memory: bool = True):
        """
        Sends a chat message to the Cycode API and streams the response.

        Args:
            prompt (str): The user's prompt.
            target (str): The target for the chat (default: "auto").
            max_new_tokens (int): Maximum number of new tokens to generate (default: 512).
            session_id (str, optional): Session ID for the chat.
            messages (list, optional): List of previous messages in the chat.
            use_memory (bool): Whether to use memory for the chat (default: True).

        Yields:
            str: Chunks of the streamed response.
        """
        payload = {
            "prompt": prompt,
            "target": target,
            "max_new_tokens": max_new_tokens,
            "stream": True,  # Always true for this endpoint
            "use_memory": use_memory
        }
        if session_id:
            payload["session_id"] = session_id
        if messages:
            payload["messages"] = messages

        try:
            with requests.post(f"{self.BASE_URL}/stream", json=payload, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                    yield chunk
        except requests.exceptions.RequestException as e:
            print(f"Error streaming chat: {e}")
            return

    def get_chat_history(self):
        """
        Retrieves the chat history from the Cycode API.

        Returns:
            dict: The JSON response containing chat history, or None if an error occurs.
        """
        try:
            response = requests.get(f"{self.BASE_URL}/history")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting chat history: {e}")
            return None

    def get_chat_history_item(self, history_id: str):
        """
        Retrieves a specific chat history item from the Cycode API.

        Args:
            history_id (str): The ID of the chat history item to retrieve.

        Returns:
            dict: The JSON response containing the chat history item, or None if an error occurs.
        """
        try:
            response = requests.get(f"{self.BASE_URL}/history/{history_id}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting chat history item {history_id}: {e}")
            return None

if __name__ == '__main__':
    # Example Usage:
    service = CycodeChatService()

    # Test POST /v3/chat
    print("--- Testing POST /v3/chat ---")
    chat_response = service.post_chat(prompt="Hello, how are you?")
    if chat_response:
        print("Chat Response:", chat_response)
    else:
        print("Failed to get chat response.")

    # Test GET /v3/chat/history
    print("\n--- Testing GET /v3/chat/history ---")
    history_response = service.get_chat_history()
    if history_response:
        print("Chat History:", history_response)
    else:
        print("Failed to get chat history.")

    # Test POST /v3/chat/stream
    print("\n--- Testing POST /v3/chat/stream ---")
    print("Streaming chat response:")
    stream_chunks = []
    for chunk in service.post_chat_stream(prompt="Tell me a short story about a brave knight."):
        print(chunk, end='')
        stream_chunks.append(chunk)
    print("\nFinished streaming.")
    if not stream_chunks:
        print("Failed to stream chat response.")

    # Assuming there's at least one history item to test get_chat_history_item
    if history_response and isinstance(history_response, list) and history_response:
        first_history_id = history_response[0] # Assuming history_response is a list of IDs or similar
        print(f"\n--- Testing GET /v3/chat/history/{first_history_id} ---")
        history_item = service.get_chat_history_item(first_history_id)
        if history_item:
            print("Specific History Item:", history_item)
        else:
            print(f"Failed to get history item {first_history_id}.")
    else:
        print("\nSkipping test for GET /v3/chat/history/{id} as no history items were found.")
