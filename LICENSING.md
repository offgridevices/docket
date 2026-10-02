# Licensing

Copyright (C) 2026 OffGrid LLC.

Docket is open source under two licences. The application is under the GNU Affero
General Public License, version 3 only. The interfaces, meaning the record format, the
exporters and the HTTP API description, are under the Apache License 2.0, so anyone can
build tools that read and write Docket records without a licence question. The decision
and its reasons are in
`docs/decisions/2026-10-02-licence-agpl-application-apache-interfaces.md`.

## Which licence covers which files

| Paths | Licence | Full text |
|---|---|---|
| `src/docket/schema/`, including `objects.yaml` and every generated file in `json/` | Apache-2.0 | `LICENSE-APACHE` |
| `src/docket/exports/` | Apache-2.0 | `LICENSE-APACHE` |
| `ui/src/types/objects.d.ts`, the TypeScript types generated from the JSON Schemas | Apache-2.0 | `LICENSE-APACHE` |
| The OpenAPI document the service serves at `/api/openapi.json` | Apache-2.0 | `LICENSE-APACHE` |
| `src/docket/standard/research-standards-36.yaml` and `src/docket/standard/tailorings/` | Apache-2.0 | `LICENSE-APACHE` |
| `ui/src/brand/logo/` — the Docket and OffGrid names, marks, wordmarks and lockups | Not licensed; trademarks of OffGrid LLC, all rights reserved | — |
| Everything else in this repository that OffGrid LLC wrote | AGPL-3.0-only | `LICENSE` |

In SPDX terms the project as a whole is `AGPL-3.0-only AND Apache-2.0`.

Notes on the Apache-licensed parts:

- **The OpenAPI document** is generated at run time from the route and model
  definitions in `src/docket/api/`. The document itself, and any copy of it, is under
  Apache-2.0. The code that serves the API stays under AGPL-3.0-only.
- **The research-standard data** is derived from published GAO reports. The question
  text taken from those reports is a work of the U.S. Government and is not subject to
  copyright in the United States; the Apache grant covers OffGrid's selection,
  arrangement, identifiers and annotations. The scoring rules (`rules.yaml`), the
  doctrine crosswalk (`crosswalk.yaml`) and the loading code (`__init__.py`) in the same
  folder are part of the application and stay under AGPL-3.0-only.
- **The exporters** import parts of the application: `docket.store`, `docket.kernel.render` (including the private helper `_cite_withheld_level`), `docket.kernel.scope`, `docket.objects`, `docket.canon`, and `KERNEL_VERSION` from the top-level `docket` package.
  The Apache grant covers the exporter source and the file formats they write. A
  program that runs the exporters together with those application modules includes
  AGPL-3.0-only code, and that code keeps its own terms.

Each Apache-licensed folder also carries a short `LICENSE.md` that points here.

## Contributions

Contributions are accepted under the licence of the files they change (inbound =
outbound). A change to `src/docket/schema/` is contributed under Apache-2.0; a change to
the kernel is contributed under AGPL-3.0-only. There is no separate contributor licence
agreement. `CONTRIBUTING.md` has the development rules.

## Names and logos are not licensed

The names "Docket" and "OffGrid" and the marks in `ui/src/brand/logo/` identify OffGrid
LLC's software and service. Neither licence grants any right to use them. A fork may say
truthfully that it is based on Docket, but anything it distributes or hosts must carry its
own name and logo.

## Third-party material keeps its own rights

Nothing here relicenses anyone else's work.

- **Documents described in `sources/`.** They are written by other people and
  organisations, are not committed, and each keeps its own rights. `NOTICE.md` records
  those rights item by item.
- **UI fonts.** Each typeface keeps its own licence; see `ui/src/brand/FONTS.md`.
- **Dependencies.** Python and npm packages keep their own licences, as declared in
  `uv.lock`, `ui/package-lock.json` and each package's metadata.

## What the AGPL means if you host a modified copy

You may run, study, change and share Docket. If you change it and let people use your
changed version over a network, for example by hosting it as a service for your
organisation or your customers, you must offer those users the complete source code of
your changed version, under the same licence. Running an unmodified copy, or a modified
copy only you use, carries no such duty. Tools that only talk to Docket through its
record format, exporters or HTTP API are not affected: those interfaces are under
Apache-2.0, and your tool can carry any licence you choose. This summary is a plain
reading, not legal advice; the text in `LICENSE` governs.
