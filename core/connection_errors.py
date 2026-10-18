"""User-visible failure messages that never expose request tokens or bodies."""
import re


def describe(error):
    if isinstance(error,OSError):return 'Não foi possível gravar ou acessar os dados locais. A configuração anterior foi preservada. Confira o acesso à pasta de dados.'
    if isinstance(error,ValueError):
        text=str(error)
        text=re.sub(r'(?:sk-[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]+|Bearer\s+\S+)','[credencial protegida]',text,flags=re.I)
        return text[:500] or 'Dados inválidos. Confira os campos e tente novamente.'
    code=getattr(error,'status_code',None) or getattr(error,'http_status',None) or getattr(getattr(error,'resp',None),'status',None)
    if code==401:return 'A autorização expirou ou foi recusada. Use Reconectar.'
    if code==403:return 'O provedor recusou a permissão. Confira a conta e os acessos autorizados.'
    if code==402:return 'O provedor exige crédito ou acesso ao modelo selecionado.'
    if code==429:return 'Limite de uso do provedor atingido. Aguarde antes de testar novamente.'
    return 'Não foi possível concluir o teste ('+type(error).__name__+'). Confira a internet e a autorização; nenhuma conexão foi apagada.'
