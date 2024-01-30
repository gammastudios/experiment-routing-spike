from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Query,
    HTTPException,
)
import os
from structlog import get_logger
import yaml

from jinja2 import (
    Environment,
    select_autoescape,
)

from .treatments.t1_treatment import t1_handler
from .treatments.t2_treatment import t2_handler
from .treatments.default_treatment import default_handler
from fastapi import Request

# service map from a file
service_mapping_filename = "client-cohort-map.yml"

service_client_map = {}  # lookup cohort-name by service-name & client-id
service_treatment_map = {}  # lookup treatment by service-name & cohort-name
treatment_routes = {}  # lookup treatment details by treatment-name

logger = None
jinja_env = None


def load_service_map(file_path):
    global service_client_map, service_treatment_map, logger
    current_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = os.path.join(current_dir, file_path)
    with open(relative_path, "r") as file:
        data = yaml.safe_load(file)

    # construct the service client map and service treatment map
    for svc in data:
        service_name = svc["service-name"]
        service_client_map[service_name] = {}
        for cohort in svc["service-cohorts"]:
            for client_id in cohort["client-ids"]:
                service_client_map[service_name][client_id] = cohort["cohort-name"]

        service_treatment_map[service_name] = {}
        treatment_routes[service_name] = {}
        for exp in svc["service-experiments"]:
            if "default-experiment" in exp and exp["default-experiment"] is True:
                default_exp = True
            else:
                default_exp = False
            for treatment in exp["treatments"]:
                treatment_routes[service_name][treatment["treatment-name"]] = treatment[
                    "treatment-route"
                ]
                if (
                    default_exp is True
                    and "default-treatment" in treatment
                    and treatment["default-treatment"] is True
                ):
                    treatment_routes[service_name]["default"] = treatment[
                        "treatment-route"
                    ]
                for cohort_name in treatment["assigned-cohorts"]:
                    service_treatment_map[service_name][cohort_name] = treatment[
                        "treatment-name"
                    ]

    logger.info(
        "routing config",
        service_client_map=service_client_map,
        service_treatment_map=service_treatment_map,
        treatment_routes=treatment_routes,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global logger, service_mapping_filename, jinja_env
    logger = get_logger("xp-rtr")
    load_service_map(service_mapping_filename)
    jinja_env = Environment(autoescape=False)
    yield


def treatment_route_lookup(trgt_service: str, client_id: int) -> dict:
    """
    Given a target service and client id, return the treatement route details
    """
    # get the customer to cohort mapping
    if trgt_service not in treatment_routes:
        return None
    if client_id not in service_client_map[trgt_service]:
        # return the default treatment for the service
        return treatment_routes[trgt_service]["default"]
    cohort = service_client_map[trgt_service][client_id]
    treatment = service_treatment_map[trgt_service][cohort]
    return treatment_routes[trgt_service][treatment]


app = FastAPI(lifespan=lifespan)


def render_jinja_pattern(target_route_pattern: str, client_id: int, query_string=None):
    uri_template = jinja_env.from_string(target_route_pattern)
    rendered_string = uri_template.render(client_id=client_id, query_string=query_string)
    return rendered_string


@app.get("/services/{trgt_service}")
async def handle_service(
    trgt_service: str,
    request: Request,
    client_id: str = Query(None, alias="client-id", description="Client ID"),
):
    if client_id is not None:
        client_id = int(client_id)

    # look up the treatment directly assuming flattened cohort to treatment reference table
    treatment_route = treatment_route_lookup(trgt_service, client_id)

    if treatment_route is None:
        raise HTTPException(status_code=404, detail="Not Found")

    query_params = request.query_params
    logger.info("query_params", query_params=query_params)
    target_uri = render_jinja_pattern(
        treatment_route["target-pattern"], client_id=client_id, query_string=query_params
    )

    return f"I would process treatment route: {target_uri}"
