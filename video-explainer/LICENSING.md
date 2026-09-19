# Licensing

Two third party dependencies matter here. Neither is vendored into this repo,
and that is a deliberate decision rather than an oversight.

## Why nothing is vendored

Vendoring means shipping someone else's code inside this repo and handing a
copy to every person who installs the plugin. For both dependencies that is
worse than declaring them:

1. **It would redistribute code this repo has no clear right to redistribute.**
   The Remotion Free License grants permission to *use* and to *modify for your
   own use case*. It does not grant permission to redistribute Remotion to third
   parties. Installing from npm is the path Remotion intends.

2. **It would hand a licensed dependency to people who may not be licensed.**
   Remotion is free for individuals and organizations of up to 3 people, and
   paid above that. A 40 person company installing this plugin needs a Company
   License. If the code arrived silently inside the plugin, they would be using
   it unlicensed without ever being told there was a license. The setup script
   asks instead.

3. **For ffmpeg it would pull GPL obligations onto this repo.** The common
   Homebrew build is configured `--enable-gpl --enable-version3`, and several of
   its encoders (x264, x265) are GPL. Shipping those binaries is distribution
   under the GPL and carries a corresponding-source obligation for the whole
   combined work. Calling a binary the user installed themselves does not.

So: ffmpeg comes from Homebrew, Remotion comes from npm, and `scripts/setup.sh`
installs both on the user's own machine under the user's own license.

## Remotion

Source-available, **not** OSI open source. Two tiers.

**Free License.** Individuals (personal or commercial), organizations of up to
3 people, non-profits, and anyone still evaluating. No account, no key, no
functional restrictions, commercial output allowed, automations allowed.

**Company License.** Required at 4 or more people. Two shapes:

- *Remotion for Creators*, $25/month per person writing Remotion code
- *Remotion for Automators*, $0.01 per render with a $100/month minimum

Relevant to this plugin: `npx remotion render` is explicitly named in Remotion's
definition of an automation. A non-eligible organization that wires this skill
into a recurring job is on the Automators tier, not the Creators tier. That is
the single most expensive surprise available here, so `setup.sh` says it out
loud before installing anything.

Verified against remotion.dev/docs/license/faq and the repo LICENSE.md,
2026-09-19. Licensing terms change; re-read before relying on this.

The slides path has no Remotion dependency at all and no licensing constraint
beyond ffmpeg's ordinary use. If licensing is a problem for an install, that
path still works completely.

## ffmpeg

Used by both paths, invoked as an external binary, never bundled. Homebrew's
build is GPLv3. Ordinary use of a program you installed yourself carries no
distribution obligation.

Separately, and independently of ffmpeg and Remotion: H.264 and AAC are
patent-encumbered codecs in some jurisdictions. Remotion's own FAQ disclaims
codec patent coverage. For ordinary internal explainer videos this is not
something anyone acts on, but it is on the record here rather than not.

## TTS

`scripts/tts.sh` defaults to OpenAI's TTS API, which bills per character to the
installer's own API key, and falls back to the macOS `say` command, which is
free and offline. Neither is bundled. If the host install already has a TTS
script, point `$VIDEO_EXPLAINER_TTS_BIN` at it and this one steps aside.

## This plugin's own code

Everything in `scripts/` and `remotion-template/src/` is original and carries
the repo's license. `remotion-template/` is a project scaffold: it contains a
`package.json` that names Remotion as a dependency, not a copy of Remotion.
