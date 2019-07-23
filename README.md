# PS Utilities -- A JSON REST API for Promo Standard Services including forms for manual entry

-   Can update a db with a list of companies and their working endpoints (/update).
-   Returns json or table html for ajax requests  ie returnType=json or returnType=table
-   can use a plugin to update your ERP order status
-   has forms for manual use
-   can import username/passwd service authentications from previous database
-   working services: INV, ORDSTAT, OSN, PO(json POST only)

While PO's may be entered manually in a form eventually, I'm assuming that automated processes
will be the main usage, and only have it working for a json POST to /jsonpo/index  - see exampleSimplePO.json  The
json POST is validated by schema, field names, and their value types before sending a soap request.  See the 'Insturctions for PO' under the 'Info' tab on the nav bar.

The PO also only works with the docker image as it has a fix for suds-py3 included (Dockerfile line 24) - Waiting for fix to module - see https://github.com/cackharot/suds-py3/issues/41.  If you build the image your self, you must add the following lines to 171,172 in site-packages/suds/xsd/sxbase.py for it to correctly parse "ref:..." in the WSDLs

    if self.ref and self.ref in self.schema.elements.keys():
        ns = self.ref

## clone repository

`git clone https://github.com/VernonCo/ps_utils.git`

## Run locally or with docker-compose

###To run locally and/or use with vscode
first create venv
`python3 -m venv venv`

activate venv
`source venv/bin/activate`
to deactivate:
`deactivate`

install requirements into virtualenv

    pip install --upgrade pip
    pip install -r requirements.txt

run locally on vscode using F5 and view at <http://localhost:5000> or in terminal using venv:
`python run.py`

to setup the database to test or run on production, it needs to be accessible to the local run

### to run docker container with [docker-compose](https://docs.docker.com/compose/install/)

`docker-compose [-f dev-docker-compose.yml] up -d`

if using [weavenet](https://www.weave.works/oss/net/) to provide secure WAN to databases etc.
`docker-compose $(weave config) [-f dev-docker-compose.yml] up -d`

docker-compose files have the option of running the db as a container or comment out db and adminer services and set variables in for remote db access...make sure of persistent volume for production if running in k8 or similar

##create admin user to view additional tabs in web page
in other words, this needs ran to access the utilities.

### local
    export FLASK_APP="app:app"
    flask fab create-admin

### on container
    docker exec -it ps_utils[_dev] bash
    export FLASK_APP="run:app"
    flask fab create-admin

## Add available views to users

Make the app available to operators by either putting on limited network or adding users

### Behind limited network
The config.py  (or config-4passwords.py) have configuration to allow public access to the forms.
If desiring granular control over access, comment out the FAB_ROLES, and use the security model.

-   Create new roles(s) under Security > List Roles
-   Click on Security > List Roles >  edit role
-   Add 'can list on Companies', 'can show on Companies'
-   Add for any services open to role : 'can this form get on '..., 'can this form post on'..., 'menu access on'...
    ### Create users
-   Create users and assign roles under Security > List Users

### Open network
user registration and roles
    https://flask-appbuilder.readthedocs.io/en/latest/security.html
It is also possible to change the authentication to use LDAP and create roles in line with your AD groups


## if using vscode...set interpeter to the one with the path to the venv

    ctl+shft+p
    python:select interpeter

### add pylint in venv terminal

`pip install pylint`

### set path on vscode to run file locally (will need local database connection in config file)

Click Debug > Open current configurations.  Add following to end of configurations if not one created for 'Python: Flask'

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

### add to ../.env to keep envirnoment variables out of your code

    FLASK_APP=ps_utils/run.py
    DB_AUTH=youruser
    DB_PASS=yourpassword
    DB_HOST=yourhost
    DB_PORT=yourhostport
    SERVER_PATH=/path to/ps_

    CONFIG_FILE='config'   # or config-4passwords to move existing credentials
    #for passwords move
    OLD_DB_AUTH=youruser
    OLD_DB_PASS=yourpassword
    OLD_DB_HOST=yourhost
    OLD_DB_PORT=yourhostport


## Soap requests conditional sequence

-   if ORDSAT or OSN service Inject xml and location until fix for suds-py issue #41 released to pypi
-   1st call using local wsdl and inject location -- quicker retrieving local wsdl, consistent, and standard
-   else on error: call using remote wsdl -- some do not work with the standard wsdl
-   else on error: call using remote wsdl and inject location -- some have the wrong location (ie localhost) in their wsdl
