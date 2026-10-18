from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('context7')
PLUGIN_SETTINGS=settings('context7')
def run(parameters,**kwargs):return dispatch('context7',parameters)
