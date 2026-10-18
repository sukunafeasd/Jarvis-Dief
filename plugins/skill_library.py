from core import skill_library
from core.essential_plugins import respond

PLUGIN = {'name': 'skill_library', 'description': 'Biblioteca ativa de skills revisadas e workflows do Jarvis. list/search encontra IDs; read consulta instrucoes paginadas. Nao executa scripts, instala pacotes ou concede contas. Use sob demanda para tarefas complexas, com ferramentas reais.',
 'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['status', 'list', 'search', 'read']},
 'id': {'type': 'STRING'}, 'query': {'type': 'STRING'}, 'offset': {'type': 'INTEGER'}}, 'required': ['action']}}


def run(parameters, **kwargs):
    return respond(lambda: skill_library.run(parameters))
