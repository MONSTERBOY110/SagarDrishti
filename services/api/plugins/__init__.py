"""Drop-in plugin directory for the F6 extension points.

This is a *directory*, not really a package: app/plugins.py loads each .py file
here BY PATH (as `sagardrishti_plugin_<stem>`), so a new plugin is a file
copied in with no edit to this file, no install step and no restart beyond
POST /plugins/reload. The __init__.py exists only so the directory is
explicitly ours rather than incidental.

Rules, in full, with the reasoning in docs/PLUGINS.md:

  * A file must expose `def register(registry): ...` and call
    registry.register_derived_product / registry.register_source_reader inside
    it. Nothing is picked up by naming convention.
  * A leading underscore in the filename disables the file. That is how a
    plugin is switched off on stage without deleting anyone's work.
  * No network client, ever. tests/test_plugins.py statically scans this
    directory for one, because a plugin is the obvious place for a forgotten
    HTTP import to hide, and the demo runs air-gapped.
  * Missing data stays missing. A derived product returns NaN over land and
    wherever its answer does not exist; app/plugins.py refuses a result that
    invents a value there (rule C5).
"""
