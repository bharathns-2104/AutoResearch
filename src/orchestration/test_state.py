from .state_manager import StateManager, SystemState

state = StateManager()

state.update_state(SystemState.INPUT_RECEIVED)
state.update_progress(10)
state.add_data("idea", "AI Invoice Automation")

state.update_state(SystemState.SEARCHING)
state.update_progress(30)

state.add_error("Sample scraping failure")

state.dump_to_file()

print(state.get_snapshot())
