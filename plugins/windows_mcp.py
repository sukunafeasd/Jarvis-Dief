from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('windows_mcp')
PLUGIN_SETTINGS=settings('windows_mcp')
def run(parameters,**kwargs):return dispatch('windows_mcp',parameters)
