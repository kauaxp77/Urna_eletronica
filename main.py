"""
URNA ELETRÔNICA - ELEIÇÕES MUNICIPAIS 2024 (PREFEITO)

Sistema que simula o processo de votação de uma urna eletrônica:
  * cadastro, alteração e exclusão de candidatos e eleitores (CRUD);
  * votação com teclado igual ao da urna (números, BRANCO, CORRIGE, CONFIRMA);
  * cada eleitor vota apenas uma vez por turno;
  * apuração seguindo as regras de maioria simples/absoluta e 2º turno;
  * todos os dados gravados em banco SQLite (arquivo urna.db).

Execute:  python main.py
"""

import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import apuracao
from database import SITUACOES, BancoDeDados, ErroUrna

try:
    import winsound  # som de "fim" da urna (somente Windows)
except ImportError:
    winsound = None

# ---------------------------------------------------------------------
# Cores e fontes
# ---------------------------------------------------------------------
AZUL = "#0b3d91"
AZUL_CLARO = "#e8eef9"
VERDE = "#1e8f3e"
LARANJA = "#e07b00"
VERMELHO = "#b3261e"
CINZA_URNA = "#3a3a3a"
TELA_URNA = "#f4f4ec"
FONTE = ("Segoe UI", 10)
FONTE_TITULO = ("Segoe UI", 16, "bold")


def tocar_som_fim():
    if winsound is None:
        return

    def tocar():
        for _ in range(5):
            winsound.Beep(1600, 90)
        winsound.Beep(1600, 500)

    threading.Thread(target=tocar, daemon=True).start()


def ler_inteiro(texto, campo):
    try:
        return int(texto.strip())
    except ValueError:
        raise ErroUrna(f"O campo '{campo}' deve ser um número inteiro.")


