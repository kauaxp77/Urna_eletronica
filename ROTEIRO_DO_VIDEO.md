# Roteiro do vídeo (máximo 3 minutos)

## 0:00 – 0:15 · Apresentação
"Olá, meu nome é ________, matrícula ________, curso ________.
Este é o meu sistema de urna eletrônica para a ATPS de Tópicos Avançados."

## 0:15 – 2:15 · Código-fonte (2 minutos)

1. **script_banco_de_dados.sql** (~25 s)
   - Quatro tabelas: `eleicao`, `candidatos`, `eleitores`, `votos`.
   - Mostrar `votou_turno1/votou_turno2` (garante voto único) e que `votos` não tem o eleitor (voto secreto).
   - Restrições `CHECK` e `UNIQUE` (número do candidato e título).

2. **database.py** (~40 s)
   - Classe `BancoDeDados`: cria o banco executando o script SQL.
   - CRUD: `inserir_candidato`, `listar_candidatos`, `atualizar_candidato`, `excluir_candidato`
     (e o mesmo para eleitores).
   - `registrar_voto`: UPDATE "já votou" + INSERT do voto **na mesma transação** – se o eleitor já votou, nada é gravado.

3. **apuracao.py** (~30 s)
   - `exige_maioria_absoluta`: capital ou > 200 mil eleitores.
   - `apurar`: conta válidos, brancos e nulos; decide eleito, empate ou 2º turno; exige mínimo de 10 votos.
   - `escolher_finalistas`: só candidatos APTOS → se alguém desistir, o próximo mais votado é convocado.

4. **main.py** (~25 s)
   - Tkinter com abas (Notebook); classe `AbaUrna` com tela e teclado iguais aos da urna real.
   - Abas de cadastro com Treeview; apuração com gráfico desenhado em Canvas.

## 2:15 – 3:00 · Execução e testes (1 minuto)
1. Votar com 2 ou 3 eleitores (um nominal, um BRANCO, um número inexistente → NULO). Mostrar a tela "FIM".
2. Tentar votar de novo com o mesmo título → mensagem "JÁ VOTOU".
3. (Ter deixado previamente outros votos para completar 10.) Abrir **Apuração** → resultado + gráfico → **Iniciar 2º turno**.
4. **Candidatos**: cadastrar um, alterar, excluir. Alterar um finalista para DESISTENTE e mostrar o 3º colocado convocado.
5. Encerrar: "Obrigado!"

> Dica: grave a tela com OBS Studio ou Loom, não use o celular. Publique no YouTube (não listado), Loom ou Vimeo
> e cole o link no arquivo `LINK_DO_VIDEO_SEU_NOME_COMPLETO.txt`.
