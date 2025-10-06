import typer

from .pgnscanner import pgnscanner


app = typer.Typer()
app.command()(pgnscanner)


if __name__ == "__main__":
  app()