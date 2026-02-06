from chatbot.bot import IdeaIntakeBot
from chatbot.states import BotState

bot = IdeaIntakeBot()

while bot.state != BotState.COMPLETE:
    if bot.state == BotState.GREETING:
        bot.greet()

    elif bot.state == BotState.INTAKE:
        user_input = input("\nYour idea: ")
        bot.intake(user_input)

    elif bot.state == BotState.VALIDATION:
        bot.validate()

    elif bot.state == BotState.CORRECTION:
        bot.correct()

    elif bot.state == BotState.CONFIRMATION:
        bot.confirm()

print("\n✅ Idea captured successfully. Agents can now start.")
