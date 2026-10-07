# Auto Support Generator beta 1.3

This release packages the current graph-based workflow and all five reproducible examples in one Windows installer.

## Highlights

- Single all-in-one Word input with compound, reaction, scope, SI-template and crystallography-template sections.
- Range-selected methods and reaction schemas for several synthetic series in one input.
- Editable ChemDraw OLE structures and scope/reaction drawings in generated Word files.
- Raw 1H/13C and optional HSQC, HMBC, COSY, NOESY, TOCSY and ROESY processing with saved Mnova artifacts.
- Optional CIF/ORTEP/checkCIF input stored on compound objects and rendered in the X-ray section.
- Journal publication presets with inherited publisher defaults, bundled Word templates and validation metadata.
- Five numbered examples, each with editable inputs and a `Reference_output.docx` generated with Show scope enabled.
- Installer payload validation, SHA-256 checksum and clean-install support without Git or Python.

## Installation

Download `installer/AutoSupportGeneratorSetup.exe` together with its `.sha256` file, verify the checksum if desired, and run it on Windows. Microsoft Word, ChemDraw and MestReNova are licensed external applications and must be installed separately.

This is a research beta. Review generated Supporting Information and journal-specific requirements before submission.
