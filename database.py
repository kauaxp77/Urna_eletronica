"""
Camada de acesso ao banco de dados (SQLite).

Concentra todas as operações de CRUD (Create, Read, Update, Delete)
sobre as tabelas eleicao, candidatos, eleitores e votos.
"""

import os
import sqlite3

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_BANCO = os.path.join(PASTA, "urna.db")
ARQUIVO_SCRIPT = os.path.join(PASTA, "script_banco_de_dados.sql")

SITUACOES = ("APTO", "DESISTENTE", "IMPEDIDO", "FALECIDO")


class ErroUrna(Exception):
    """Erro de regra de negócio, exibido ao usuário em uma caixa de mensagem."""


class BancoDeDados:
    def __init__(self, caminho=ARQUIVO_BANCO):
        banco_novo = not os.path.exists(caminho)
        self.conexao = sqlite3.connect(caminho)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.execute("PRAGMA foreign_keys = ON")
        if banco_novo:
            self._executar_script()

    def _executar_script(self):
        """Cria as tabelas e os dados iniciais a partir do script SQL."""
        with open(ARQUIVO_SCRIPT, encoding="utf-8") as arquivo:
            self.conexao.executescript(arquivo.read())
        self.conexao.commit()

    def fechar(self):
        self.conexao.close()

    # ------------------------------------------------------------------
    # ELEIÇÃO
    # ------------------------------------------------------------------
    def obter_eleicao(self):
        return self.conexao.execute("SELECT * FROM eleicao WHERE id = 1").fetchone()

    def atualizar_eleicao(self, municipio, total_eleitores, capital):
        municipio = municipio.strip()
        if not municipio:
            raise ErroUrna("Informe o nome do município.")
        if total_eleitores <= 0:
            raise ErroUrna("O total de eleitores do município deve ser maior que zero.")
        if self.total_votos() > 0:
            raise ErroUrna("Não é possível alterar a regra da eleição depois que a votação começou.")
        with self.conexao:
            self.conexao.execute(
                "UPDATE eleicao SET municipio = ?, total_eleitores_municipio = ?, capital = ? WHERE id = 1",
                (municipio, total_eleitores, int(capital)),
            )

    def definir_turno(self, turno):
        with self.conexao:
            self.conexao.execute("UPDATE eleicao SET turno_atual = ? WHERE id = 1", (turno,))

    # ------------------------------------------------------------------
    # CANDIDATOS
    # ------------------------------------------------------------------
    def _validar_candidato(self, numero, nome, partido, vice, situacao):
        if not (10 <= numero <= 99):
            raise ErroUrna("O número do candidato a prefeito deve ter 2 dígitos (10 a 99).")
        if not nome.strip() or not partido.strip() or not vice.strip():
            raise ErroUrna("Preencha nome, partido e vice.")
        if situacao not in SITUACOES:
            raise ErroUrna("Situação inválida.")

    def inserir_candidato(self, numero, nome, partido, vice, situacao="APTO"):
        self._validar_candidato(numero, nome, partido, vice, situacao)
        if self.total_votos() > 0:
            raise ErroUrna("Não é possível cadastrar candidatos depois que a votação começou.")
        try:
            with self.conexao:
                self.conexao.execute(
                    "INSERT INTO candidatos (numero, nome, partido, vice, situacao) VALUES (?, ?, ?, ?, ?)",
                    (numero, nome.strip(), partido.strip().upper(), vice.strip(), situacao),
                )
        except sqlite3.IntegrityError:
            raise ErroUrna(f"Já existe um candidato com o número {numero}.")

    def listar_candidatos(self):
        return self.conexao.execute("SELECT * FROM candidatos ORDER BY numero").fetchall()

    def buscar_candidato_por_numero(self, numero):
        return self.conexao.execute("SELECT * FROM candidatos WHERE numero = ?", (numero,)).fetchone()

    def atualizar_candidato(self, candidato_id, numero, nome, partido, vice, situacao):
        self._validar_candidato(numero, nome, partido, vice, situacao)
        atual = self.conexao.execute("SELECT * FROM candidatos WHERE id = ?", (candidato_id,)).fetchone()
        if atual is None:
            raise ErroUrna("Candidato não encontrado.")
        if numero != atual["numero"] and self.votos_do_candidato(candidato_id) > 0:
            raise ErroUrna("Não é possível mudar o número de um candidato que já recebeu votos.")
        try:
            with self.conexao:
                self.conexao.execute(
                    "UPDATE candidatos SET numero = ?, nome = ?, partido = ?, vice = ?, situacao = ? WHERE id = ?",
                    (numero, nome.strip(), partido.strip().upper(), vice.strip(), situacao, candidato_id),
                )
        except sqlite3.IntegrityError:
            raise ErroUrna(f"Já existe um candidato com o número {numero}.")

    def excluir_candidato(self, candidato_id):
        if self.votos_do_candidato(candidato_id) > 0:
            raise ErroUrna(
                "Este candidato já recebeu votos e não pode ser excluído.\n"
                "Para retirá-lo da disputa, altere a situação para DESISTENTE ou IMPEDIDO."
            )
        with self.conexao:
            self.conexao.execute("DELETE FROM candidatos WHERE id = ?", (candidato_id,))

    def marcar_segundo_turno(self, ids):
        with self.conexao:
            self.conexao.execute("UPDATE candidatos SET no_segundo_turno = 0")
            self.conexao.executemany("UPDATE candidatos SET no_segundo_turno = 1 WHERE id = ?", [(i,) for i in ids])

    # ------------------------------------------------------------------
    # ELEITORES
    # ------------------------------------------------------------------
    def _validar_eleitor(self, titulo, nome, secao):
        if not (titulo.isdigit() and len(titulo) == 12):
            raise ErroUrna("O título de eleitor deve ter exatamente 12 números.")
        if not nome.strip():
            raise ErroUrna("Informe o nome do eleitor.")
        if secao <= 0:
            raise ErroUrna("A seção deve ser um número maior que zero.")

    def inserir_eleitor(self, titulo, nome, secao):
        self._validar_eleitor(titulo, nome, secao)
        try:
            with self.conexao:
                self.conexao.execute(
                    "INSERT INTO eleitores (titulo, nome, secao) VALUES (?, ?, ?)",
                    (titulo, nome.strip(), secao),
                )
        except sqlite3.IntegrityError:
            raise ErroUrna(f"Já existe um eleitor com o título {titulo}.")

    def listar_eleitores(self, filtro=""):
        termo = f"%{filtro.strip()}%"
        return self.conexao.execute(
            "SELECT * FROM eleitores WHERE nome LIKE ? OR titulo LIKE ? ORDER BY nome",
            (termo, termo),
        ).fetchall()

    def buscar_eleitor_por_titulo(self, titulo):
        return self.conexao.execute("SELECT * FROM eleitores WHERE titulo = ?", (titulo,)).fetchone()

    def atualizar_eleitor(self, eleitor_id, titulo, nome, secao):
        self._validar_eleitor(titulo, nome, secao)
        try:
            with self.conexao:
                self.conexao.execute(
                    "UPDATE eleitores SET titulo = ?, nome = ?, secao = ? WHERE id = ?",
                    (titulo, nome.strip(), secao, eleitor_id),
                )
        except sqlite3.IntegrityError:
            raise ErroUrna(f"Já existe um eleitor com o título {titulo}.")

    def excluir_eleitor(self, eleitor_id):
        eleitor = self.conexao.execute("SELECT * FROM eleitores WHERE id = ?", (eleitor_id,)).fetchone()
        if eleitor is None:
            raise ErroUrna("Eleitor não encontrado.")
        if eleitor["votou_turno1"] or eleitor["votou_turno2"]:
            raise ErroUrna("Este eleitor já votou e não pode ser excluído (integridade da votação).")
        with self.conexao:
            self.conexao.execute("DELETE FROM eleitores WHERE id = ?", (eleitor_id,))

    # ------------------------------------------------------------------
    # VOTOS
    # ------------------------------------------------------------------
    def registrar_voto(self, eleitor_id, turno, tipo, candidato_id=None):
        """Grava o voto e marca o eleitor como 'já votou' na MESMA transação.

        Se o eleitor já tiver votado neste turno, nada é gravado.
        """
        coluna = {1: "votou_turno1", 2: "votou_turno2"}[turno]
        with self.conexao:
            cursor = self.conexao.execute(
                f"UPDATE eleitores SET {coluna} = 1 WHERE id = ? AND {coluna} = 0", (eleitor_id,)
            )
            if cursor.rowcount != 1:
                raise ErroUrna("Este eleitor já votou neste turno.")
            self.conexao.execute(
                "INSERT INTO votos (turno, candidato_id, tipo) VALUES (?, ?, ?)",
                (turno, candidato_id, tipo),
            )

    def total_votos(self, turno=None):
        if turno is None:
            return self.conexao.execute("SELECT COUNT(*) FROM votos").fetchone()[0]
        return self.conexao.execute("SELECT COUNT(*) FROM votos WHERE turno = ?", (turno,)).fetchone()[0]

    def votos_do_candidato(self, candidato_id):
        return self.conexao.execute(
            "SELECT COUNT(*) FROM votos WHERE candidato_id = ?", (candidato_id,)
        ).fetchone()[0]

    def contagem(self, turno):
        """Retorna (lista de candidatos com votos, brancos, nulos) do turno."""
        candidatos = self.conexao.execute(
            """
            SELECT c.*, COUNT(v.id) AS votos
              FROM candidatos c
              LEFT JOIN votos v ON v.candidato_id = c.id AND v.turno = ?
             GROUP BY c.id
             ORDER BY votos DESC, c.numero
            """,
            (turno,),
        ).fetchall()
        brancos = self.conexao.execute(
            "SELECT COUNT(*) FROM votos WHERE turno = ? AND tipo = 'BRANCO'", (turno,)
        ).fetchone()[0]
        nulos = self.conexao.execute(
            "SELECT COUNT(*) FROM votos WHERE turno = ? AND tipo = 'NULO'", (turno,)
        ).fetchone()[0]
        return candidatos, brancos, nulos

    def zerar_votacao(self):
        """Nova eleição: apaga os votos e libera todos os eleitores."""
        with self.conexao:
            self.conexao.execute("DELETE FROM votos")
            self.conexao.execute("UPDATE eleitores SET votou_turno1 = 0, votou_turno2 = 0")
            self.conexao.execute("UPDATE candidatos SET no_segundo_turno = 0")
            self.conexao.execute("UPDATE eleicao SET turno_atual = 1 WHERE id = 1")
