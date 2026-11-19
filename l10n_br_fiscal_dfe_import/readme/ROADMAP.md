- The key import uses the current company as recipient of the DF-e query.
- The 10 days of the acknowledgement are counted from the emission date kept in
  the DF-e inbox, which is never later than the authorization date.
- Automatic acknowledgement stays the existing company option
  (`auto_manifest_nfe`), off by default.
- Linking with purchases, stock and purchase requests, and the final
  manifestation of the recipient, are left to separate modules.
- Models other than NF-e (CT-e, NFS-e) keep using the previous wizard.
