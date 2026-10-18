from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('qdrant_memory')
PLUGIN_SETTINGS=settings('qdrant_memory')
def run(parameters,**kwargs):return dispatch('qdrant_memory',parameters)
