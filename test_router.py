from source_registry import classify_intent

def test_router():
    assert classify_intent("What did NP15 settle yesterday?") == "price"
    assert classify_intent("Did Diablo Canyon ramp down today?") == "generation"
    assert classify_intent("latest BPA winds") == "west"
    assert classify_intent("any transmission outage today?") == "grid"
    assert classify_intent("SoCalGas pipeline maintenance") == "gas"
