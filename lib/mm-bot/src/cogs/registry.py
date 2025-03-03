_registry = {}

def register_cog(name: str, instance: object):
    _registry[name] = instance

def get(name: str):
    return _registry.get(name)