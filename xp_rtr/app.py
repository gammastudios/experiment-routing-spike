from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import Query
import yaml

from .treatments.t1_treatment import t1_handler
from .treatments.t2_treatment import t2_handler
from .treatments.default_treatment import default_handler
import os

# service map from a file
service_mapping_filename = 'client-cohort-map.yml'
service_map = {}

def load_service_map(file_path):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = os.path.join(current_dir, file_path)
    with open(relative_path, 'r') as file:
        data = yaml.safe_load(file)

    # convert the service map into a structure that makes for fast lookup ups of
    #
    # select experiment, treatment-id
    # from service_map
    # where client-id = <client-id>
    #   and service-name = <service-name>
    #
    # | client-id | service-name | cohort | experiment | treatment |

    # service.experiment.treatment.cohort

    # select treatment-details
    # from treatments
    # where treatment-id = <treatment-id>
    # | treatment | treatment-details |
    
    for svc_map in data:
        print(f"found service: {svc['service-name']}")
        service_map[svc_map['service-name']] = svc

    return data


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service_map
    service_map = load_service_map(service_mapping_filename)
    yield

def treatment_lookup(service_name, client_id):
    """
    Look up the treatment name to appliy for a given service and client combination.
    If treatment cannot be found, then a default experiment.treatment value is returned.
    e.g. "<svc>.default.default"


    Args:
        service_name (str): Name of the service being requested
        client_id (str): Client ID to look up

    Returns:
      str: Treatment name, using the format '<svc>.<experiment>.<treatment>' 
    """
    return 'svc-a.exp-a.t1'

app = FastAPI(lifespan=lifespan)
@app.get("/services/{trgt_service}")
async def handle_service(trgt_service: str, client_id: str = Query(..., alias='client-id', description="Client ID")):

    # look up the treatment directly assuming flattened cohort to treatment reference table
    treatment = treatment_lookup(trgt_service, client_id)
    print(service_map)
    match trgt_service:
        case "svc-a":
            return t1_handler(client_id)
        case _:
            return {"message": f"Handling request for service: {trgt_service}, client ID: {client_id}"}

