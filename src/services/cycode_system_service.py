from .cycode_base import CycodeBaseService

class CycodeSystemService(CycodeBaseService):
    def get_root_info(self):
        return self.get("/")

    def get_health(self):
        return self.get("/health")

    def get_models(self):
        return self.get("/models")

    def get_model_details(self, model_id: str):
        return self.get(f"/models/{model_id}")

    def run_loadtest(self):
        return self.post("/loadtest/run")

    def get_loadtest_status(self):
        return self.get("/loadtest/status")
