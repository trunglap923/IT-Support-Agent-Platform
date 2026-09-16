# Demo IT knowledge corpus

This directory contains fictional, self-authored IT guidance for the Acme Demo company.
It contains no real credentials, private URLs, customer data, or copied vendor manuals.

The canonical inventory is `../manifests/documents.json`. Every entry records its access
scope, provenance, license, effective period, and SHA-256 checksum. Run
`make knowledge-validate` after changing any corpus file.

The first snapshot intentionally includes an expired Registry token policy so retrieval
tests can prove that only the current version is served. Questions about printer PINs and
Wi-Fi passwords are intentionally unanswered.
