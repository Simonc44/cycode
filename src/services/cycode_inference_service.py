import requests
from .cycode_base import CycodeBaseService

class CycodeInferenceService(CycodeBaseService):
    # --- Chat Endpoints ---

    def post_chat(self, prompt: str, target: str = "auto", max_new_tokens: int = 512, session_id: str = None, messages: list = None, stream: bool = False, use_memory: bool = True):
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

        return self.post("/chat", json=payload)

    def post_chat_stream(self, prompt: str, target: str = "auto", max_new_tokens: int = 512, session_id: str = None, messages: list = None, use_memory: bool = True):
        payload = {
            "prompt": prompt,
            "target": target,
            "max_new_tokens": max_new_tokens,
            "stream": True,
            "use_memory": use_memory
        }
        if session_id:
            payload["session_id"] = session_id
        if messages:
            payload["messages"] = messages

        url = f"{self.base_url.rstrip('/')}/chat/stream"
        headers = self._get_headers()
        
        try:
            with requests.post(url, json=payload, headers=headers, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                    yield chunk
        except Exception as e:
            self.logger.error(f"Stream error: {e}")
            yield f"Error: {str(e)}"

    def get_chat_history(self):
        return self.get("/chat/history")

    def get_chat_history_item(self, history_id: str):
        return self.get(f"/chat/history/{history_id}")

    # --- Session Endpoints ---

    def create_session(self):
        return self.post("/session")

    def get_sessions(self):
        return self.get("/session")

    def get_session_details(self, session_id: str):
        return self.get(f"/session/{session_id}")

    def add_session_message(self, session_id: str, role: str, content: str):
        payload = {"role": role, "content": content}
        return self.post(f"/session/{session_id}/messages", json=payload)

    # --- Vision (CyVision) Endpoints ---

    def generate_image(self, prompt: str, quality: str = "standard"):
        payload = {"prompt": prompt, "quality": quality}
        return self.post("/image/generate", json=payload)

    def edit_image(self, image_path: str, prompt: str):
        try:
            with open(image_path, 'rb') as img_file:
                return self.post("/image/edit", files={'image': img_file}, data={'prompt': prompt}, content_type=None)
        except Exception as e:
            return {"error": str(e)}

    def analyze_image(self, image_path: str):
        try:
            with open(image_path, 'rb') as img_file:
                return self.post("/image/analyze", files={'image': img_file}, content_type=None)
        except Exception as e:
            return {"error": str(e)}

    # --- Code Endpoints ---

    def execute_code(self, code: str, language: str = "python", timeout: int = 30):
        payload = {"language": language, "code": code, "timeout": timeout}
        return self.post("/code/execute", json=payload)

    def analyze_code(self, code: str):
        return self.post("/code/analyze", json=code)

    def refactor_code(self, code: str):
        return self.post("/code/refactor", json=code)
