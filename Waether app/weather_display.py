# ============================================================
#  weather_display.py  –  Rich-powered terminal UI
# ============================================================
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.columns import Columns
from rich         import box
from rich.text    import Text

console = Console()


def _wind_direction(deg: float) -> str:
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    return dirs[round(deg / 45) % 8]


def show_banner():
    banner = Text("⛅  WEATHER FORECAST APP  ⛅", style="bold cyan")
    console.print(Panel(banner, border_style="cyan", expand=False))
    console.print()


def show_current(w: dict):
    """Pretty-print current weather."""
    title = (
        f"{w['emoji']}  {w['city']}, {w['country']}  "
        f"– {w['description']}"
    )
    body = (
        f"[bold yellow]Temperature :[/]  {w['temp']}{w['unit_sym']}  "
        f"(feels like {w['feels_like']}{w['unit_sym']})\n"
        f"[bold yellow]Min / Max   :[/]  {w['temp_min']}{w['unit_sym']} / "
        f"{w['temp_max']}{w['unit_sym']}\n"
        f"[bold yellow]Humidity    :[/]  {w['humidity']}%\n"
        f"[bold yellow]Pressure    :[/]  {w['pressure']} hPa\n"
        f"[bold yellow]Visibility  :[/]  {w['visibility']:.1f} km\n"
        f"[bold yellow]Wind        :[/]  {w['wind_speed']} {w['wind_unit']}  "
        f"{_wind_direction(w['wind_dir'])}\n"
        f"[bold yellow]Sunrise     :[/]  {w['sunrise']}     "
        f"[bold yellow]Sunset:[/]  {w['sunset']}\n"
        f"[dim]Last updated: {w['updated_at']}[/]"
    )
    console.print(Panel(body, title=title, border_style="bright_blue", expand=False))
    console.print()


def show_forecast(days: list):
    """Print 5-day forecast as a Rich table."""
    table = Table(
        title="📅  5-Day Forecast",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Date",        style="bold white",  justify="left",   min_width=14)
    table.add_column("Condition",   style="cyan",        justify="left",   min_width=18)
    table.add_column("Min Temp",    style="bold blue",   justify="center", min_width=10)
    table.add_column("Max Temp",    style="bold red",    justify="center", min_width=10)

    for d in days:
        table.add_row(
            d["date"],
            f"{d['emoji']}  {d['description']}",
            f"{d['temp_min']}{d['unit_sym']}",
            f"{d['temp_max']}{d['unit_sym']}",
        )
    console.print(table)
    console.print()


def show_error(msg: str):
    console.print(f"[bold red]Error:[/] {msg}")


def show_info(msg: str):
    console.print(f"[dim]{msg}[/]")


def show_menu() -> str:
    console.print("[bold cyan]Options:[/]")
    console.print("  [1] Search by city name")
    console.print("  [2] Auto-detect my location")
    console.print("  [3] Change units  (metric / imperial)")
    console.print("  [4] Exit")
    return console.input("\n[bold]Your choice:[/] ").strip()


def ask_city() -> str:
    return console.input("[bold]Enter city name:[/] ").strip()


def ask_units() -> str:
    choice = console.input(
        "[bold]Units — enter [M]etric, [I]mperial, or [S]tandard:[/] "
    ).strip().lower()
    mapping = {"m": "metric", "i": "imperial", "s": "standard"}
    return mapping.get(choice[0] if choice else "m", "metric")
