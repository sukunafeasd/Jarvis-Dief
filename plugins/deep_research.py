from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('deep_research')
PLUGIN_SETTINGS=settings('deep_research')
def run(parameters,**kwargs):return dispatch('deep_research',parameters)
