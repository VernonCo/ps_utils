# Can update a db with a list of companies and their working endpoints (/update).
# Returns json for PS Service POST requests
# can use a plugin to update your ERP

# first create venv to be able to run flask fab <command>
python3 -m venv ps_utils

#activeate venv
source ps_utils/bin/activate
# to deactivate:
deactivate

# install requirements into virtualenv
pip install --upgrade pip
pip install -r requirements.txt

# create db and admin user before running locally or in container (both need to use same db host)
edit db connection in config & config-local or export DB_AUTH, etc.
flask fab create-db
flask fab create-admin

#run locally
flask run

#run container
# we use weavenet to provide secure WAN to databases etc.
docker-compose $(weave config) -f dev-docker-compose.yml up
#regular (will need local database connection) or add db service to docker-compose.yml
docker-compose -f dev-docker-compose.yml up

#set interpeter in vscode
ctl+shft+p
python:select interpeter
pip install pylint
#select the one with the path to the venv

# set path on vscode to run file locally (will need local database connection)
Debug > Open current configurations
# add following to end of configurations if not one created for Python: Flask
        ,{
            "name": "Python: Flask",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {
                "FLASK_APP": "app:create_app('config-local')"
            },
            "args": [
                "run",
                "--no-debugger",
                "--no-reload"
            ],
            "jinja": true
        }
