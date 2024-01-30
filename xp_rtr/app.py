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

service_client_map = {} # lookup cohort-name by service-name & client-id 
service_treatment_map = {} # lookup treatment by service-name & cohort-name


def load_service_map(file_path):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = os.path.join(current_dir, file_path)
    with open(relative_path, 'r') as file:
        data = yaml.safe_load(file)

    # construct the service client map and service treatment map
    for svc in data:
        service_name = svc['service-name']
        service_client_map[service_name] = {}
        for cohort in svc['service-cohorts']:
            for client_id in cohort['client-ids']:
                service_client_map[service_name][client_id] = cohort['cohort-name']

        service_treatment_map[service_name] = {}
        for exp in svc['service-experiments']:
            for treatment in exp['treatments']:
                for cohort_name in treatment['assigned-cohorts']:
                    service_treatment_map[service_name][cohort_name] = treatment['treatment-name']

    print("client_mapping to cohort")
    print(service_client_map)
    print(service_treatment_map)


    # service.experiment.treatment.cohort

    # select treatment-details
    # from treatments
    # where treatment-id = <treatment-id>
    # | treatment | treatment-details |
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

