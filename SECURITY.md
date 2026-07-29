# Security policy

## Reporting a vulnerability

**Do not open a public issue.** A public issue discloses the problem to everyone
at the same moment, including anyone who would use it.

Use GitHub's private vulnerability reporting instead:

**[Report a vulnerability](https://github.com/scrollinondubs/behalfbot-plugins/security/advisories/new)**

It is enabled on this repo. The report stays visible only to the maintainer until
a fix is ready, and it gives us a private thread to ask questions in.

Expect a first response within a few days. Small project, one maintainer - please
do not read silence as dismissal. If a week passes with nothing, nudge by opening
a public issue that says only "I filed a private report, please look", with no
detail in it.

## Why this repo matters more than its size suggests

This is a plugin directory, and both chassis **fetch from it at install and
update time**. A plugin here runs with real access on someone's personal machine
- their credentials, their filesystem, their network. A malicious or careless
plugin is not a library bug, it is access to a person's life.

That shapes what is worth reporting.

## What is in scope

- **A plugin reaching something it did not declare.** The manifest's config
  schema is how an operator decides whether to enable a plugin. Anything that
  touches a credential, path, database or endpoint outside its declaration is a
  vulnerability even if it is benign in intent.
- **Anything that gets code into an install without review.** The fetch path,
  `tools/fetch-plugins.sh`, the `PLUGINS_PIN` mechanism, `registry.json`
  resolution. A way to make a chassis fetch content that a maintainer never
  merged is the highest-value report here.
- **A `setup.sh` that can be made to run something unintended**, including via a
  crafted manifest or a path that escapes the plugin directory.
- **Prompt injection through plugin-supplied content.** Skills are read by an
  agent. A `SKILL.md` or a plugin output that steers the agent into a privileged
  action is in scope.
- **Credential exposure** - anything that puts a token or key into a log, an
  error message, a committed file, or a prompt sent to a model provider.

## What is out of scope

- Findings that require an attacker to already have shell access on the machine
  running the agent. At that point they have everything.
- A plugin behaving badly *as declared*. If a plugin says in its manifest that it
  reads your email and it reads your email, that is the feature. Argue about
  whether it should exist in an issue, not a security report.
- Missing hardening with no exploit path attached, particularly automated scanner
  output pasted verbatim.
- Vulnerabilities in a plugin's third-party dependencies. Report those upstream;
  we will happily take a PR bumping a version.
- Social engineering of the maintainer.

## A note on the CI checks

This repo scans added lines for credential-shaped strings and flags fork PRs that
touch CI, hooks or the registry. Those are speed bumps for accidents, not a
defence against a determined attacker, and they are not treated as one. **The
real control is that a human reads every diff before it merges, and no submitted
code is executed during review.**

If you find a way past the scanner, that is worth telling us about, but please do
not assume the scanner was load-bearing.

## Disclosure

We would rather fix it and credit you than argue about a timeline. Tell us what
schedule you are working to and we will try to meet it. If you would like credit,
say so and how you want to be named.
