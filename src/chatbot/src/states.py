from enum import Enum

class BotState(Enum):
    GREETING = 1
    INTAKE = 2
    VALIDATION = 3
    CORRECTION = 4
    CONFIRMATION = 5
    COMPLETE = 6
