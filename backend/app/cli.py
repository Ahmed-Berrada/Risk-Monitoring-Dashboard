"""CLI commands for the risk dashboard backend."""

import asyncio
import sys
import click


@click.group()
def cli():
    """Risk Monitoring Dashboard CLI."""
    pass


@cli.command()
@click.option("--years", default=5, help="Number of years to backfill")
def backfill(years: int):
    """Backfill historical OHLCV and FX data."""
    from app.services.ingestion.service import backfill as run_backfill

    click.echo(f"Starting backfill for {years} years...")
    results = asyncio.run(run_backfill(years=years))
    for ticker, result in results.items():
        status = result["status"]
        rows = result.get("rows", "N/A")
        click.echo(f"  {ticker}: {status} ({rows} rows)")
    click.echo("Backfill complete.")


@cli.command()
def ingest():
    """Run a single daily ingestion cycle."""
    from app.services.ingestion.service import run_daily_ingestion

    click.echo("Running daily ingestion...")
    results = asyncio.run(run_daily_ingestion())
    for ticker, result in results.items():
        status = result["status"]
        rows = result.get("rows", "N/A")
        click.echo(f"  {ticker}: {status} ({rows} rows)")
    click.echo("Done.")


if __name__ == "__main__":
    cli()
