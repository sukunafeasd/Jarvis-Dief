from core.extension_plugin import definition,settings,dispatch
PLUGIN=definition('local_transcription')
PLUGIN_SETTINGS=settings('local_transcription')
def run(parameters,**kwargs):return dispatch('local_transcription',parameters)
