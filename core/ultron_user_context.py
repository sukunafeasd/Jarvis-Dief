"""Only completed user transcriptions may authorize native operations."""
def finalized_text(transcription,fragments,*,response_boundary=False,turn_complete=False):
    finished=getattr(transcription,'finished',None)
    if not (finished is True or turn_complete or response_boundary and finished is not False):return None
    text=' '.join(fragment for fragment in fragments if isinstance(fragment,str)).strip()
    return text or None
