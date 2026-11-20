"""Testes automáticos das regras de negócio (banco de dados e apuração).

Executar na raiz do projeto:  python -m unittest -v
Não abrem a interface gráfica: cada teste usa um banco SQLite temporário.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import apuracao  # noqa: E402
from database import BancoDeDados, ErroUrna  # noqa: E402


class BaseUrna(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.db = BancoDeDados(os.path.join(self.pasta.name, "teste.db"))

    def tearDown(self):
        self.db.fechar()
        self.pasta.cleanup()

    # ---- auxiliares --------------------------------------------------
    def candidato(self, numero):
        return self.db.buscar_candidato_por_numero(numero)

    def votar(self, votos, turno=1):
        """votos: lista com número do candidato, 'BRANCO' ou 'NULO' (um por eleitor)."""
        eleitores = [e for e in self.db.listar_eleitores() if not e[f"votou_turno{turno}"]]
        self.assertGreaterEqual(len(eleitores), len(votos), "eleitores insuficientes no teste")
        for eleitor, voto in zip(eleitores, votos):
            if voto in ("BRANCO", "NULO"):
                self.db.registrar_voto(eleitor["id"], turno, voto)
            else:
                self.db.registrar_voto(eleitor["id"], turno, "NOMINAL", self.candidato(voto)["id"])

    def exigir_maioria_absoluta(self):
        self.db.atualizar_eleicao("Capital Teste", 500_000, capital=True)


class TestBancoDeDados(BaseUrna):
    def test_dados_iniciais(self):
        self.assertEqual(len(self.db.listar_candidatos()), 4)
        self.assertEqual(len(self.db.listar_eleitores()), 12)
        self.assertEqual(self.db.obter_eleicao()["municipio"], "Águas Lindas de Goiás")

    def test_eleitor_vota_uma_unica_vez(self):
        eleitor = self.db.buscar_eleitor_por_titulo("000000000101")
        self.db.registrar_voto(eleitor["id"], 1, "BRANCO")
        with self.assertRaises(ErroUrna):
            self.db.registrar_voto(eleitor["id"], 1, "BRANCO")
        self.assertEqual(self.db.total_votos(1), 1, "o segundo voto não pode ser gravado")

    def test_voto_secreto_tabela_votos_sem_eleitor(self):
        colunas = {linha["name"] for linha in self.db.conexao.execute("PRAGMA table_info(votos)")}
        self.assertFalse(any("eleitor" in c for c in colunas))

    def test_crud_candidato(self):
        self.db.inserir_candidato(99, "Teste Silva", "ptt", "Vice Teste")
        novo = self.candidato(99)
        self.assertEqual(novo["partido"], "PTT")
        self.db.atualizar_candidato(novo["id"], 99, "Teste Souza", "PTT", "Vice Teste", "APTO")
        self.assertEqual(self.candidato(99)["nome"], "Teste Souza")
        self.db.excluir_candidato(novo["id"])
        self.assertIsNone(self.candidato(99))

    def test_numero_de_candidato_duplicado(self):
        with self.assertRaises(ErroUrna):
            self.db.inserir_candidato(12, "Outro", "XYZ", "Vice")

    def test_numero_de_candidato_invalido(self):
        with self.assertRaises(ErroUrna):
            self.db.inserir_candidato(123, "Outro", "XYZ", "Vice")

    def test_nao_exclui_candidato_com_votos(self):
        self.votar([12])
        with self.assertRaises(ErroUrna):
            self.db.excluir_candidato(self.candidato(12)["id"])

    def test_crud_eleitor_e_titulo_invalido(self):
        self.db.inserir_eleitor("123456789012", "Novo Eleitor", 104)
        self.assertIsNotNone(self.db.buscar_eleitor_por_titulo("123456789012"))
        with self.assertRaises(ErroUrna):
            self.db.inserir_eleitor("123", "Título Curto", 104)

    def test_nao_exclui_eleitor_que_votou(self):
        self.votar(["BRANCO"])
        eleitor = [e for e in self.db.listar_eleitores() if e["votou_turno1"]][0]
        with self.assertRaises(ErroUrna):
            self.db.excluir_eleitor(eleitor["id"])

    def test_nao_altera_regra_depois_da_votacao(self):
        self.votar(["BRANCO"])
        with self.assertRaises(ErroUrna):
            self.exigir_maioria_absoluta()


class TestApuracao(BaseUrna):
    def test_aguarda_minimo_de_10_votos(self):
        self.votar([12] * 9)
        self.assertEqual(apuracao.apurar(self.db, 1)["situacao"], "AGUARDANDO")

    def test_maioria_simples_sem_segundo_turno(self):
        # 4 x 3 x 3: 40% dos válidos já basta em município com até 200 mil eleitores
        self.votar([12] * 4 + [25] * 3 + [40] * 3)
        r = apuracao.apurar(self.db, 1)
        self.assertEqual(r["situacao"], "ELEITO")
        self.assertEqual(r["eleito"]["numero"], 12)

    def test_brancos_e_nulos_nao_sao_validos(self):
        self.votar([12] * 3 + [25] * 2 + ["BRANCO"] * 3 + ["NULO"] * 2)
        r = apuracao.apurar(self.db, 1)
        self.assertEqual((r["validos"], r["brancos"], r["nulos"], r["total"]), (5, 3, 2, 10))

    def test_empate_na_maioria_simples(self):
        self.votar([12] * 5 + [25] * 5)
        self.assertEqual(apuracao.apurar(self.db, 1)["situacao"], "EMPATE")

    def test_sem_votos_validos(self):
        self.votar(["BRANCO"] * 5 + ["NULO"] * 5)
        self.assertEqual(apuracao.apurar(self.db, 1)["situacao"], "SEM_VOTOS_VALIDOS")

    def test_maioria_absoluta_eleito_no_primeiro_turno(self):
        self.exigir_maioria_absoluta()
        self.votar([12] * 6 + [25] * 4)
        r = apuracao.apurar(self.db, 1)
        self.assertEqual(r["situacao"], "ELEITO")
        self.assertEqual(r["eleito"]["numero"], 12)

    def test_exatamente_50_por_cento_vai_ao_segundo_turno(self):
        self.exigir_maioria_absoluta()
        self.votar([12] * 5 + [25] * 3 + [40] * 2)
        r = apuracao.apurar(self.db, 1)
        self.assertEqual(r["situacao"], "SEGUNDO_TURNO")
        self.assertEqual([c["numero"] for c in r["finalistas"]], [12, 25])

    def test_segundo_turno_completo(self):
        self.exigir_maioria_absoluta()
        self.votar([12] * 4 + [25] * 4 + [40] * 2)
        apuracao.iniciar_segundo_turno(self.db)
        self.assertEqual(self.db.obter_eleicao()["turno_atual"], 2)
        # quem não está no 2º turno não pode receber voto
        self.assertFalse(apuracao.candidato_pode_receber_voto(self.candidato(40), 2))
        self.votar([25] * 6 + [12] * 4, turno=2)
        r = apuracao.apurar(self.db, 2)
        self.assertEqual(r["situacao"], "ELEITO")
        self.assertEqual(r["eleito"]["numero"], 25)

    def test_desistente_convoca_o_proximo_mais_votado(self):
        self.exigir_maioria_absoluta()
        self.votar([12] * 4 + [25] * 3 + [40] * 2 + [77])
        apuracao.iniciar_segundo_turno(self.db)
        c25 = self.candidato(25)
        self.db.atualizar_candidato(c25["id"], 25, c25["nome"], c25["partido"], c25["vice"], "DESISTENTE")
        finalistas = apuracao.recompor_segundo_turno(self.db)
        self.assertEqual([c["numero"] for c in finalistas], [12, 40])


if __name__ == "__main__":
    unittest.main()
