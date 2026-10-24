"""Distinguish useful Live output from empty packets and internal thoughts."""


def has_response_progress(response):
    if getattr(response, 'data', None):
        return True
    calls = getattr(response, 'tool_call', None)
    if calls and getattr(calls, 'function_calls', None):
        return True
    content = getattr(response, 'server_content', None)
    if not content:
        return False
    if getattr(content, 'turn_complete', False):
        return True
    transcript = getattr(content, 'output_transcription', None)
    if str(getattr(transcript, 'text', '') or '').strip():
        return True
    turn = getattr(content, 'model_turn', None)
    for part in getattr(turn, 'parts', None) or ():
        if getattr(part, 'thought', False):
            continue
        if str(getattr(part, 'text', '') or '').strip():
            return True
        inline = getattr(part, 'inline_data', None)
        if inline and getattr(inline, 'data', None):
            return True
    return False
