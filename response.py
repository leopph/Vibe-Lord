import random
import json


class Response:
    with open("responses.json") as responses:
        RESPONSES: dict[str, list[str]] = json.load(responses)

    @staticmethod
    def get(cat: str) -> str:
        if cat not in Response.RESPONSES:
            raise Exception

        return random.choice(Response.RESPONSES[cat])
