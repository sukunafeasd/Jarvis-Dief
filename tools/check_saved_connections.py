"""Read-only provider checks, with no credential or mailbox contents in output."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import google_services as google,spotify_service as spotify,gmail_connection as gmail


def main():
    checks=[('gmail',gmail.status,gmail.verify),('google_drive',lambda:google.status('google_drive'),lambda:google.verify('google_drive')),
            ('google_calendar',lambda:google.status('google_calendar'),lambda:google.verify('google_calendar')),('spotify',spotify.status,spotify.verify)]
    for name,status,verify in checks:
        value=status();print(name,{key:value.get(key) for key in ('configured','connected','authorization_pending')},flush=True)
        if not value.get('connected'):continue
        try:
            result=verify();print(name,'teste',result[0] if isinstance(result,tuple) else bool(result.get('ok')),flush=True)
        except Exception as error:
            print(name,'falha',type(error).__name__,'errno',getattr(error,'errno',None),'HTTP',getattr(getattr(error,'resp',None),'status',None),flush=True)
            import traceback
            print([(Path(frame.filename).name,frame.lineno,frame.name) for frame in traceback.extract_tb(error.__traceback__)[-4:]],flush=True)


if __name__=='__main__':main()
