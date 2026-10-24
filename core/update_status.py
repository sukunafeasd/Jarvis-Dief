"""Release comparison shared by startup and in-session update checks."""
from core.distribution import version


def release_status(state, release):
    current = state.get('current')
    latest = release['version']
    if not current:
        return 'first_install', 'Preparando a primeira instalacao'
    if version(latest) <= version(current):
        return 'current', 'Versao mais recente ja instalada' if version(latest) == version(current) else 'Versao local mais recente que a publicada'
    if state.get('rejected') == latest:
        return 'rejected', 'Atualizacao com falha anterior. Versao estavel preservada'
    return 'available', 'Versao mais recente disponivel: ' + latest
