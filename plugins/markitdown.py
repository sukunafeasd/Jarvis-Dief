from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('markitdown')
PLUGIN_SETTINGS=settings('markitdown')
def run(parameters,**kwargs):return dispatch('markitdown',parameters)
