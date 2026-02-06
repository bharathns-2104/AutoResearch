from chatbot.states import BotState
from chatbot.validator import validate_idea
from chatbot.memory import save_idea

class IdeaIntakeBot:
    def __init__(self):
        self.state = BotState.GREETING
        self.idea_text = ""
        self.fail_count = 0
    def greet(self):
        print("👋 Hi! I'm here to collect your business idea for analysis.")
        print("Please describe your idea in detail.")
        self.state = BotState.INTAKE
    def intake(self, user_input):
        if user_input.lower() in ["restart", "back", "cancel"]:
            self.reset()
            return

        self.idea_text = user_input
        self.state = BotState.VALIDATION
    def validate(self):
        is_valid, reason = validate_idea(self.idea_text)

        if is_valid:
            self.state = BotState.CONFIRMATION
        else:
            self.fail_count += 1
            self.state = BotState.CORRECTION
            self.reason = reason
    def correct(self):
        if self.fail_count >= 3:
            print("❗ Example:")
            print("I want to build a mobile app that connects local farmers with restaurants.")
            self.fail_count = 0

        if self.reason == "too_short":
            print("Please add more details (problem, user, solution).")
        elif self.reason == "missing_keywords":
            print("What kind of product or service is this?")
        else:
            print("That input seems unclear. Please rephrase.")

        self.state = BotState.INTAKE
    def confirm(self):
        print("\nHere is what I understood:")
        print(f"👉 {self.idea_text}")
        answer = input("Is this correct? (yes/no): ").lower()

        if answer == "yes":
            save_idea(self.idea_text)
            self.state = BotState.COMPLETE
        else:
            print("Okay, let's fix it.")
            self.state = BotState.INTAKE
    def reset(self):
        print("🔄 Restarting...")
        self.state = BotState.GREETING
        self.idea_text = ""
        self.fail_count = 0
