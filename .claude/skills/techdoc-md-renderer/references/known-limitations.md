# Known Limitations

- Legacy renderer remains the default path.
- PDF V2 output is backend-dependent and may fall back to review or
  non-conformant fidelity.
- DOCX formal document output remains profile-gated.
- Full advanced pagination, widow/orphan control, footnotes, and perfect table
  splitting are not implemented in V2.
- Raw HTML in DOCX/PDF is preserved or diagnosed as fallback, not faithfully
  rendered.
- Plugin interfaces are minimal and explicit; there is no auto-discovery yet.
- Profile extensions support YAML deep merge, not arbitrary code.
- Legacy preflight/postflight/polisher remain compatibility and safety tools.
