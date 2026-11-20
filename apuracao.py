"""
Regras de apuração do sistema majoritário (eleição para prefeito),
conforme a Resolução TSE nº 23.677/2021 (alterada pela Res. nº 23.731/2024):

* Municípios com até 200 mil eleitores (e que não são capitais):
  maioria simples - vence quem tiver mais votos, sem segundo turno.
* Capitais e municípios com mais de 200 mil eleitores:
  maioria absoluta - é preciso ter MAIS da metade dos votos válidos;
  caso contrário, há segundo turno entre os dois mais votados.
* Se, antes do segundo turno, um finalista morrer, desistir ou ficar
  impedido, é convocado o remanescente com a maior votação.
* Só candidatos APTOS podem ser eleitos ou ir ao segundo turno.
* Empate: vence (ou vai ao segundo turno) o candidato mais idoso
  (Constituição Federal, art. 77, § 5º, e Código Eleitoral, art. 110).

Votos válidos = votos nominais (brancos e nulos não entram na conta).
"""

from database import ErroUrna, data_para_tela

MINIMO_VOTOS = 10            # o enunciado pede no mínimo 10 iterações de votação
LIMITE_ELEITORES = 200_000


def exige_maioria_absoluta(eleicao):
    return bool(eleicao["capital"]) or eleicao["total_eleitores_municipio"] > LIMITE_ELEITORES


def descricao_regra(eleicao):
    if exige_maioria_absoluta(eleicao):
        return "Maioria absoluta (pode haver 2º turno)"
    return "Maioria simples (turno único)"


def candidato_pode_receber_voto(candidato, turno):
    if candidato is None or candidato["situacao"] != "APTO":
        return False
    return turno == 1 or bool(candidato["no_segundo_turno"])


