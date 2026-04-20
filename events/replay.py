from events.store import get_store

def load_events():
    return get_store().read_all()
