# cache loaders for xprtr-cli
import redis
import yaml

class BaseLoader:
    def __init__(self, redis_client: redis.client.Redis) -> None:
        self.rc = redis_client

    def load_from_yaml(self, yaml_file:str) -> None:
        """
        Implement this method in the derived class to load data from a yaml file.
        """
        pass

class CohortStrategyAssignemtLoader(BaseLoader):
    def __init__(self, redis_client: redis.client.Redis, **kwargs):
        self.cohort_stragegy = {}
        super().__init__(redis_client, **kwargs)

    def load_from_yaml(self, yaml_file:str) -> None:
        """
        Load a cohort strategy assignment map from a yaml file and upload to redis.
        redis key path: cohort-name:<cohort-strategy-name>:<client-id>
        """
        with open(yaml_file, 'r') as file:
            data = yaml.safe_load(file)
            # Process the data as needed
            self.cohort_strategy = data
        cohort_strategy_name = self.cohort_strategy['cohort-strategy-name']
        cohorts = self.cohort_strategy['cohorts']

        for cohort in cohorts:
            cohort_name = cohort['cohort-name']
            client_ids = cohort['client-ids']
            for client_id in client_ids:
                redis_key = f"cohort-name:{cohort_strategy_name}:{client_id}"
                redis_value = cohort_name

                print(f'adding cohort assignment: {redis_key} -> {redis_value}')

class ServiceLoader(BaseLoader):
    def __init__(self, redis_client: redis.client.Redis, **kwargs):
        self.services = {}
        super().__init__(redis_client, **kwargs)