# =====================================================================
# Aba 1 - URNA
# =====================================================================
class AbaUrna(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=15)
        self.app = app
        self.db = app.db
        self.eleitor = None       # eleitor liberado pelo mesário
        self.digitos = ""
        self.estado = "bloqueada"  # bloqueada | votando | branco | fim

        self.columnconfigure(1, weight=1)
        self._montar_mesario()
        self._montar_urna()
        self.mostrar_bloqueada()

    # ------------------------- terminal do mesário -------------------
    def _montar_mesario(self):
        painel = ttk.LabelFrame(self, text=" Terminal do Mesário ", padding=15)
        painel.grid(row=0, column=0, sticky="ns", padx=(0, 15))

        ttk.Label(painel, text="Título de eleitor (12 dígitos):").pack(anchor="w")
        self.var_titulo = tk.StringVar()
        self.entrada_titulo = ttk.Entry(painel, textvariable=self.var_titulo, width=24, font=("Consolas", 13))
        self.entrada_titulo.pack(fill="x", pady=(4, 8))
        self.entrada_titulo.bind("<Return>", lambda e: self.liberar_urna())

        self.botao_liberar = ttk.Button(painel, text="Liberar urna", style="Primario.TButton",
                                        command=self.liberar_urna)
        self.botao_liberar.pack(fill="x")

        self.lbl_eleitor = ttk.Label(painel, text="", wraplength=230, justify="left")
        self.lbl_eleitor.pack(anchor="w", pady=12)

        ttk.Separator(painel).pack(fill="x", pady=8)
        self.lbl_turno = ttk.Label(painel, text="", font=("Segoe UI", 11, "bold"))
        self.lbl_turno.pack(anchor="w")
        self.lbl_contador = ttk.Label(painel, text="")
        self.lbl_contador.pack(anchor="w", pady=(4, 2))
        self.barra = ttk.Progressbar(painel, maximum=apuracao.MINIMO_VOTOS, length=230)
        self.barra.pack(fill="x", pady=4)

        ttk.Separator(painel).pack(fill="x", pady=8)
        dica = ("Dica: com a urna liberada você também pode usar o teclado:\n"
                "números = digitar, Enter = CONFIRMA,\nBackspace = CORRIGE, B = BRANCO.")
        ttk.Label(painel, text=dica, foreground="#555", wraplength=230, justify="left").pack(anchor="w")

    # ------------------------------ urna -----------------------------
    def _montar_urna(self):
        corpo = tk.Frame(self, bg=CINZA_URNA, padx=18, pady=18)
        corpo.grid(row=0, column=1, sticky="nsew")
        corpo.columnconfigure(0, weight=1)

        # Tela
        self.tela = tk.Frame(corpo, bg=TELA_URNA, bd=4, relief="sunken", width=520, height=380)
        self.tela.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.tela.grid_propagate(False)
        self.tela.pack_propagate(False)

        # Teclado
        teclado = tk.Frame(corpo, bg="#222", padx=12, pady=12)
        teclado.grid(row=0, column=1, sticky="n")
        tk.Label(teclado, text="JUSTIÇA ELEITORAL", bg="#222", fg="white",
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 10))

        posicoes = ["1", "2", "3", "4", "5", "6", "7", "8", "9", None, "0", None]
        for indice, digito in enumerate(posicoes):
            if digito is None:
                continue
            tk.Button(teclado, text=digito, width=4, height=1, font=("Segoe UI", 16, "bold"),
                      bg="black", fg="white", activebackground="#444", activeforeground="white",
                      command=lambda d=digito: self.digitar(d)).grid(
                row=1 + indice // 3, column=indice % 3, padx=4, pady=4)

        especiais = tk.Frame(teclado, bg="#222")
        especiais.grid(row=6, column=0, columnspan=3, pady=(12, 0))
        tk.Button(especiais, text="BRANCO", width=8, height=2, bg="white", fg="black",
                  font=("Segoe UI", 9, "bold"), command=self.branco).pack(side="left", padx=3)
        tk.Button(especiais, text="CORRIGE", width=8, height=2, bg=LARANJA, fg="black",
                  font=("Segoe UI", 9, "bold"), command=self.corrige).pack(side="left", padx=3)
        tk.Button(especiais, text="CONFIRMA", width=9, height=3, bg=VERDE, fg="black",
                  font=("Segoe UI", 9, "bold"), command=self.confirma).pack(side="left", padx=3)

    def _limpar_tela(self):
        for widget in self.tela.winfo_children():
            widget.destroy()

    def _texto(self, texto, tamanho=12, negrito=False, **opcoes):
        fonte = ("Segoe UI", tamanho, "bold" if negrito else "normal")
        return tk.Label(self.tela, text=texto, bg=TELA_URNA, font=fonte, **opcoes)

    # ------------------------- telas da urna -------------------------
    def mostrar_bloqueada(self):
        self.estado = "bloqueada"
        self.eleitor = None
        self.digitos = ""
        self._limpar_tela()
        self._texto("URNA ELETRÔNICA", 22, True, fg=AZUL).pack(pady=(90, 10))
        self._texto("Eleições Municipais 2024 - Prefeito", 13).pack()
        self._texto("Aguardando liberação do mesário...", 12, fg="#777").pack(pady=30)
        self.entrada_titulo.configure(state="normal")
        self.botao_liberar.configure(state="normal")
        self.var_titulo.set("")
        self.lbl_eleitor.configure(text="")
        self.entrada_titulo.focus_set()
        self.atualizar()

    def mostrar_votacao(self):
        self._limpar_tela()
        turno = self.app.turno_atual()
        cabecalho = "SEU VOTO PARA" + (" - 2º TURNO" if turno == 2 else "")
        self._texto(cabecalho, 11).place(x=12, y=8)
        self._texto("PREFEITO", 20, True).place(x=170, y=40)

        self._texto("Número:", 13).place(x=20, y=110)
        for posicao in range(2):
            digito = self.digitos[posicao] if posicao < len(self.digitos) else ""
            caixa = tk.Label(self.tela, text=digito, width=2, font=("Consolas", 24, "bold"), bg="white",
                             relief="solid", bd=1)
            caixa.place(x=110 + posicao * 52, y=96)
            if posicao == len(self.digitos):
                caixa.configure(bg="#fff6b0")  # piscando onde o próximo número entra

        if len(self.digitos) == 2:
            candidato = self.db.buscar_candidato_por_numero(int(self.digitos))
            if apuracao.candidato_pode_receber_voto(candidato, turno):
                self._texto(f"Nome:     {candidato['nome']}", 13).place(x=20, y=170)
                self._texto(f"Partido:  {candidato['partido']}", 13).place(x=20, y=205)
                self._texto(f"Vice-prefeito:  {candidato['vice']}", 11).place(x=20, y=240)
            else:
                self._texto("NÚMERO ERRADO", 14, True).place(x=20, y=170)
                self._texto("VOTO NULO", 22, True, fg=VERMELHO).place(x=150, y=210)
            self._rodape()

    def mostrar_branco(self):
        self.estado = "branco"
        self.digitos = ""
        self._limpar_tela()
        self._texto("SEU VOTO PARA", 11).place(x=12, y=8)
        self._texto("PREFEITO", 20, True).place(x=170, y=40)
        self._texto("VOTO EM BRANCO", 24, True).place(x=110, y=150)
        self._rodape()

    def _rodape(self):
        tk.Frame(self.tela, bg="black", height=1, width=500).place(x=5, y=290)
        self._texto("Aperte a tecla:", 10).place(x=12, y=298)
        self._texto("CONFIRMA para CONFIRMAR este voto", 10, fg=VERDE).place(x=30, y=320)
        self._texto("CORRIGE para REINICIAR este voto", 10, fg=LARANJA).place(x=30, y=342)

    def mostrar_fim(self):
        self.estado = "fim"
        self._limpar_tela()
        self._texto("FIM", 90, True).pack(expand=True)
        tocar_som_fim()
        self.after(2500, self.mostrar_bloqueada)

    # ---------------------------- ações ------------------------------
    def liberar_urna(self):
        if self.estado != "bloqueada":
            return
        titulo = self.var_titulo.get().strip()
        eleitor = self.db.buscar_eleitor_por_titulo(titulo)
        turno = self.app.turno_atual()
        if eleitor is None:
            messagebox.showerror("Eleitor não encontrado",
                                 "Título não cadastrado nesta seção.\nCadastre o eleitor na aba 'Eleitores'.")
            return
        if eleitor[f"votou_turno{turno}"]:
            messagebox.showwarning("Voto já registrado",
                                   f"{eleitor['nome']} JÁ VOTOU no {turno}º turno.\n"
                                   "Cada eleitor só pode votar uma vez.")
            return
        self.eleitor = eleitor
        self.digitos = ""
        self.estado = "votando"
        self.lbl_eleitor.configure(text=f"Eleitor liberado:\n{eleitor['nome']}\nSeção {eleitor['secao']}",
                                   foreground=VERDE)
        self.entrada_titulo.configure(state="disabled")
        self.botao_liberar.configure(state="disabled")
        self.focus_set()
        self.mostrar_votacao()

    def digitar(self, digito):
        if self.estado == "votando" and len(self.digitos) < 2:
            self.digitos += digito
            self.mostrar_votacao()

    def branco(self):
        if self.estado == "votando" and not self.digitos:
            self.mostrar_branco()

    def corrige(self):
        if self.estado in ("votando", "branco"):
            self.digitos = ""
            self.estado = "votando"
            self.mostrar_votacao()

    def confirma(self):
        turno = self.app.turno_atual()
        if self.estado == "branco":
            tipo, candidato_id = "BRANCO", None
        elif self.estado == "votando" and len(self.digitos) == 2:
            candidato = self.db.buscar_candidato_por_numero(int(self.digitos))
            if apuracao.candidato_pode_receber_voto(candidato, turno):
                tipo, candidato_id = "NOMINAL", candidato["id"]
            else:
                tipo, candidato_id = "NULO", None
        else:
            return
        try:
            self.db.registrar_voto(self.eleitor["id"], turno, tipo, candidato_id)
        except ErroUrna as erro:
            messagebox.showerror("Erro", str(erro))
            self.mostrar_bloqueada()
            return
        self.app.atualizar_tudo()
        self.mostrar_fim()

    def tecla(self, evento):
        """Atalhos do teclado físico quando a urna está liberada."""
        if self.estado not in ("votando", "branco"):
            return
        if evento.char.isdigit():
            self.digitar(evento.char)
        elif evento.keysym in ("Return", "KP_Enter"):
            self.confirma()
        elif evento.keysym == "BackSpace":
            self.corrige()
        elif evento.char.lower() == "b":
            self.branco()

    def atualizar(self):
        turno = self.app.turno_atual()
        votos = self.db.total_votos(turno)
        self.lbl_turno.configure(text=f"{turno}º TURNO em andamento")
        self.lbl_contador.configure(text=f"Votos registrados: {votos}  (mínimo: {apuracao.MINIMO_VOTOS})")
        self.barra.configure(value=min(votos, apuracao.MINIMO_VOTOS))


# =====================================================================
# Aba 2 - CANDIDATOS (CRUD)
# =====================================================================
class AbaCandidatos(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=15)
        self.app = app
        self.db = app.db
        self.selecionado = None

        formulario = ttk.LabelFrame(self, text=" Dados do candidato a prefeito ", padding=12)
        formulario.pack(fill="x")

        self.var_numero = tk.StringVar()
        self.var_nome = tk.StringVar()
        self.var_partido = tk.StringVar()
        self.var_vice = tk.StringVar()
        self.var_situacao = tk.StringVar(value="APTO")

        campos = [("Número (2 dígitos):", self.var_numero, 8), ("Nome:", self.var_nome, 32),
                  ("Partido (sigla):", self.var_partido, 10), ("Vice-prefeito:", self.var_vice, 32)]
        for indice, (rotulo, variavel, largura) in enumerate(campos):
            linha, coluna = divmod(indice, 2)
            ttk.Label(formulario, text=rotulo).grid(row=linha, column=coluna * 2, sticky="w", padx=(0, 6), pady=4)
            ttk.Entry(formulario, textvariable=variavel, width=largura).grid(
                row=linha, column=coluna * 2 + 1, sticky="w", padx=(0, 20), pady=4)
        ttk.Label(formulario, text="Situação:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(formulario, textvariable=self.var_situacao, values=SITUACOES, state="readonly",
                     width=14).grid(row=2, column=1, sticky="w", pady=4)

        botoes = ttk.Frame(self)
        botoes.pack(fill="x", pady=10)
        ttk.Button(botoes, text="➕ Cadastrar", style="Primario.TButton", command=self.cadastrar).pack(side="left")
        ttk.Button(botoes, text="✏ Alterar", command=self.alterar).pack(side="left", padx=6)
        ttk.Button(botoes, text="🗑 Excluir", style="Perigo.TButton", command=self.excluir).pack(side="left")
        ttk.Button(botoes, text="Limpar campos", command=self.limpar).pack(side="left", padx=6)
        ttk.Label(botoes, text="Clique em um candidato da lista para alterar ou excluir.",
                  foreground="#555").pack(side="right")

        colunas = ("numero", "nome", "partido", "vice", "situacao", "segundo")
        titulos = ("Número", "Nome", "Partido", "Vice-prefeito", "Situação", "No 2º turno")
        larguras = (70, 220, 90, 220, 110, 100)
        self.tabela = ttk.Treeview(self, columns=colunas, show="headings", height=12)
        for coluna, titulo, largura in zip(colunas, titulos, larguras):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura, anchor="center" if largura < 120 else "w")
        self.tabela.tag_configure("inapto", foreground="#999")
        self.tabela.pack(fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.selecionar)

    def _dados(self):
        return (ler_inteiro(self.var_numero.get(), "Número"), self.var_nome.get(), self.var_partido.get(),
                self.var_vice.get(), self.var_situacao.get())

    def cadastrar(self):
        try:
            self.db.inserir_candidato(*self._dados())
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível cadastrar", str(erro))
            return
        messagebox.showinfo("Sucesso", "Candidato cadastrado com sucesso!")
        self.limpar()
        self.app.atualizar_tudo()

    def alterar(self):
        if self.selecionado is None:
            messagebox.showwarning("Atenção", "Selecione um candidato na lista para alterar.")
            return
        try:
            self.db.atualizar_candidato(self.selecionado, *self._dados())
            finalistas = apuracao.recompor_segundo_turno(self.db)
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível alterar", str(erro))
            return
        mensagem = "Candidato alterado com sucesso!"
        if finalistas:
            nomes = " x ".join(c["nome"] for c in finalistas)
            mensagem += f"\n\nSegundo turno atualizado: {nomes}"
        messagebox.showinfo("Sucesso", mensagem)
        self.limpar()
        self.app.atualizar_tudo()

    def excluir(self):
        if self.selecionado is None:
            messagebox.showwarning("Atenção", "Selecione um candidato na lista para excluir.")
            return
        if not messagebox.askyesno("Confirmar exclusão", f"Excluir o candidato {self.var_nome.get()}?"):
            return
        try:
            self.db.excluir_candidato(self.selecionado)
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível excluir", str(erro))
            return
        messagebox.showinfo("Sucesso", "Candidato excluído.")
        self.limpar()
        self.app.atualizar_tudo()

    def selecionar(self, _evento=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        self.selecionado = int(selecao[0])
        numero, nome, partido, vice, situacao, _ = self.tabela.item(selecao[0], "values")
        self.var_numero.set(numero)
        self.var_nome.set(nome)
        self.var_partido.set(partido)
        self.var_vice.set(vice)
        self.var_situacao.set(situacao)

    def limpar(self):
        self.selecionado = None
        for variavel in (self.var_numero, self.var_nome, self.var_partido, self.var_vice):
            variavel.set("")
        self.var_situacao.set("APTO")
        self.tabela.selection_remove(self.tabela.selection())

    def atualizar(self):
        self.tabela.delete(*self.tabela.get_children())
        for c in self.db.listar_candidatos():
            tags = () if c["situacao"] == "APTO" else ("inapto",)
            self.tabela.insert("", "end", iid=str(c["id"]), tags=tags, values=(
                c["numero"], c["nome"], c["partido"], c["vice"], c["situacao"],
                "Sim" if c["no_segundo_turno"] else "-"))


# =====================================================================
# Aba 3 - ELEITORES (CRUD)
# =====================================================================
class AbaEleitores(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=15)
        self.app = app
        self.db = app.db
        self.selecionado = None

        formulario = ttk.LabelFrame(self, text=" Dados do eleitor ", padding=12)
        formulario.pack(fill="x")
        self.var_titulo = tk.StringVar()
        self.var_nome = tk.StringVar()
        self.var_secao = tk.StringVar()
        ttk.Label(formulario, text="Título (12 dígitos):").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(formulario, textvariable=self.var_titulo, width=16).grid(row=0, column=1, sticky="w", padx=(0, 20))
        ttk.Label(formulario, text="Nome:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        ttk.Entry(formulario, textvariable=self.var_nome, width=32).grid(row=0, column=3, sticky="w", padx=(0, 20))
        ttk.Label(formulario, text="Seção:").grid(row=0, column=4, sticky="w", padx=(0, 6))
        ttk.Entry(formulario, textvariable=self.var_secao, width=8).grid(row=0, column=5, sticky="w")

        botoes = ttk.Frame(self)
        botoes.pack(fill="x", pady=10)
        ttk.Button(botoes, text="➕ Cadastrar", style="Primario.TButton", command=self.cadastrar).pack(side="left")
        ttk.Button(botoes, text="✏ Alterar", command=self.alterar).pack(side="left", padx=6)
        ttk.Button(botoes, text="🗑 Excluir", style="Perigo.TButton", command=self.excluir).pack(side="left")
        ttk.Button(botoes, text="Limpar campos", command=self.limpar).pack(side="left", padx=6)

        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_: self.atualizar())
        ttk.Entry(botoes, textvariable=self.var_busca, width=24).pack(side="right")
        ttk.Label(botoes, text="🔍 Pesquisar:").pack(side="right", padx=4)

        colunas = ("titulo", "nome", "secao", "turno1", "turno2")
        titulos = ("Título", "Nome", "Seção", "Votou 1º turno", "Votou 2º turno")
        larguras = (130, 260, 70, 120, 120)
        self.tabela = ttk.Treeview(self, columns=colunas, show="headings", height=13)
        for coluna, titulo, largura in zip(colunas, titulos, larguras):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura, anchor="w" if coluna == "nome" else "center")
        self.tabela.tag_configure("votou", foreground=VERDE)
        self.tabela.pack(fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.selecionar)

        self.lbl_resumo = ttk.Label(self, text="")
        self.lbl_resumo.pack(anchor="w", pady=(8, 0))

    def _dados(self):
        return self.var_titulo.get().strip(), self.var_nome.get(), ler_inteiro(self.var_secao.get(), "Seção")

    def cadastrar(self):
        try:
            self.db.inserir_eleitor(*self._dados())
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível cadastrar", str(erro))
            return
        messagebox.showinfo("Sucesso", "Eleitor cadastrado com sucesso!")
        self.limpar()
        self.app.atualizar_tudo()

    def alterar(self):
        if self.selecionado is None:
            messagebox.showwarning("Atenção", "Selecione um eleitor na lista para alterar.")
            return
        try:
            self.db.atualizar_eleitor(self.selecionado, *self._dados())
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível alterar", str(erro))
            return
        messagebox.showinfo("Sucesso", "Eleitor alterado com sucesso!")
        self.limpar()
        self.app.atualizar_tudo()

    def excluir(self):
        if self.selecionado is None:
            messagebox.showwarning("Atenção", "Selecione um eleitor na lista para excluir.")
            return
        if not messagebox.askyesno("Confirmar exclusão", f"Excluir o eleitor {self.var_nome.get()}?"):
            return
        try:
            self.db.excluir_eleitor(self.selecionado)
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível excluir", str(erro))
            return
        messagebox.showinfo("Sucesso", "Eleitor excluído.")
        self.limpar()
        self.app.atualizar_tudo()

    def selecionar(self, _evento=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        self.selecionado = int(selecao[0])
        titulo, nome, secao, _, _ = self.tabela.item(selecao[0], "values")
        self.var_titulo.set(titulo)
        self.var_nome.set(nome)
        self.var_secao.set(secao)

    def limpar(self):
        self.selecionado = None
        for variavel in (self.var_titulo, self.var_nome, self.var_secao):
            variavel.set("")
        self.tabela.selection_remove(self.tabela.selection())

    def atualizar(self):
        self.tabela.delete(*self.tabela.get_children())
        eleitores = self.db.listar_eleitores(self.var_busca.get())
        turno = self.app.turno_atual()
        for e in eleitores:
            votou = e[f"votou_turno{turno}"]
            self.tabela.insert("", "end", iid=str(e["id"]), tags=("votou",) if votou else (), values=(
                e["titulo"], e["nome"], e["secao"],
                "✔ Sim" if e["votou_turno1"] else "Não", "✔ Sim" if e["votou_turno2"] else "Não"))
        ja_votaram = sum(1 for e in eleitores if e[f"votou_turno{turno}"])
        self.lbl_resumo.configure(
            text=f"{len(eleitores)} eleitor(es) listado(s) - {ja_votaram} já votaram no {turno}º turno.")


# =====================================================================
# Aba 4 - APURAÇÃO
# =====================================================================
class AbaApuracao(ttk.Frame):
    CORES_BARRAS = ("#0b3d91", "#1e8f3e", "#e07b00", "#7b2cbf", "#b3261e", "#00838f", "#5d4037")

    def __init__(self, master, app):
        super().__init__(master, padding=15)
        self.app = app
        self.db = app.db
        self.resultado = None

        topo = ttk.Frame(self)
        topo.pack(fill="x")
        ttk.Label(topo, text="Turno:").pack(side="left")
        self.var_turno = tk.IntVar(value=1)
        for turno in (1, 2):
            ttk.Radiobutton(topo, text=f"{turno}º turno", value=turno, variable=self.var_turno,
                            command=self.atualizar).pack(side="left", padx=6)
        ttk.Button(topo, text="🔄 Atualizar", command=self.atualizar).pack(side="left", padx=10)
        ttk.Button(topo, text="🧹 Nova eleição", style="Perigo.TButton", command=self.nova_eleicao).pack(side="right")
        ttk.Button(topo, text="📄 Emitir boletim de urna", command=self.emitir_boletim).pack(side="right", padx=6)
        self.botao_segundo_turno = ttk.Button(topo, text="▶ Iniciar 2º turno", style="Primario.TButton",
                                              command=self.iniciar_segundo_turno)
        self.botao_segundo_turno.pack(side="right")

        self.lbl_resumo = ttk.Label(self, text="", font=("Segoe UI", 10))
        self.lbl_resumo.pack(anchor="w", pady=10)

        meio = ttk.Frame(self)
        meio.pack(fill="both", expand=True)
        colunas = ("pos", "numero", "nome", "partido", "votos", "perc")
        titulos = ("#", "Número", "Candidato", "Partido", "Votos", "% válidos")
        larguras = (35, 65, 190, 70, 60, 80)
        self.tabela = ttk.Treeview(meio, columns=colunas, show="headings", height=10)
        for coluna, titulo, largura in zip(colunas, titulos, larguras):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura, anchor="w" if coluna == "nome" else "center")
        self.tabela.tag_configure("eleito", background="#d7f5df")
        self.tabela.pack(side="left", fill="y")

        self.grafico = tk.Canvas(meio, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.grafico.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.grafico.bind("<Configure>", lambda e: self.desenhar_grafico())

        self.lbl_resultado = tk.Label(self, text="", font=("Segoe UI", 12, "bold"), bg=AZUL_CLARO,
                                      fg=AZUL, justify="left", anchor="w", padx=14, pady=12)
        self.lbl_resultado.pack(fill="x", pady=(12, 0))

    def atualizar(self):
        turno = self.var_turno.get()
        self.resultado = r = apuracao.apurar(self.db, turno)
        comparecimento = len(self.db.listar_eleitores())
        self.lbl_resumo.configure(text=(
            f"Total de votos: {r['total']}   |   Válidos: {r['validos']}   |   Brancos: {r['brancos']}   |   "
            f"Nulos: {r['nulos']}   |   Eleitores cadastrados nesta urna: {comparecimento}"))

        self.tabela.delete(*self.tabela.get_children())
        for posicao, c in enumerate(r["candidatos"], start=1):
            percentual = c["votos"] / r["validos"] * 100 if r["validos"] else 0
            eleito = r["eleito"] is not None and r["eleito"]["id"] == c["id"]
            nome = c["nome"] + ("" if c["situacao"] == "APTO" else f" ({c['situacao'].lower()})")
            self.tabela.insert("", "end", tags=("eleito",) if eleito else (), values=(
                f"{posicao}º", c["numero"], nome, c["partido"], c["votos"], f"{percentual:.1f}%"))

        cores = {"ELEITO": (VERDE, "#e3f6e8"), "SEGUNDO_TURNO": (LARANJA, "#fff1dc"),
                 "EMPATE": (LARANJA, "#fff1dc"), "AGUARDANDO": (AZUL, AZUL_CLARO),
                 "SEM_VOTOS_VALIDOS": (VERMELHO, "#fde7e6")}
        frente, fundo = cores[r["situacao"]]
        icone = {"ELEITO": "🏆 ", "SEGUNDO_TURNO": "🔁 ", "AGUARDANDO": "⏳ "}.get(r["situacao"], "⚠ ")
        self.lbl_resultado.configure(text=icone + r["mensagem"], fg=frente, bg=fundo)

        pode_iniciar = (r["situacao"] == "SEGUNDO_TURNO" and turno == 1 and self.app.turno_atual() == 1)
        self.botao_segundo_turno.configure(state="normal" if pode_iniciar else "disabled")
        self.desenhar_grafico()

    def desenhar_grafico(self):
        canvas = self.grafico
        canvas.delete("all")
        if self.resultado is None:
            return
        largura, altura = canvas.winfo_width(), canvas.winfo_height()
        r = self.resultado
        barras = [(f"{c['numero']} - {c['nome'].split()[0]}", c["votos"]) for c in r["candidatos"]]
        barras += [("Brancos", r["brancos"]), ("Nulos", r["nulos"])]
        canvas.create_text(largura / 2, 16, text=f"Votos do {r['turno']}º turno", font=("Segoe UI", 11, "bold"))
        if not barras:
            return
        maior = max(v for _, v in barras) or 1
        topo, esquerda = 40, 130
        espaco = (altura - topo - 10) / len(barras)
        espessura = min(28, espaco * 0.7)
        for indice, (rotulo, votos) in enumerate(barras):
            y = topo + indice * espaco
            comprimento = (largura - esquerda - 60) * votos / maior
            cor = self.CORES_BARRAS[indice % len(self.CORES_BARRAS)] if indice < len(r["candidatos"]) else "#9e9e9e"
            canvas.create_text(esquerda - 8, y + espessura / 2, text=rotulo, anchor="e", font=("Segoe UI", 9))
            canvas.create_rectangle(esquerda, y, esquerda + comprimento, y + espessura, fill=cor, outline="")
            canvas.create_text(esquerda + comprimento + 6, y + espessura / 2, text=str(votos), anchor="w",
                               font=("Segoe UI", 9, "bold"))

    def iniciar_segundo_turno(self):
        if not messagebox.askyesno("Segundo turno", "Encerrar o 1º turno e iniciar a votação do 2º turno?"):
            return
        try:
            finalistas = apuracao.iniciar_segundo_turno(self.db)
        except ErroUrna as erro:
            messagebox.showerror("Erro", str(erro))
            return
        nomes = "\n".join(f"  {c['numero']} - {c['nome']} ({c['partido']})" for c in finalistas)
        messagebox.showinfo("2º turno iniciado", f"Candidatos no 2º turno:\n{nomes}\n\n"
                                                 "Os eleitores já podem votar novamente na aba 'Urna'.")
        self.var_turno.set(2)
        self.app.atualizar_tudo()

    def nova_eleicao(self):
        if not messagebox.askyesno("Nova eleição", "Isso APAGA todos os votos e libera os eleitores.\n"
                                                   "Candidatos e eleitores cadastrados são mantidos.\n\nContinuar?",
                                   icon="warning"):
            return
        self.db.zerar_votacao()
        self.var_turno.set(1)
        self.app.atualizar_tudo()
        messagebox.showinfo("Nova eleição", "Votação zerada. A urna está pronta para o 1º turno.")

    def emitir_boletim(self):
        r = self.resultado
        eleicao = self.db.obter_eleicao()
        agora = datetime.now()
        linhas = [
            "=" * 52, "             BOLETIM DE URNA - ELEIÇÕES 2024", "=" * 52,
            f"Município: {eleicao['municipio']}",
            f"Regra: {apuracao.descricao_regra(eleicao)}",
            f"Turno: {r['turno']}º    Emitido em: {agora:%d/%m/%Y %H:%M:%S}", "-" * 52,
            f"{'Nº':<4}{'CANDIDATO':<28}{'PARTIDO':<9}{'VOTOS':>6}", "-" * 52,
        ]
        for c in r["candidatos"]:
            linhas.append(f"{c['numero']:<4}{c['nome'][:27]:<28}{c['partido']:<9}{c['votos']:>6}")
        linhas += ["-" * 52, f"Votos válidos: {r['validos']}", f"Votos brancos: {r['brancos']}",
                   f"Votos nulos:   {r['nulos']}", f"TOTAL:         {r['total']}", "-" * 52,
                   r["mensagem"], "=" * 52]
        nome_arquivo = f"boletim_turno{r['turno']}_{agora:%Y%m%d_%H%M%S}.txt"
        caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), nome_arquivo)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write("\n".join(linhas))
        messagebox.showinfo("Boletim emitido", f"Boletim de urna salvo em:\n{caminho}")


