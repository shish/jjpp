# JJ PR Phabricator Integration

- assumes you have an API token in `~/.arcrc`:
  - `{"hosts": {"https://phabricator.mycompany.com/api/": {"token": "<api-token>"}}}`
- assumes your git remote is set to `https://phabricator.mycompany.com/source/<project>.git`
- assumes your repo contains a `.arcconfig` file with properties set:
  - `repository.callsign`
  - `phabricator.uri` (optional, will default to the host in the git remote)
  - `arc.land.onto.default` (optional, will default to remote `HEAD`)
