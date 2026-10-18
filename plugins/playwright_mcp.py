from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('playwright_mcp')
PLUGIN_SETTINGS=settings('playwright_mcp')
def run(parameters,**kwargs):return dispatch('playwright_mcp',parameters)
