from rich.console import Console
import redis
import typer
from typer import Argument, Option
from typing import Dict, List, Tuple
from typing_extensions import Annotated
import yaml

from xp_rtr import VERSION
from xp_rtr.utils.loaders import (
    CohortStrategyAssignemtLoader,
    ServiceLoader,
)

app = typer.Typer(no_args_is_help=True)

console = Console()
err_console = Console(stderr=True)

@app.command(name="version")
def version():
    console.print(f"Version: {VERSION}")

def _parse_client_id_ranges(client_id_ranges: List[str]) -> List[Tuple[int, int]]:
    """
    Parse the client id and/or id ranges into (min, max) tuples.  If the client id is a single value,
    then min and max will be the same.

    Args:
      client_id_ranges(List[str]): list of client ids or client id ranges. e.g. 7777 or 8888-9999

    Returns:
        List[Tuple[int, int]]: list of (min, max) tuples.
    """

    parsed_ranges = []
    for range_str in client_id_ranges:
        if "-" in range_str:
            min_client_id, max_client_id = map(int, range_str.rstrip(",").split("-"))
        else:
            min_client_id = max_client_id = int(range_str.strip(","))
        parsed_ranges.append((min_client_id, max_client_id))

    # for neatness sort the ranges
    parsed_ranges.sort(key=lambda x: x[0])

    # Check for range overlaps to avoid duplication
    for i in range(len(parsed_ranges) - 1):
        current_range = parsed_ranges[i]
        next_range = parsed_ranges[i + 1]
        if current_range[1] >= next_range[0]:
            err_console.print(f"[red]ERROR[/red]: Overlapping client id ranges: {current_range} and {next_range}")
            raise typer.Exit(code=1)

    return parsed_ranges

def _assign_cohorts_mod100(client_id_ranges: List[Tuple[int, int]]) -> Dict[str, List[int]]:
    """
    Assign cohorts using the mod100 strategy.
    Cohort names follow the pattern "00", "01", "02", ..., "99".

    Args:
        client_id_ranges(List[Tuple[int, int]]): list of (min, max) tuples.

    Returns:
        Dict[str, List[int]]: dictionary of cohort name and list of client ids.
    """
    cohort_assignments = {}
    for min_client_id, max_client_id in client_id_ranges:
        for client_id in range(min_client_id, max_client_id + 1):
            cohort_name = f"mod100-cohort-{client_id % 100:02d}"
            if cohort_name not in cohort_assignments:
                cohort_assignments[cohort_name] = []
            cohort_assignments[cohort_name].append(client_id)
    return cohort_assignments

def _dump_cohort_assignments(cohort_assignments: Dict[str, List[int]], format:str='yaml') -> None:
    """
    Dump the set of cohort assignments to stdout

    Args:
      chort_assignments(Dict[str, List[int]]): dictionary of cohort name and list of client ids.
      format(str): output format. Defaults to 'yaml'.
    
    Returns:
      None
    """

    # convert the dictionany to use explicit keys
    cohort_output = {
        "cohort-strategy-name": "mod100",
        "cohorts": [], # the list of cohorts
    }

    for cohort_name, client_ids in cohort_assignments.items():
        cohort_output["cohorts"].append({
            "cohort-name": cohort_name,
            "client-ids": client_ids
        })
    
    yaml_string = yaml.dump(cohort_output, sort_keys=False)
    console.print('---')
    console.print(yaml_string)
    


@app.command(name="assign-cohorts")
def assign_cohorts(
        client_id_ranges: Annotated[List[str], Argument(help="list of client ids or client id ranges. e.g. 7777 or 8888-9999")], 
        cohort_strategy: Annotated[ str, Option(
                                      "--strategy", "-s",
                                      help="Cohort strategy to use for cohort assignment.") ] = "mod100",
    ):
    """
    Generate a yaml snippet containing a cohort assignment for a set of client ids.

    Yaml schema:\n
        |cohort-strategy-name: <cohort-strategy-name>\n
        |cohorts:\n
        | - cohort-name: <cohort-name>\n
        |   client-ids:\n
        |     - <client-id>\n
        |     - <client-id>\n
        |     - <client-id>
    """
    supported_cohort_strategies = [ "mod100", "random" ]
    if cohort_strategy not in supported_cohort_strategies:
        err_console.print(f"[red]ERROR[/red]: Unsupported cohort strategy: {cohort_strategy}. Supported strategies: {supported_cohort_strategies}")
        raise typer.Exit(code=1)

    # an array of min/max tuples, e.g. [ (1, 3), (5, 5), (8, 10) ]
    client_id_range_tuples = _parse_client_id_ranges(client_id_ranges)
    err_console.print(f"client_id_ranges: {client_id_range_tuples}")

    err_console.print(f"Assigning cohorts using strategy \"{cohort_strategy}\"...")
    if cohort_strategy == "mod100":
        # assign cohorts using mod100 strategy
        cohort_assignments = _assign_cohorts_mod100(client_id_range_tuples)

    # dump the cohort assignment lists
    _dump_cohort_assignments(cohort_assignments)

@app.command(name="upload-cohort-assignments")
def upload_cohort_assignments(
        yaml_file: Annotated[str, Argument(help="Yaml file containing cohort assignments.")],
        redis_passwd: Annotated[str, Option(
                                      "--passwd", "-p",
                                      help="Redis password", envvar="REDIS_PASSWORD")]=None,
        redis_host: Annotated[str, Option(
                                      "--host", "-h",
                                      help="Redis hostname", envvar="REDIS_HOST")]="localhost",
        redis_port: Annotated[int, Option(
                                        "--port", "-P",
                                        help="Redis port", envvar="REDIS_PORT")]=6379,
    ):
    """
    Load a cohort strategy assignment map from a yaml file and upload to redis.
    redis key path: cohort-name:<cohort-strategy-name>:<client-id>
    """
    # create a loader instance
    rc = redis.Redis(host=redis_host, port=redis_port, password=redis_passwd, decode_responses=True)
    rc.ping()
    loader = CohortStrategyAssignemtLoader(rc)
    loader.load_from_yaml(yaml_file)
    console.print(f"Uploaded cohort assignments from {yaml_file} to redis.")

@app.command("upload-services")
def upload_services(
    yaml_file: Annotated[str, Argument(help="Yaml file containing cohort assignments.")],
    redis_passwd: Annotated[str, Option(
                                    "--passwd", "-p",
                                    help="Redis password", envvar="REDIS_PASSWORD")]=None,
    redis_host: Annotated[str, Option(
                                    "--host", "-h",
                                    help="Redis hostname", envvar="REDIS_HOST")]="localhost",
    redis_port: Annotated[int, Option(
                                    "--port", "-P",
                                    help="Redis port", envvar="REDIS_PORT")]=6379,
) -> None:
    """
    Load services map from a yaml file and upload to redis.
    redis key pathes:
      - cohort-strategy:<service>
      - treatment:<service>:<cohort-name>
      - treatment-details:<service>:<treatment>
    """
    # create a loader instance
    rc = redis.Redis(host=redis_host, port=redis_port, password=redis_passwd, decode_responses=True)
    rc.ping()
    loader = ServiceLoader(rc)
    loader.load_from_yaml(yaml_file)
    console.print(f"Uploaded services and treatments from \"{yaml_file}\" to redis.")

if __name__ == "__main__":
    app()
