# Abertura 2.0.12 local

Resolucao de diretorios reaproveitada dentro de cada inspecao. Cada arquivo
continua recebendo lstat; links/reparse points recebem resolucao propria antes
da decisao de pertinencia ao ambiente. Arquivos normais nao repetem is_file e
stat. Cache de hash e verificacao completa diaria da 2.0.11 preservados.

Comparacao no mesmo ambiente de testes: aquecimento completo 164,81s; algoritmo
anterior com cache 13,58s; novo 6,56s e 6,59s. Nenhuma distribuicao danificada.
Estes numeros nao medem abertura total do aplicativo nem a instalacao pessoal.
O aquecimento mostrou variabilidade alta de disco e continua sendo um limite.

43 testes passaram. Revisao independente identificou link externo apontando
para arquivo interno ausente; corrigido e coberto por regressao especifica.
Sem publicacao de release nem push. Instalador com certificado Equipe Dief.
