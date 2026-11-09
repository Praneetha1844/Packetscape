# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability** (private security advisory). Do not open a public issue for a vulnerability.

Include what you found, how to reproduce it and the version or commit. This is a personal project maintained by one person, so there is no guaranteed response time, but reports are read.

## Scope

Packetscape is an offline simulator. It reads a YAML scenario with `yaml.safe_load`, validates every field, and writes CSV and PNG files to a directory you choose. It opens no network connections and executes no code from scenario files.

In scope: unsafe parsing of scenario files, writing outside the chosen output directory, and denial of service from a small scenario file (a scenario can make a run arbitrarily long, so run untrusted files with a time limit). Out of scope: the simulated network behaviour itself.
