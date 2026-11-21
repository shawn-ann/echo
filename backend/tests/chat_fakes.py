from app.services.llm_client import LLMClient


class ScriptedLLMClient(LLMClient):
    def __init__(self, *, locate, minimal="", fluency=""):
        self.locate = locate
        self.minimal = minimal
        self.fluency = fluency
        self.calls: list[str] = []

    async def complete(self, messages, *, thinking=True, json_mode=True):
        system = messages[0]["content"]
        if "TASK: LOCATE_ERRORS" in system:
            self.calls.append("locate")
            if isinstance(self.locate, Exception):
                raise self.locate
            return self.locate
        if "TASK: MINIMAL_EDIT" in system:
            self.calls.append("minimal")
            if isinstance(self.minimal, Exception):
                raise self.minimal
            return self.minimal
        if "TASK: NATIVE_FLUENCY" in system:
            self.calls.append("fluency")
            if isinstance(self.fluency, Exception):
                raise self.fluency
            return self.fluency
        raise AssertionError(f"unexpected prompt: {system[:80]}")
