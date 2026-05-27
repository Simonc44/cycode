import requests
import json
import logging

class CycodeBaseService:
    def __init__(self, base_url="https://needlessly-faithful-gopher.ngrok-free.app/v3", api_key=None, admin_key=None):
        self.base_url = base_url
        self.api_key = api_key
        self.admin_key = admin_key
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_headers(self, auth_type="bearer", content_type="application/json"):
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        
        if auth_type == "bearer" and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif auth_type == "x-api-key" and self.admin_key:
            headers["X-API-Key"] = self.admin_key
        elif auth_type == "bearer" and self.admin_key:
            headers["Authorization"] = f"Bearer {self.admin_key}"
            
        return headers

    def _request(self, method, endpoint, auth_type="bearer", content_type="application/json", **kwargs):
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self._get_headers(auth_type, content_type)
        
        # Merge existing headers if provided in kwargs
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
            
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            if response.status_code == 204:
                return True
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error for {method} {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    return {"error": e.response.json()}
                except:
                    return {"error": e.response.text}
            return {"error": str(e)}

    def get(self, endpoint, **kwargs):
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self._request("POST", endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self._request("PUT", endpoint, **kwargs)

    def patch(self, endpoint, **kwargs):
        return self._request("PATCH", endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self._request("DELETE", endpoint, **kwargs)
