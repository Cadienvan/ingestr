import hashlib
from datetime import datetime
from typing import Optional

import dlt
import humanize
import typer
from rich.console import Console
from typing_extensions import Annotated

from ingestr.src.factory import SourceDestinationFactory

app = typer.Typer(
    name="ingestr",
    help="ingestr is the CLI tool to ingest data from one source to another",
    rich_markup_mode="rich",
)


console = Console()
print = console.print

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f%z",
]


@app.command()
def ingest(
    source_uri: Annotated[
        str, typer.Option(help="The URI of the [green]source[/green]")
    ],  # type: ignore
    dest_uri: Annotated[
        str, typer.Option(help="The URI of the [cyan]destination[/cyan]")
    ],  # type: ignore
    source_table: Annotated[
        str, typer.Option(help="The table name in the [green]source[/green] to fetch")
    ],  # type: ignore
    dest_table: Annotated[
        str,
        typer.Option(
            help="The table in the [cyan]destination[/cyan] to save the data into"
        ),
    ] = None,  # type: ignore
    incremental_key: Annotated[
        str,
        typer.Option(
            help="The incremental key from the table to be used for incremental strategies"
        ),
    ] = None,  # type: ignore
    incremental_strategy: Annotated[
        str,
        typer.Option(
            help="The incremental strategy to use, must be one of 'replace', 'append', 'delete+insert', or 'merge'"
        ),
    ] = "replace",  # type: ignore
    interval_start: Annotated[
        Optional[datetime],
        typer.Option(
            help="The start of the interval the incremental key will cover",
            formats=DATE_FORMATS,
        ),
    ] = None,  # type: ignore
    interval_end: Annotated[
        Optional[datetime],
        typer.Option(
            help="The end of the interval the incremental key will cover",
            formats=DATE_FORMATS,
        ),
    ] = None,  # type: ignore
    primary_key: Annotated[Optional[list[str]], typer.Option(help="The merge ")] = None,  # type: ignore
):
    if not dest_table:
        print()
        print(
            "[yellow]Destination table is not given, defaulting to the source table.[/yellow]"
        )
        dest_table = source_table

    merge_key = None
    if incremental_strategy == "delete+insert":
        merge_key = incremental_key
        incremental_strategy = "merge"

    factory = SourceDestinationFactory(source_uri, dest_uri)
    source = factory.get_source()
    destination = factory.get_destination()

    m = hashlib.sha256()
    m.update(dest_table.encode("utf-8"))

    pipeline = dlt.pipeline(
        pipeline_name=m.hexdigest(),
        destination=destination.dlt_dest(
            uri=dest_uri,
        ),
        progress=dlt.progress.log(dump_system_stats=False),
        pipelines_dir="pipeline_data",
        dataset_name="testschema",
    )

    print()
    print("[bold green]Initiated the pipeline with the following:[/bold green]")
    print(
        f"[bold yellow]  Source:[/bold yellow] {factory.source_scheme} / {source_table}"
    )
    print(
        f"[bold yellow]  Destination:[/bold yellow] {factory.destination_scheme} / {dest_table}"
    )
    print(f"[bold yellow]  Incremental Strategy:[/bold yellow] {incremental_strategy}")
    print(
        f"[bold yellow]  Incremental Key:[/bold yellow] {incremental_key if incremental_key else 'None'}"
    )
    print()

    continuePipeline = typer.confirm("Are you sure you would like to continue?")
    if not continuePipeline:
        raise typer.Abort()

    print()
    print("[bold green]Starting the ingestion...[/bold green]")
    print()

    run_info = pipeline.run(
        source.dlt_source(
            uri=source_uri,
            table=source_table,
            incremental_key=incremental_key,
            merge_key=merge_key,
            interval_start=interval_start,
            interval_end=interval_end,
        ),
        **destination.dlt_run_params(
            uri=dest_uri,
            table=dest_table,
        ),
        write_disposition=incremental_strategy,  # type: ignore
        primary_key=(primary_key if primary_key and len(primary_key) > 0 else None),  # type: ignore
    )

    elapsedHuman = ""
    if run_info.started_at:
        elapsed = run_info.finished_at - run_info.started_at
        elapsedHuman = f"in {humanize.precisedelta(elapsed)}"

    print()
    print(
        f"[bold green]Successfully finished loading data from '{factory.source_scheme}' to '{factory.destination_scheme}' {elapsedHuman} [/bold green]"
    )


@app.command()
def example_uris():
    print()
    typer.echo(
        "Following are some example URI formats for supported sources and destinations:"
    )

    print()
    print(
        "[bold green]Postgres:[/bold green] [white]postgres://user:password@host:port/dbname?sslmode=require [/white]"
    )
    print(
        "[white dim]└── https://docs.sqlalchemy.org/en/20/core/engines.html#postgresql[/white dim]"
    )

    print()
    print(
        "[bold green]BigQuery:[/bold green] [white]bigquery://project-id?credentials_path=/path/to/credentials.json&location=US [/white]"
    )
    print(
        "[white dim]└── https://github.com/googleapis/python-bigquery-sqlalchemy?tab=readme-ov-file#connection-string-parameters[/white dim]"
    )

    print()
    print(
        "[bold green]Snowflake:[/bold green] [white]snowflake://user:password@account/dbname?warehouse=COMPUTE_WH [/white]"
    )
    print(
        "[white dim]└── https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy#connection-parameters"
    )

    print()
    print(
        "[bold green]Redshift:[/bold green] [white]redshift://user:password@host:port/dbname?sslmode=require [/white]"
    )
    print(
        "[white dim]└── https://aws.amazon.com/blogs/big-data/use-the-amazon-redshift-sqlalchemy-dialect-to-interact-with-amazon-redshift/[/white dim]"
    )

    print()
    print(
        "[bold green]Databricks:[/bold green] [white]databricks://token:<access_token>@<server_hostname>?http_path=<http_path>&catalog=<catalog>&schema=<schema>[/white]"
    )
    print("[white dim]└── https://docs.databricks.com/en/dev-tools/sqlalchemy.html")

    print()
    print(
        "[bold green]Microsoft SQL Server:[/bold green] [white]mssql://user:password@host:port/dbname?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes [/white]"
    )
    print(
        "[white dim]└── https://docs.sqlalchemy.org/en/20/core/engines.html#microsoft-sql-server"
    )

    print()
    print(
        "[bold green]MySQL:[/bold green] [white]mysql://user:password@host:port/dbname [/white]"
    )
    print(
        "[white dim]└── https://docs.sqlalchemy.org/en/20/core/engines.html#mysql[/white dim]"
    )

    print()
    print("[bold green]DuckDB:[/bold green] [white]duckdb://path/to/database [/white]")
    print("[white dim]└── https://github.com/Mause/duckdb_engine[/white dim]")

    print()
    print("[bold green]SQLite:[/bold green] [white]sqlite://path/to/database [/white]")
    print(
        "[white dim]└── https://docs.sqlalchemy.org/en/20/core/engines.html#sqlite[/white dim]"
    )

    print()
    typer.echo(
        "These are all coming from SQLAlchemy's URI format, so they should be familiar to most users."
    )


def main():
    app()


if __name__ == "__main__":
    main()