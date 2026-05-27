from .cycode_base import CycodeBaseService

class CycodeAdminService(CycodeBaseService):
    """
    Handles routes that usually require Admin key or are for management.
    """
    
    # --- Auth & Keys ---
    def get_auth_status(self):
        return self.get("/auth/status")

    def create_api_key(self, label: str):
        return self.post(f"/auth/keys", params={"label": label}, auth_type="bearer") # Use admin_key as bearer

    def list_api_keys(self):
        return self.get("/auth/keys", auth_type="bearer")

    def delete_api_key(self, label: str):
        return self.delete(f"/auth/keys/{label}", auth_type="bearer")

    def set_rbac(self, user_id: str, role: str, permissions: list):
        payload = {
            "user_id": user_id,
            "role": role,
            "permissions": permissions
        }
        return self.post("/auth/rbac", json=payload, auth_type="bearer")

    # --- Queue ---
    def submit_job(self, task: str, file_id: str = None, **kwargs):
        payload = {"task": task}
        if file_id: payload["file_id"] = file_id
        payload.update(kwargs)
        return self.post("/queue", json=payload)

    def list_jobs(self):
        return self.get("/queue")

    def get_job_status(self, job_id: str):
        return self.get(f"/queue/{job_id}")

    def cancel_job(self, job_id: str):
        return self.delete(f"/queue/{job_id}")

    def get_queue_stats(self):
        return self.get("/queue/stats")

    def clear_queue(self):
        return self.delete("/queue/clear")

    # --- Ops & Logs ---
    def get_logs(self):
        return self.get("/logs", auth_type="bearer")

    def get_usage_metrics(self):
        return self.get("/metrics/usage")

    def get_latency_metrics(self):
        return self.get("/metrics/latency")

    def get_error_metrics(self):
        return self.get("/metrics/errors")

    def update_quota(self, user_id: str, limit: int):
        return self.post(f"/billing/quotas", params={"uid": user_id, "limit": limit}, auth_type="bearer")
