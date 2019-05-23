# PS Utilities
- Can update a db with a list of companies and their working endpoints (/update).
- Returns json or table html for ajax requests  ie field4=json or field4=table
- can use a plugin to update your ERP order status
- has forms for manual use
## to setup the database to test or run on production, it needs to be accessible to the local run (see # create db and admin user) or follow steps for docker-compose

## clone repository
`git clone https://github.com/VernonCo/ps_utils.git`

##To run locally or use with vscode
first create venv
`python3 -m venv venv`

activeate venv
`source venv/bin/activate`
to deactivate:
deactivate

install requirements into virtualenv
```
pip install --upgrade pip
pip install -r requirements.txt
```
run locally on vscode using F5 and view at http://localhost:5000 or in terminal using venv:
`python run.py`


## to run docker container with [docker-compose](https://docs.docker.com/compose/install/)
`docker-compose [-f dev-docker-compose.yml] up -d`

if using [weavenet](https://www.weave.works/oss/net/) to provide secure WAN to databases etc.
`docker-compose $(weave config) [-f dev-docker-compose.yml] up -d`

docker-compose files have the option of running the db as a container or comment out db and adminer services and set variables in for remote db access...make sure of persistent volume for production if running in k8 or similar

##create admin user to view additional tabs in web page
in other words, this needs ran to access the utilities.
### local
```
export FLASK_APP="app:app"
flask fab create-admin
```
### on container
```
docker exec -it ps_utils[_dev] bash
flask fab create-admin
```


## if using vscode...set interpeter the one with the path to the venv
ctl+shft+p
python:select interpeter
### add pylint in venv terminal
`pip install pylint`

### set path on vscode to run file locally (will need local database connection in config file)
> Debug > Open current configurations
add following to end of configurations if not one created for Python: Flask
```
        ,{
            "name": "Flask",
            "type": "python",
            "request": "launch",
            "stopOnEntry": false,
            "program": "${workspaceFolder}/venv/bin/flask",
            "envFile": "${workspaceFolder}/../.env",
            "args": [
                "run",
                "--no-debugger",
                "--no-reload"
            ],
            "debugOptions": [
                "WaitOnAbnormalExit",
                "WaitOnNormalExit",
                "RedirectOutput"
            ]
        }
```
### add to ../.env to keep envirnoment variables out of your code
```
FLASK_APP=ps_utils/run.py
DB_AUTH=youruser
DB_PASS=yourpassword
DB_HOST=yourhost
DB_PORT=yourhostport
SERVER_PATH=/path to/ps_utils
CONFIG_FILE='config'   # or setup config-4passwords to move existing credentials
#for passwords move
OLD_DB_AUTH=youruser
OLD_DB_PASS=yourpassword
OLD_DB_HOST=yourhost
OLD_DB_PORT=yourhostport

```

## requests conditional sequence
- 1st call using local wsdl and inject location
- else on error: call using remote wsdl
- else on error: call using remote wsdl and inject location
