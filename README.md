# pgn-scanner

PGNScanner is a Python CLI tool for generating and manipulating chess PGN databases using an interactive REPL loop. It allows exploring chess positions, adding moves, marking terminal nodes, inspecting move trees, and outputting PGN files. 

It also integrates Stockfish for move evaluations and can fetch move statistics from Lichess.

## Installation

**1. Clone the repository**

**2. Install dependencies (inside a virtual environment is recommended):**

```bash
pip install -r requirements.txt
```

- Requires Python 3.9+
- Make sure [Stockfish](https://stockfishchess.org/download/) is installed and available, or provide the path to the binary in the REPL configuration.

## Usage

Run the CLI:

```bash
python -m pgnscanner.cli
```

This starts an interactive REPL loop where you can manipulate your PGN database.

You can also provide starting positions when initializing the REPL by providing the starting moves as a comma separated string and the `-s` or `--start` flag:

```bash
python -m pgnscanner.cli -s "e4, e5, Nf3, Nc6, d4"
```

## REPL Commands

|       Command        | Description |
| :------------------: | :------------ |
|         `fen`        | Displays the current node’s FEN (Forsyth–Edwards Notation) string. |
| `add <move>[,moves]` | Add one or more SAN/UCI moves from the current position. Example: `add e4, e5` |
|        `next`        | Move to the next node in the DFS search. If all nodes are terminal, prompts to output the PGN. |
|      `terminal`      | Mark the current node as terminal (no further expansion). |
|        `tree`        | Displays the move tree from the current position and returns the number of lines created. |
|   `output <file>`    | Output the PGN database to the specified file. Example: `output openings.pgn` |
|      `top <X>`       | Display the top X most common moves for the current position using Lichess master database, sorted by engine evaluation. If X is negative, shows the most common worst moves. Example: `top 5` or `top -3` |
