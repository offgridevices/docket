# Open source: AGPL for the application, Apache for the interfaces

Date: 2026-10-02. Status: settled by Shreyash, 2026-10-02.

**Chosen:** open-source the whole project under two licences, copyright OffGrid LLC.

- **The application** (kernel, agent, API service, UI, CLI, demos, scripts, docs):
  GNU Affero General Public License, version 3 only (`LICENSE`).
- **The interfaces:** Apache License 2.0 (`LICENSE-APACHE`). That covers the record
  format in `src/docket/schema/` with its generated JSON Schemas and the TypeScript types
  generated from them, the exporters in `src/docket/exports/`, the OpenAPI document the
  service serves at `/api/openapi.json`, and the research-standard data
  (`research-standards-36.yaml` and `tailorings/`), whose question text is a U.S.
  Government work.

Contributions come in under the licence of the files they change (inbound = outbound),
with no separate contributor agreement. `LICENSING.md` holds the file map; third-party
material keeps its own rights (`NOTICE.md`, `ui/src/brand/FONTS.md`, dependency metadata).
This is the split that Mattermost and Grafana use: a copyleft application with permissive
interfaces around it.

**Over:**

- **All rights reserved,** the previous posture. No outside party could inspect, run or
  contribute on any stated terms. A Government user deciding whether to rely on the tool
  had nothing to stand on beyond trusting the vendor.
- **Apache-2.0 for everything.** Maximum adoption, but anyone could take the
  application, change it and host a closed copy as a service, and the improvements would
  never come back to the people using the tool.
- **Proprietary core with only the API open,** the Lattice pattern. Integrators get a
  stable surface, but the scoring kernel, the thing a reviewer most needs to inspect,
  stays closed, and customers stay locked to one vendor's build.

**Why.**

1. **Trust and no lock-in for Government users.** Docket's claim is that a deterministic
   kernel, not the agent, produces every number and that the record proves it. That
   claim is only checkable if the kernel is open. AGPL lets any user read, run, fork and
   self-host the whole application, so no customer depends on OffGrid to keep using it.
2. **Integration with no licence friction.** Other tools need to read and write Docket
   records. Putting the record format, exporters and API description under Apache-2.0
   means a tool that only speaks those interfaces can carry any licence, closed or open,
   without asking.
3. **Hosted modifications come back.** AGPL section 13 requires anyone who runs a
   modified copy as a network service to offer its users the source. A competitor
   cannot host a closed fork and sell it as its own.

**Would reverse if:** a Government customer or prime contractor that is otherwise ready
to adopt cannot accept AGPL software under its own policy; or contributors stay away because of the
AGPL in numbers that matter; or the Apache split proves unworkable in practice, for
instance if the exporters cannot be kept usable without pulling AGPL kernel code into
every tool that wants them. Any change to the split needs a new record. Relicensing
contributions received from others would need their consent, because inbound = outbound
gives OffGrid no right to relicense them.

**Consequences recorded elsewhere.** `LICENSING.md` (the file map and a plain reading of
the AGPL), `README.md` ("Licence"), `CONTRIBUTING.md` ("Licence first"), `NOTICE.md`,
`docs/architecture.md`, the review workflow's settled-decisions list, the `license` field
in `pyproject.toml` and `ui/package.json`, and a `LICENSE.md` pointer in each
Apache-licensed folder.
