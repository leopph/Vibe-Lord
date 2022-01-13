import json
import random


class Responses:
    def __init__(self, path: str) -> None:
        with open(path) as responses:
            self.__responses: dict[str, list[str]] = json.load(responses)


    def get(self, cat: str, *args) -> str: 
        try:
            return random.choice(self.__responses[cat]).format(*args)
        # If __responses[cat] throws
        except KeyError:
            raise Exception("INVALID RESPONSE CATEGORY")
        # If format throws
        except IndexError:
            raise Exception("NOT ENOUGH PARAMETERS FOR RESPONSE")
