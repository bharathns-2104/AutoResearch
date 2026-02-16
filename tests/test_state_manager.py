from orchestration.state_manager import StateManager, SystemState


def test_singleton_behavior():
    s1 = StateManager()
    s2 = StateManager()
    assert s1 is s2


def test_state_transition():
    state = StateManager()
    state.update_state(SystemState.SEARCHING)
    assert state.current_state == SystemState.SEARCHING


def test_error_addition():
    state = StateManager()
    state.add_error("Test error")
    assert "Test error" in state.errors
