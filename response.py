import random
import json


class Response:
    with open("responses.json") as responses:
        RESPONSES: dict[str, list[str]] = json.load(responses)

    @staticmethod
    def get(cat: str, *args) -> str:
        if cat not in Response.RESPONSES:
            raise Exception("INVALID RESPONSE CATEGORY")

        try:
            return random.choice(Response.RESPONSES[cat]).format(*args)
            
        except IndexError:
            raise Exception("NOT ENOUGH PARAMETERS FOR RESPONSE")