# =====================================================================
# Aba 5 - CONFIGURAÇÃO DA ELEIÇÃO
# =====================================================================
class AbaConfiguracao(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=15)
        self.app = app
        self.db = app.db

        quadro = ttk.LabelFrame(self, text=" Dados do município ", padding=15)
        quadro.pack(fill="x")
        self.var_municipio = tk.StringVar()
        self.var_total = tk.StringVar()
        self.var_capital = tk.BooleanVar()
        ttk.Label(quadro, text="Município:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(quadro, textvariable=self.var_municipio, width=32).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(quadro, text="Total de eleitores do município:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(quadro, textvariable=self.var_total, width=14).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Checkbutton(quadro, text="É capital do estado", variable=self.var_capital).grid(
            row=2, column=1, sticky="w", padx=8, pady=5)
        ttk.Button(quadro, text="💾 Salvar", style="Primario.TButton", command=self.salvar).grid(
            row=3, column=1, sticky="w", padx=8, pady=(10, 0))

        explicacao = (
            "Como funciona a regra (Resolução TSE nº 23.677/2021, alterada pela nº 23.731/2024):\n\n"
            "• Municípios com até 200 mil eleitores: MAIORIA SIMPLES — quem tiver mais votos é eleito,\n"
            "  sem segundo turno.\n"
            "• Capitais e municípios com mais de 200 mil eleitores: MAIORIA ABSOLUTA — é preciso ter mais da\n"
            "  metade dos votos válidos. Se ninguém conseguir, há 2º turno entre os dois mais votados.\n"
            "• Se um finalista morrer, desistir ou ficar impedido antes do 2º turno, é convocado o\n"
            "  remanescente com a maior votação (altere a situação do candidato na aba 'Candidatos').\n"
            "• Votos brancos e nulos não são votos válidos.\n"
            f"• Para garantir a apuração, são exigidos no mínimo {apuracao.MINIMO_VOTOS} votos por turno.\n"
            "• Cada eleitor vota uma única vez por turno; o voto é secreto (não fica ligado ao eleitor)."
        )
        ttk.Label(self, text=explicacao, justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=15)

        self.lbl_regra = ttk.Label(self, text="", font=("Segoe UI", 11, "bold"), foreground=AZUL)
        self.lbl_regra.pack(anchor="w")

    def salvar(self):
        try:
            total = ler_inteiro(self.var_total.get(), "Total de eleitores")
            self.db.atualizar_eleicao(self.var_municipio.get(), total, self.var_capital.get())
        except ErroUrna as erro:
            messagebox.showerror("Não foi possível salvar", str(erro))
            return
        messagebox.showinfo("Sucesso", "Configuração da eleição atualizada!")
        self.app.atualizar_tudo()

    def atualizar(self):
        eleicao = self.db.obter_eleicao()
        self.var_municipio.set(eleicao["municipio"])
        self.var_total.set(str(eleicao["total_eleitores_municipio"]))
        self.var_capital.set(bool(eleicao["capital"]))
        self.lbl_regra.configure(text=f"Regra aplicada nesta eleição: {apuracao.descricao_regra(eleicao)}")


# =====================================================================
# JANELA PRINCIPAL
# =====================================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = BancoDeDados()
        self.title("Urna Eletrônica - Eleições Municipais 2024")
        self.geometry("1100x720")
        self.minsize(1000, 680)
        self.configure(bg="white")
        self._estilos()

        cabecalho = tk.Frame(self, bg=AZUL, padx=18, pady=10)
        cabecalho.pack(fill="x")
        tk.Label(cabecalho, text="🗳  URNA ELETRÔNICA  •  ELEIÇÕES 2024", bg=AZUL, fg="white",
                 font=FONTE_TITULO).pack(side="left")
        self.lbl_status = tk.Label(cabecalho, text="", bg=AZUL, fg="#cfdcff", font=("Segoe UI", 10))
        self.lbl_status.pack(side="right")

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=10, pady=10)
        self.aba_urna = AbaUrna(self.abas, self)
        self.aba_candidatos = AbaCandidatos(self.abas, self)
        self.aba_eleitores = AbaEleitores(self.abas, self)
        self.aba_apuracao = AbaApuracao(self.abas, self)
        self.aba_configuracao = AbaConfiguracao(self.abas, self)
        self.abas.add(self.aba_urna, text="  🗳 Urna  ")
        self.abas.add(self.aba_candidatos, text="  👤 Candidatos  ")
        self.abas.add(self.aba_eleitores, text="  🪪 Eleitores  ")
        self.abas.add(self.aba_apuracao, text="  📊 Apuração  ")
        self.abas.add(self.aba_configuracao, text="  ⚙ Configuração  ")

        self.bind_all("<Key>", self._tecla)
        self.protocol("WM_DELETE_WINDOW", self.sair)
        self.atualizar_tudo()

    def _estilos(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(".", font=FONTE, background="white")
        estilo.configure("TNotebook", background="white")
        estilo.configure("TNotebook.Tab", font=("Segoe UI", 11), padding=(10, 6))
        estilo.map("TNotebook.Tab", background=[("selected", AZUL_CLARO)], foreground=[("selected", AZUL)])
        estilo.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=AZUL)
        estilo.configure("Treeview", rowheight=26, font=FONTE)
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=AZUL_CLARO)
        estilo.configure("TButton", padding=(10, 5))
        estilo.configure("Primario.TButton", background=AZUL, foreground="white")
        estilo.map("Primario.TButton", background=[("disabled", "#9aa9c7"), ("active", "#123f9e")])
        estilo.configure("Perigo.TButton", background=VERMELHO, foreground="white")
        estilo.map("Perigo.TButton", background=[("active", "#8e1d17")])
        estilo.configure("Horizontal.TProgressbar", background=VERDE, troughcolor="#e6e6e6")

    def _tecla(self, evento):
        if self.abas.select() == str(self.aba_urna) and not isinstance(evento.widget, (tk.Entry, ttk.Entry)):
            self.aba_urna.tecla(evento)

    def turno_atual(self):
        return self.db.obter_eleicao()["turno_atual"]

    def atualizar_tudo(self):
        eleicao = self.db.obter_eleicao()
        self.lbl_status.configure(text=(
            f"{eleicao['municipio']}  •  {eleicao['total_eleitores_municipio']:,} eleitores".replace(",", ".")
            + f"  •  {apuracao.descricao_regra(eleicao)}  •  {eleicao['turno_atual']}º turno"))
        self.aba_urna.atualizar()
        self.aba_candidatos.atualizar()
        self.aba_eleitores.atualizar()
        self.aba_apuracao.atualizar()
        self.aba_configuracao.atualizar()

    def sair(self):
        self.db.fechar()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
