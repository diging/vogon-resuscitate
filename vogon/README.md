# vogon-resuscitate
Resuscitated Vogon that works without Vue.js

# Setup
To run Vogon, copy and rename the following files:
- `.env_app-example` to `.env_app` and define the variables in the file.

If you are using the production docker-compose set up (`docker-compose-prod.yml`) you will have to do the same for `.env-example` and `.docker-env-example`, in which `.env` needs to contain the variables that are in required in the docker-compose file, while `.docker-env` should contain all environment variables needed inside the Docker containers.

# Startup
Run `docker compose up` inside the directory that holds the `docker-compose.yml` file.