from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('github_mcp')
PLUGIN_SETTINGS=settings('github_mcp')
def run(parameters,**kwargs):return dispatch('github_mcp',parameters)
