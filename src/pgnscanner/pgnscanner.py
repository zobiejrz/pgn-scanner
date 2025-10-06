import typer
from typing_extensions import Annotated
import chess
import chess.pgn
import requests
import chess.engine

class Node:
  """
  Represents one position in the opening tree.
  """
  def __init__(self, board: chess.Board):
    self.board = board.copy()
    self.children: dict[str, "Node"] = {}
    self.terminal = False

class PGNScanner:
  """
  Manages the DFS traversal and REPL loop.
  """
  def __init__(self, starting_moves=None):
    self.root = Node(chess.Board())
    self.current = self.root
    self.stack: list[tuple[str, Node]] = []  # for DFS traversal

    starting_moves = starting_moves or []
    for move_str in starting_moves:
      try:
        move = self.parse_move(move_str)
      except ValueError:
        raise typer.BadParameter(f"Bad move in this position: '{move_str}'")

      # Apply valid move
      self.root.board.push(move)

  def cmd_fen(self):
    print(self.current.board.fen())

  def cmd_add(self, moves_str: str):
    # split comma-separated SAN/UCI moves
    for move_str in moves_str.split(","):
      move_str = move_str.strip()
      try:
        move = self.parse_move(move_str)
        self._add_move(move)
      except ValueError:
        print(f"'{move_str}' is not a valid move.")

  def cmd_next(self):
    # Find a non-terminal child to visit next
    for fen, child in self.current.children.items():
      if not child.terminal:
        self.stack.append(self.current)
        self.current = child
        print(f"Moved to next node. Current FEN:\n{self.current.board.fen()}")
        return

    # If all children are terminal, backtrack
    while self.stack:
      parent = self.stack.pop()
      # find next unexplored sibling
      for fen, child in parent.children.items():
        if not child.terminal and child is not self.current:
          self.current = child
          print(f"Moved to next sibling. FEN:\n{self.current.board.fen()}")
          return
      # continue up if no unexplored siblings

    # Reached end of DFS
    print("All nodes are terminal.")
    choice = input("Would you like to output the PGN file? (y/n) ").lower()
    if choice.startswith("y"):
      filename = input("Output file name: ").strip()
      if filename:
        self.cmd_output(filename)

  def cmd_terminal(self):
    self.current.terminal = True
    print("Marked as terminal")

  def cmd_tree(self):
    """
    Display the move tree and return the number of terminal lines.
    """
    print("Current move tree:\n")

    def recurse(node: Node, depth: int = 0, prefix_moves: list[chess.Move] = []):
      lines = 0
      indent = "  " * depth

      # Terminal node (end of a line)
      if node.terminal or not node.children:
        san_line = " ".join(self.root.board.san(m) for m in prefix_moves)
        print(f"{indent}{san_line} (terminal)")
        return 1

      # Non-terminal: explore children
      for child in node.children.values():
        move = child.board.move_stack[-1]
        san_move = self.root.board.san(move) if not prefix_moves else node.board.san(move)
        print(f"{indent}{san_move}")
        lines += recurse(child, depth + 1, prefix_moves + [move])

      return lines

    total_lines = recurse(self.root)
    print(f"\nTotal lines: {total_lines}")
    return total_lines

  def cmd_output(self, filename: str):
    print(f"Writing PGN database to {filename} ...")

    games: list[chess.pgn.Game] = []

    def dfs(node: Node, moves: list[chess.Move]):
      # If node is terminal, write out a game
      if node.terminal or not node.children:
        game = chess.pgn.Game()
        board = chess.Board()
        node_ptr = game
        for move in moves:
          node_ptr = node_ptr.add_variation(move)
          board.push(move)
        games.append(game)
      else:
        for child in node.children.values():
          # Determine move that leads to this child
          move = child.board.move_stack[-1]
          dfs(child, moves + [move])

    dfs(self.root, [])

    # Write all games to file
    with open(filename, "w") as f:
      for game in games:
        print(game, file=f, end="\n\n")

    print(f"✅ Wrote {len(games)} games to {filename}")

  def parse_move(self, move_str: str) -> chess.Move:
    # Try SAN first, then UCI
    try:
      return self.current.board.parse_san(move_str)
    except ValueError:
      return chess.Move.from_uci(move_str)
  
  def _add_move(self, move: chess.Move):
    new_board = self.current.board.copy()
    new_board.push(move)
    key = new_board.fen()
    if key not in self.current.children:
      self.current.children[key] = Node(new_board)
    print(f"Added move: {move.uci()}")

  def cmd_print(self):
    """
    Pretty-print current node information: board, FEN, move stack.
    """
    board = self.current.board

    # Header
    print("\033[1;34m=== Current Position ===\033[0m")  # bold blue
    print(f"\033[1;33mFEN:\033[0m {board.fen()}")      # yellow FEN

    # Board (ASCII)
    print("\n\033[1;32mBoard:\033[0m")  # green label
    print(board.unicode(borders=True))  # prettier chess board

    # Terminal status
    status = "Terminal" if self.current.terminal else "Non-terminal"
    print(f"\nStatus: {status}\n")

  def cmd_top(self, X: int = 5):
    """
    Show top X moves for the current position from Lichess, sorted by engine evaluation.
    Negative X shows the most common worst moves.
    """
    fen = self.current.board.fen()
    print(f"Fetching move stats for FEN:\n{fen}")

    # Step 1: Query Lichess
    response = requests.get(
      "https://explorer.lichess.ovh/lichess",
      params={
        "variant": "standard",
        "fen": fen,
        "speeds": "blitz,rapid",
        "ratings": "1200,1400,1600,1800,2000",
        "moves": "20",
        "topGames": "0",
        "recentGames": "0",
        "history": "false"
        }
      )
    if response.status_code != 200:
      print("Error fetching Lichess stats")
      print(response)
      print(response.text)
      return
    print("Got response from lichess")
    moves_stats = response.json()["moves"]

    if not moves_stats:
      print("No data available for this position")
      return

    # Step 2: Evaluate each move with Stockfish
    engine_path = "stockfish"
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    engine.configure({"Threads": 4})

    results = []
    board = self.current.board
    print("Starting stockfish analysis")
    for move_data in moves_stats:
      move = chess.Move.from_uci(move_data["uci"])
      if move not in board.legal_moves:
          continue

      # engine evaluation
      info = engine.analyse(board, chess.engine.Limit(depth=15), root_moves=[move])
      score = info["score"].white().score(mate_score=100000)

      # temporary value used for sorting
      if self.current.board.turn == chess.WHITE:
        score_for_sort = score
      else:
        score_for_sort = -score

      popularity = move_data["white"] + move_data["black"] + move_data["draws"]

      results.append({
        "san": move_data["san"],
        "uci": move_data["uci"],
        "popularity": popularity,
        "score": score,
        "score_for_sort": score_for_sort
      })

    engine.quit()

    # Step 3: sort
    display_X = X
    if X > 0:
      results.sort(key=lambda r: (-r["score_for_sort"], -r["popularity"]))
    else:
      results.sort(key=lambda r: (r["score_for_sort"], -r["score"]))
      display_X = -X

    # Step 4: print top X
    print(f"{"Worst" if X < 0 else "Best"} {display_X} moves for {"white" if self.current.board.turn else "black"}:")
    for r in results[:display_X]:
      eval_str = f"{r['score']/100:.2f}" if r["score"] is not None else "Mate"
      print(f"{r['san']:6} | popularity={r['popularity']:5} | eval={eval_str}")

  def run(self):
    """
    Interactive loop
    """
    print("Entering PGN scanner interactive mode.")
    print("Type a command (print, fen, add, next, terminal, top, tree, output, quit).")

    while True:
      try:
        raw = input("> ").strip()
      except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        break

      if not raw:
        continue

      parts = raw.split(maxsplit=1)
      cmd = parts[0]
      arg = parts[1] if len(parts) > 1 else None

      if cmd == "quit":
        break
      elif cmd == "fen":
        self.cmd_fen()
      elif cmd == "print":
        self.cmd_print()
      elif cmd == "add" and arg:
        self.cmd_add(arg)
      elif cmd == "next":
        self.cmd_next()
      elif cmd == "terminal":
        self.cmd_terminal()
      elif cmd == "top":
        try:
          X = int(arg) if arg else 5
        except ValueError:
          print("Usage: top <X> (integer, positive or negative)")
          continue
        self.cmd_top(X)
      elif cmd == "tree":
        self.cmd_tree()
      elif cmd == "output" and arg:
        self.cmd_output(arg)
      else:
        print("Unknown command or missing argument.")

def pgnscanner(start: str = typer.Option(
    None,
    "--start",
    "-s",
    help="Comma-separated list of starting moves (SAN or UCI)"
)):
  """
  Entry function called from Typer.
  """
  # Parse starting moves into a list
  moves = [m.strip() for m in start.split(",")] if start else []
  
  try:
    scanner = PGNScanner(starting_moves=moves)
  except typer.BadParameter as e:
    typer.echo(f"{e}", err=True)
    return
  scanner.run()