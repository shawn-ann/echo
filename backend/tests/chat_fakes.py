from app.services.llm_client import LLMClient


class ScriptedLLMClient(LLMClient):
    def __init__(self, *, locate, minimal="", fluency="", explain=""):
        self.locate = locate
        self.minimal = minimal
        self.fluency = fluency
        self.explain = explain
        self.calls: list[str] = []
        self.reasoning_efforts: list[str | None] = []
        self.temperatures: list[float | None] = []

    async def complete(
        self,
        messages,
        *,
        thinking=True,
        json_mode=True,
        reasoning_effort=None,
        temperature=None,
    ):
        self.reasoning_efforts.append(reasoning_effort)
        self.temperatures.append(temperature)
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
        if "TASK: EXPLAIN_ERROR" in system:
            self.calls.append("explain")
            if isinstance(self.explain, Exception):
                raise self.explain
            return self.explain
        raise AssertionError(f"unexpected prompt: {system[:80]}")
