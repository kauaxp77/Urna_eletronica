-- =====================================================================
--  URNA ELETRÔNICA - ELEIÇÕES MUNICIPAIS 2024 (PREFEITO)
--  Script do banco de dados (SQLite 3)
--
--  Este script é executado automaticamente pelo programa (database.py)
--  na primeira vez que ele roda, criando o arquivo "urna.db".
--  Também pode ser executado manualmente:
--      sqlite3 urna.db < script_banco_de_dados.sql
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Dados da eleição (uma única linha).
-- total_eleitores_municipio e capital definem a regra de maioria:
--   * até 200 mil eleitores e não capital -> maioria simples (turno único)
--   * capital ou mais de 200 mil eleitores -> maioria absoluta (pode ter 2º turno)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eleicao (
    id                        INTEGER PRIMARY KEY CHECK (id = 1),
    municipio                 TEXT    NOT NULL,
    total_eleitores_municipio INTEGER NOT NULL CHECK (total_eleitores_municipio > 0),
    capital                   INTEGER NOT NULL DEFAULT 0 CHECK (capital IN (0, 1)),
    turno_atual               INTEGER NOT NULL DEFAULT 1 CHECK (turno_atual IN (1, 2))
);

-- ---------------------------------------------------------------------
-- Candidatos a prefeito.
-- situacao: APTO, DESISTENTE, IMPEDIDO ou FALECIDO.
-- no_segundo_turno = 1 marca os dois candidatos que disputam o 2º turno.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidatos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    numero           INTEGER NOT NULL UNIQUE CHECK (numero BETWEEN 10 AND 99),
    nome             TEXT    NOT NULL,
    partido          TEXT    NOT NULL,
    vice             TEXT    NOT NULL,
    situacao         TEXT    NOT NULL DEFAULT 'APTO'
                     CHECK (situacao IN ('APTO', 'DESISTENTE', 'IMPEDIDO', 'FALECIDO')),
    no_segundo_turno INTEGER NOT NULL DEFAULT 0 CHECK (no_segundo_turno IN (0, 1))
);

-- ---------------------------------------------------------------------
-- Eleitores aptos a votar nesta urna.
-- votou_turno1 / votou_turno2 garantem que cada eleitor vote uma única vez
-- por turno.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eleitores (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo       TEXT    NOT NULL UNIQUE CHECK (length(titulo) = 12),
    nome         TEXT    NOT NULL,
    secao        INTEGER NOT NULL CHECK (secao > 0),
    votou_turno1 INTEGER NOT NULL DEFAULT 0 CHECK (votou_turno1 IN (0, 1)),
    votou_turno2 INTEGER NOT NULL DEFAULT 0 CHECK (votou_turno2 IN (0, 1))
);

-- ---------------------------------------------------------------------
-- Votos. Não existe ligação entre o voto e o eleitor: o sigilo do voto
-- é preservado (só se sabe QUE o eleitor votou, não EM QUEM).
-- tipo: NOMINAL (em candidato), BRANCO ou NULO.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS votos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    turno         INTEGER NOT NULL CHECK (turno IN (1, 2)),
    candidato_id  INTEGER REFERENCES candidatos (id) ON DELETE RESTRICT,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('NOMINAL', 'BRANCO', 'NULO')),
    registrado_em TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK ((tipo = 'NOMINAL' AND candidato_id IS NOT NULL)
        OR (tipo <> 'NOMINAL' AND candidato_id IS NULL))
);

-- =====================================================================
-- Dados iniciais (só são inseridos se ainda não existirem)
-- =====================================================================
INSERT OR IGNORE INTO eleicao (id, municipio, total_eleitores_municipio, capital, turno_atual)
VALUES (1, 'Águas Lindas de Goiás', 150000, 0, 1);

INSERT OR IGNORE INTO candidatos (numero, nome, partido, vice) VALUES
    (12, 'Ana Ribeiro',     'PVA', 'Carlos Menezes'),
    (25, 'Bruno Albuquerque','PNT', 'Fernanda Lima'),
    (40, 'Cláudia Santos',  'PSN', 'Rafael Duarte'),
    (77, 'Diego Fernandes', 'MPC', 'Juliana Rocha');

INSERT OR IGNORE INTO eleitores (titulo, nome, secao) VALUES
    ('000000000101', 'Amanda Costa',      101),
    ('000000000202', 'Bernardo Silva',    101),
    ('000000000303', 'Camila Oliveira',   101),
    ('000000000404', 'Daniel Souza',      101),
    ('000000000505', 'Eduarda Pereira',   102),
    ('000000000606', 'Felipe Rodrigues',  102),
    ('000000000707', 'Gabriela Almeida',  102),
    ('000000000808', 'Henrique Nunes',    102),
    ('000000000909', 'Isabela Carvalho',  103),
    ('000000001010', 'João Pedro Martins',103),
    ('000000001111', 'Larissa Gomes',     103),
    ('000000001212', 'Marcos Vinícius',   103);
