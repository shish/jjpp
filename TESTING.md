# JJ-PR Integration Testing

```bash
docker compose up -d
docker compose ps    # wait and repeat until containers are healthy

# Initialise phabricator
docker compose exec phabricator /opt/phabricator/bin/config set mysql.host phabricator-mysql
docker compose exec phabricator /opt/phabricator/bin/config set mysql.user root
docker compose exec phabricator /opt/phabricator/bin/config set mysql.pass phabricator
docker compose exec phabricator /opt/phabricator/bin/config set phabricator.base-uri http://phab.localhost:8081/
docker compose exec phabricator /opt/phabricator/bin/storage upgrade --force
docker compose exec phabricator /opt/phabricator/bin/phd start

# Create initial user with username "admin"
open "http://phab.localhost:8081/"

# Create an API token in user settings
open "http://phab.localhost:8081/settings/user/admin/page/apitokens/"
export PHABRICATOR_API_TOKEN=...

# Create test-repo-p / PTEST / trp in Diffusion, Activate it
open "http://phab.localhost:8081/diffusion/query/active/"


# Create an API token and set an SSH key in user settings
open "http://gerrit.localhost:8080/settings/#HTTPCredentials"
export GERRIT_API_TOKEN=...

# create test-repo-g in gerrit
ssh -p 29418 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    admin@localhost gerrit create-project --empty-commit test-repo-g

# Automatic test to ensure all of the above were done correctly
uv run pytest -v --no-cov tests/integration

# Delete test environment
docker compose down -v
```
