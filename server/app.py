from openenv.core.env_server import create_fastapi_app
from server.sre_environment import SREEnvironment
from sre_incident_env.models import SREAction, SREObservation

app = create_fastapi_app(SREEnvironment, SREAction, SREObservation)


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
