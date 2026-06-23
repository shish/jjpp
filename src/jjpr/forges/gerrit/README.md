# JJ PR Gerrit Integration

* assumes you have an API token set in `~/.netrc` for your Gerrit host
  * `machine <gerrit-host> login <username> password <api-token>`
  * (API token from settings -> HTTP Credentials)
* assumes your git remote is set to `https://gerrit.mycompany.com/a/<project>` or `ssh://git@gerrit.mycompany.com:29142/<project>.git`
* uses JJ's `gerrit.review-url` setting
* uses JJ's `gerrit.default-remote-branch` setting
