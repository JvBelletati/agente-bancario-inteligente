"""Gera os CSVs base (clientes e tabela de score→limite)."""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CLIENTES = [
    ("12345678901", "Ana Souza",      "1990-05-14",  2000.00, 620),
    ("23456789012", "Bruno Lima",     "1985-11-02",  5000.00, 710),
    ("34567890123", "Carla Dias",     "1998-03-27",  1000.00, 280),
    ("45678901234", "Diego Alves",    "1979-07-19", 15000.00, 865),
    ("56789012345", "Elaine Rocha",   "1993-09-08",  3000.00, 540),
    ("67890123456", "Felipe Nunes",   "2000-01-30",   800.00, 150),
    ("78901234567", "Gabriela Mota",  "1988-12-12",  8000.00, 780),
    ("89012345678", "Henrique Pires", "1995-06-05",  2500.00, 460),
    ("90123456789", "Isabela Cruz",   "1982-04-22", 12000.00, 830),
    ("01234567890", "João Reis",      "1975-08-17",   500.00, 390),
]

SCORE_LIMITE = [
    (0,   299,   500.00),
    (300, 499,  2000.00),
    (500, 699,  5000.00),
    (700, 849, 15000.00),
    (850, 1000, 50000.00),
]


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "clientes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cpf", "nome", "data_nascimento", "limite_atual", "score"])
        w.writerows(CLIENTES)
    with open(DATA_DIR / "score_limite.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score_min", "score_max", "limite_maximo"])
        w.writerows(SCORE_LIMITE)
    print(f"Gerados {len(CLIENTES)} clientes e {len(SCORE_LIMITE)} faixas de score.")


if __name__ == "__main__":
    main()