def apurar(db, turno):
    """Conta os votos do turno e decide o resultado.

    Retorna um dicionário com os números da apuração e a 'situacao':
    AGUARDANDO, ELEITO, EMPATE, SEGUNDO_TURNO ou SEM_VOTOS_VALIDOS.
    """
    candidatos, brancos, nulos = db.contagem(turno)
    if turno == 2:
        candidatos = [c for c in candidatos if c["no_segundo_turno"]]

    validos = sum(c["votos"] for c in candidatos)
    total = validos + brancos + nulos
    resultado = {
        "turno": turno,
        "candidatos": candidatos,
        "brancos": brancos,
        "nulos": nulos,
        "validos": validos,
        "total": total,
        "eleito": None,
        "finalistas": [],
    }

    if total < MINIMO_VOTOS:
        resultado["situacao"] = "AGUARDANDO"
        resultado["mensagem"] = (
            f"Apuração parcial: {total} de no mínimo {MINIMO_VOTOS} votos registrados.\n"
            "O resultado oficial só é divulgado após o mínimo de votos."
        )
        return resultado

    if validos == 0:
        resultado["situacao"] = "SEM_VOTOS_VALIDOS"
        resultado["mensagem"] = "Não houve votos válidos. Nenhum candidato foi eleito."
        return resultado

    # Votos em quem desistiu, morreu ou ficou impedido continuam contando como
    # válidos, mas esse candidato não pode ser eleito.
    aptos = [c for c in candidatos if c["situacao"] == "APTO"]
    if not aptos or aptos[0]["votos"] == 0:
        resultado["situacao"] = "SEM_VOTOS_VALIDOS"
        resultado["mensagem"] = "Nenhum candidato APTO recebeu votos. Ninguém foi eleito."
        return resultado

    primeiro = aptos[0]
    empatado = aptos[1] if len(aptos) > 1 and aptos[1]["votos"] == primeiro["votos"] else None
    percentual = primeiro["votos"] / validos * 100

    if turno == 1 and exige_maioria_absoluta(db.obter_eleicao()):
        if primeiro["votos"] > validos / 2:
            resultado["situacao"] = "ELEITO"
            resultado["eleito"] = primeiro
            resultado["mensagem"] = (
                f"ELEITO(A) NO 1º TURNO: {primeiro['nome']} ({primeiro['numero']} - {primeiro['partido']})\n"
                f"com {primeiro['votos']} votos ({percentual:.1f}% dos válidos) - maioria absoluta."
            )
        else:
            try:
                finalistas = escolher_finalistas(db)
            except ErroUrna as erro:
                resultado["situacao"] = "SEM_VOTOS_VALIDOS"
                resultado["mensagem"] = f"Ninguém obteve maioria absoluta. {erro}"
                return resultado
            nomes = " x ".join(f"{c['nome']} ({c['numero']})" for c in finalistas)
            resultado["situacao"] = "SEGUNDO_TURNO"
            resultado["finalistas"] = finalistas
            resultado["mensagem"] = (
                f"Ninguém obteve mais de 50% dos votos válidos (maior: {percentual:.1f}%).\n"
                f"Haverá SEGUNDO TURNO: {nomes}"
            )
            aptos_1turno = [c for c in db.contagem(1)[0] if c["situacao"] == "APTO"]
            if len(aptos_1turno) > 2 and aptos_1turno[2]["votos"] == finalistas[1]["votos"]:
                resultado["mensagem"] += (
                    f"\nEmpate pela 2ª vaga com {aptos_1turno[2]['nome']}: vai o mais idoso"
                    " - Constituição, art. 77, § 5º."
                )
        return resultado

    regra = "2º turno" if turno == 2 else "maioria simples"
    desempate = ""
    if empatado:
        datas = (primeiro["data_nascimento"], empatado["data_nascimento"])
        if None in datas or datas[0] == datas[1]:
            resultado["situacao"] = "EMPATE"
            resultado["mensagem"] = (
                f"EMPATE entre {primeiro['nome']} e {empatado['nome']} com {primeiro['votos']} votos.\n"
                "Pela legislação vence o mais idoso, mas a data de nascimento não permite desempatar."
            )
            return resultado
        desempate = (
            f"\nEmpate com {empatado['nome']}: vence o mais idoso (nasc. "
            f"{data_para_tela(primeiro['data_nascimento'])}) - Código Eleitoral, art. 110."
        )

    resultado["situacao"] = "ELEITO"
    resultado["eleito"] = primeiro
    resultado["mensagem"] = (
        f"ELEITO(A): {primeiro['nome']} ({primeiro['numero']} - {primeiro['partido']})\n"
        f"com {primeiro['votos']} votos ({percentual:.1f}% dos válidos) - {regra}." + desempate
    )
    return resultado


def escolher_finalistas(db):
    """Os dois candidatos APTOS mais votados no 1º turno.

    Como só considera candidatos aptos, se um finalista desistir, morrer
    ou ficar impedido, o próximo mais votado é convocado automaticamente.
    Empates são resolvidos a favor do mais idoso (ordem de db.contagem).
    """
    candidatos, _, _ = db.contagem(1)
    aptos = [c for c in candidatos if c["situacao"] == "APTO"]
    if len(aptos) < 2:
        raise ErroUrna("São necessários pelo menos dois candidatos aptos para o segundo turno.")
    return aptos[:2]


def iniciar_segundo_turno(db):
    finalistas = escolher_finalistas(db)
    db.marcar_segundo_turno([c["id"] for c in finalistas])
    db.definir_turno(2)
    return finalistas


def recompor_segundo_turno(db):
    """Chamada quando a situação de um candidato muda durante o 2º turno.

    Se a votação do 2º turno ainda não começou, refaz a lista de finalistas
    (convocando o remanescente mais votado). Retorna os finalistas ou None.
    """
    eleicao = db.obter_eleicao()
    if eleicao["turno_atual"] != 2 or db.total_votos(2) > 0:
        return None
    finalistas = escolher_finalistas(db)
    db.marcar_segundo_turno([c["id"] for c in finalistas])
    return finalistas
