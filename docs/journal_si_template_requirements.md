# Требования издательств к Supporting Information для органической химии

Дата обзора: 26 июля 2026.

Важно: у издательств есть общие правила, но финальные требования часто задаются конкретным журналом. Поэтому для программы лучше делать не один "стиль ACS/Wiley", а систему профилей: `publisher.base` + `journal.override` + ручные настройки пользователя.

## Краткий вывод

Для типового synthetic/supporting information почти все крупные журналы сходятся в одном ядре:

- Для новых соединений нужны `1H NMR` и `13C NMR` данные, обычно плюс копии спектров в SI.
- Для подтверждения молекулярной формулы нужен `HRMS` или elemental analysis; иногда X-ray допускается как замена именно для формулы, но не для чистоты.
- HRMS не считается доказательством чистоты. Чистоту доказывают NMR, elemental analysis, HPLC/GC/qNMR или другой количественный метод.
- В NMR должны быть указаны solvent, frequency, standard/reference, chemical shifts, multiplicity, integration for 1H, J values where applicable.
- Для изображений NMR журналы требуют читаемые подписи, пики, интегралы, достаточный signal-to-noise, полный диапазон ppm и inset/zoom для сложных участков.
- Для ChemDraw/структур требования различаются сильнее: ACS формулирует на уровне "drawing program such as ChemDraw", Nature/Communications Chemistry просит Nature Research style guide и ChemDraw template, Wiley-chemistry journals часто просят Wiley/Angewandte style/template или исходные CDX/рисунки.

## Источники

Primary sources used:

- ACS JOC Author Guidelines: https://researcher-resources.acs.org/publish/author_guidelines?coden=joceah
- ACS Research Data Guidelines: https://researcher-resources.acs.org/publish/data_guidelines
- ACS NMR Guidelines PDF: https://pubsapp.acs.org/paragonplus/submission/acs_nmr_guidelines.pdf
- RSC Experimental reporting: https://www.rsc.org/publishing/publish-with-us/publish-a-journal-article/experimental-reporting
- Wiley/Chemistry Europe Notice to Authors example: https://chemistry-europe.onlinelibrary.wiley.com/hub/journal/15213765/notice-to-authors
- Wiley Online Library author-guideline PDF example: https://onlinelibrary.wiley.com/pb-assets/assets/15214184/ArchPharm-Author-Guidelines-February-2024-1708440550533.pdf
- Elsevier Tetrahedron Guide for Authors: https://www.sciencedirect.com/journal/tetrahedron/publish/guide-for-authors
- MDPI Molecules Instructions for Authors: https://www.mdpi.com/journal/molecules/instructions
- Nature chemical characterization guidelines PDF: https://www.nature.com/documents/nature_chemical_characterization_guidelines.pdf
- Communications Chemistry submission guidelines: https://www.nature.com/commschem/submit/submission-guidelines
- Springer Nature Chemical Papers submission guidelines: https://link.springer.com/journal/11696/submission-guidelines
- Beilstein Journal of Organic Chemistry instructions: https://www.beilstein-journals.org/bjoc/authorInstructions

## Матрица требований

| Издатель/журнал | Supporting Information | NMR-требования | HRMS / elemental analysis | Чистота | ChemDraw / графика | Что автоматизировать |
|---|---|---|---|---|---|---|
| ACS / JOC, Organic Letters-like baseline | SI отдельным файлом; данные могут быть в Experimental или SI, если полные и точные. Для новых соединений копии `1H` и `13C` спектров обязательны. | Список `1H` и `13C` резонансов для каждого нового соединения; обычно full range `10-0 ppm` для `1H`, `200-0 ppm` для `13C`; `1H` shifts до 0.01 ppm, `13C` до 0.1 ppm; solvent/frequency обязательны; 2D assignments только если выполнены 2D methods. ACS NMR PDF дает минимум окна: `-1..9 ppm` для `1H`, `-10..180 ppm` для `13C`; JOC purity section требует обычно `0..10` и `0..200`. | Для новых соединений: `1H + 13C + HRMS или EA`. Для EA CHN found должен быть within `0.4%` от calculated. Для HRMS JOC указывает, что `0.003 m/z` для ion below 1000 amu обычно достаточно. | Для bioassay/physical measurements минимум 95% purity documented. HRMS не доказывает чистоту. | Структуры через ChemDraw/drawing program; ACS graphics minimum: line art 1200 dpi, grayscale 600 dpi, color 300 dpi. | Профили `acs.base`, `acs.joc`, `acs.orglett`: ppm ranges, NMR precision, required spectra, EA tolerance 0.4%, HRMS delta `0.003 Da` or ppm equivalent, purity evidence rules. |
| Wiley / Chemistry Europe / Angewandte-like | Для Chemistry Europe Notice: копии `1H` и `13C` NMR spectra all key intermediates/final products in SI; spectra must correspond to reactions in manuscript, not reused from previous syntheses. | Wiley-chemistry style commonly asks standard NMR listings and legible spectra in SI. For Angewandte/Chemistry Europe profiles, support both normal organic windows and journal-specific ChemDraw/Wiley drawing styles. | Common requirement: HRMS or elemental analysis for new compounds; some Wiley medicinal/chemistry journals add stricter proof of purity and may ask HPLC. | For medicinal chemistry and bioactivity contexts, include HPLC/UPLC purity traces and purity percentage. | Wiley author-guideline examples explicitly mention Wiley journal style in ChemDraw/BioviaDraw, often referring to Angewandte-style templates. | Профили `wiley.chemistry_europe`, `wiley.angew`, `wiley.arch_pharm`: ChemDraw style selector, SI spectrum list, optional HPLC purity package. |
| RSC | Experimental reporting guidance; relevant spectra may be tabulated or reproduced in SI or repository. | Use delta values; specify nucleus, J units in Hz, instrument frequency, solvent and standard. Mutually coupled protons should have matching J values; 13C assignment only when justified. | Exact masses for identification should be within `5 ppm` for EI/CI or `10 ppm` for FAB/LSIMS. RSC emphasizes elemental analytical data for purity; accurate mass alone is not purity evidence. | Evidence for homogeneity and identity required. If EA cannot be obtained, use appropriate spectroscopic evidence. | RSC is less prescriptive for ChemDraw in the generic experimental reporting page; use RSC journal templates/styles where available. | Профиль `rsc.base`: HRMS tolerance by ionization method, NMR reporting formatter, warning if HRMS is used as purity proof. |
| Elsevier / Tetrahedron | Guide says SI experimental details and spectra are in same order as manuscript; high-resolution copies of spectra required in ESI for new compounds. | New compounds normally include `1H` and `13C` NMR peak lists; high-resolution copies of spectra in ESI; spectra labeled with structure and compound number. | New compounds normally include HRMS or elemental analysis, plus indicative IR and melting point where appropriate. | Known compounds by new procedures should include `1H NMR` evidence of purity. | Less centralized ChemDraw styling; use journal template and ordinary chemical drawing consistency. | Профиль `elsevier.tetrahedron`: compound order mirrors manuscript, labels on every spectrum, new vs known-by-new-method validation. |
| MDPI / Molecules | Instructions require enough experimental detail for reproducibility; supplementary materials are accepted. In published Molecules practice, SI commonly contains characterization data and `1H/13C NMR + HRMS` spectra for all new compounds. | No single strict publisher-wide ppm window found in instructions; use organic baseline `1H 0..10`, `13C 0..200/220` unless journal/editor asks otherwise. | For synthetic papers, enforce common full characterization: HRMS and/or EA; examples often provide HRMS for all new compounds. | For bioactive compounds, add HPLC/purity evidence proactively. | MDPI uses general manuscript/figure guidance; no strict ChemDraw profile found for Molecules. | Профиль `mdpi.molecules`: pragmatic validation profile, less strict on drawing style, strong SI completeness warnings. |
| Nature Portfolio / Nature Chemistry-like | Nature chemical characterization guidelines allow methods/data as SI; figures with spectra generally go to SI unless central. | Standard peak listings for `1H` and proton-decoupled `13C` for all new compounds; other nuclides when appropriate; high-quality spectral images encouraged. | HRMS required to support molecular weight identity for new materials; elemental analysis `+-0.4%` encouraged for small molecules. | Evidence of purity requested for each new compound; high-field `1H/13C NMR`, EA, GC/HPLC/electrophoretic methods accepted. | Nature asks to use Nature Research Chemical Structures Guide and ChemDraw template. | Профиль `nature.base`: identity+purity checklist, ChemDraw template field, high-quality spectrum image flag. |
| Communications Chemistry | Detailed, current, highly actionable NMR section. Spectra should be in separate Supplementary Data file, not just main SI PDF. | `1H` and `13C{1H}` essential; `19F/31P` essential when molecule contains F/P; one spectrum per A4 landscape page; no editing; labels include compound/structure, nuclide, solvent, field strength; all peaks picked and labelled; all `1H` peaks integrated; `1H` range `10..-1 ppm`, `13C{1H}` `200..-10 ppm`; 19F/31P window no smaller than 200 ppm. | HRMS preferred; if `m/z < 1000`, calculated/found within `0.003`; if `m/z > 1000`, within `1 ppm`. | Yield and purity evidence required for every isolated compound; EA `+-0.4%` encouraged; chromatography/electrophoresis accepted. | Accepts ChemDraw `.cdx` for chemical structures; asks Nature Research style guide; figures RGB 300 dpi+, Arial/Helvetica, vector preferred. | Профиль `nature.commschem`: strict NMR render profile, separate Supplementary Data export, F/P nuclide validator, HRMS tolerance switch by mass. |
| Springer Nature / Chemical Papers | Manuscript in journal template; checklist for compound characterization required. | Novel compounds: `1H` and `13C NMR` obligatory. | Novel compounds: elemental analysis or HRMS obligatory; melting point and Rf where appropriate. EA submitted separately. | Checklist plus physical data for known compounds where missing in literature. | Chemical drawing template/configuration supplied by journal; instructions say do not change settings. | Профиль `springer.chemical_papers`: mandatory checklist export, chemical drawing template path, EA separate-sheet option. |
| Beilstein Journal of Organic Chemistry | New compounds should be fully characterized; spectra may be reproduced as figures in SI. | No strict ppm window found in core instructions; use standard organic NMR baseline and let journal override later. | EA whenever possible; sufficient evidence for identity and purity. | Identity and degree of purity must be established. | General style guide; less prescriptive than Nature/ACS. | Профиль `beilstein.bjoc`: full characterization completeness, optional spectra-in-SI, EA recommendation. |

## Реализованная модель профиля журнала

Профили реализованы в `src/si_generator/templates/journals/profiles.json`; загрузчик находится в `src/si_generator/journal_profiles.py`. JSON выбран как встроенный проверяемый формат, не требующий дополнительной YAML-зависимости в установленном приложении. Профили поддерживают наследование `publisher.base -> journal.override`.

Встроено 18 пользовательских профилей: General Organic SI; ACS JOC, Organic Letters, Journal of Medicinal Chemistry и JACS; RSC Organic Chemistry; Wiley Angewandte, Chemistry Europe/EurJOC и Archiv der Pharmazie; Elsevier Tetrahedron, Tetrahedron Letters, European Journal of Medicinal Chemistry и Bioorganic & Medicinal Chemistry; Nature Chemistry и Communications Chemistry; Molecules; BJOC; Chemical Papers.

Профиль применяется в трех сценариях:

- `Generate`: задает DOCX-шаблон, MNGP, ppm-окна, appendix layout и профильные проверки; ручные изменения записываются как overrides.
- `Add`: Same Series наследует старый профиль, New Method принимает новый.
- `Patch -> Reformat`: пересобирает существующий SI под другой профиль из manifest и готовых артефактов, не запуская Mnova повторно.

Выбранный ID, версия, дата проверки и официальные URL сохраняются в manifest. DOCX-файлы в каталоге профилей имеют статус `house_default`: это шаблоны программы по опубликованным требованиям, а не официальные publisher templates.

### Исходный проектный эскиз

Ниже сохранен ранний пример схемы как справочный материал. Он не является фактическим файловым API текущей версии.

Предлагаем добавить ресурсы:

```text
src/si_generator/resources/journal_profiles/
  acs.base.yml
  acs.joc.yml
  acs.orglett.yml
  wiley.chemistry_europe.yml
  wiley.angew.yml
  rsc.base.yml
  elsevier.tetrahedron.yml
  mdpi.molecules.yml
  nature.base.yml
  nature.commschem.yml
  springer.chemical_papers.yml
  beilstein.bjoc.yml
```

Пример YAML:

```yaml
id: nature.commschem
label: "Nature / Communications Chemistry"
publisher: "Springer Nature"
source_urls:
  - "https://www.nature.com/commschem/submit/submission-guidelines"
inherits: nature.base

document:
  template_docx: "templates/SI_template_nature_commschem.docx"
  spectra_output_mode: "supplementary_data_separate"
  spectrum_page:
    size: "A4"
    orientation: "landscape"

nmr:
  required_nuclei:
    default: ["1H", "13C{1H}"]
    if_contains:
      F: ["19F", "19F{1H}"]
      P: ["31P", "31P{1H}"]
  ppm_ranges:
    "1H": [10.0, -1.0]
    "13C{1H}": [200.0, -10.0]
    "19F": { min_width_ppm: 200 }
    "31P": { min_width_ppm: 200 }
  precision:
    "1H_shift_decimals": 2
    "13C_shift_decimals": 1
  presentation:
    require_peak_labels: true
    require_1h_integrals: true
    require_compound_label: true
    require_solvent_frequency_label: true
    forbid_manual_spectrum_editing: true

mass_spec:
  preferred: "HRMS"
  tolerances:
    - condition: "mz < 1000"
      absolute_da: 0.003
    - condition: "mz >= 1000"
      ppm: 1

purity:
  required_for: "every_isolated_compound"
  acceptable_evidence: ["1H_NMR", "13C_NMR", "elemental_analysis", "GC", "HPLC", "qNMR", "electrophoresis"]
  elemental_analysis_tolerance_percent: 0.4
  hrms_counts_as_purity: false

graphics:
  chemical_structure_style: "nature_research"
  accepted_structure_files: [".cdx"]
  figure_font: ["Arial", "Helvetica"]
  color_mode: "RGB"
  min_bitmap_dpi: 300
```

## Исходный чек-лист реализации

### 1. Loader профилей

Реализованный модуль `journal_profiles.py`:

- читает встроенный JSON-каталог из `templates/journals`;
- поддерживает `inherits`;
- валидирует схему профиля;
- возвращает resolved settings для генератора, GUI и check_support.

### 2. GUI

В GUI добавлено поле `Publication preset`:

- dropdown с журналами;
- кнопка `Apply`;
- ручные overrides через существующие поля template/MNGP/Processing.

При применении профиль заполняет:

- `template_docx`;
- `mnova_graphics_profile_1h` и `mnova_graphics_profile_13c`;
- `x_range_ppm_1h`, `x_range_ppm_13c`;
- требования по HRMS/EA и доступные правила дополнительных ядер;
- ориентацию страниц appendix.

Официальные URL и дата проверки доступны в сгенерированном manifest. Отдельный экспорт Supplementary Data остается последующим расширением для журналов, которые требуют отдельный файл со спектрами.

### 3. Генератор и manifest

В `GenerateSIRequest` добавлено:

```python
journal_profile_id: str = "organic.default"
```

В manifest сохранять:

```yaml
journal_profile:
  id: nature.commschem
  label: Nature / Communications Chemistry
  source_urls: [...]
  profile_version: 2026-07-26
  applied_overrides:
    x_range_ppm_1h: [10, -1]
    x_range_ppm_13c: [200, -10]
```

### 4. Валидация support/check_support

Сделать валидатор профиль-зависимым:

- missing `1H` spectrum;
- missing `13C` spectrum;
- missing `19F/31P` when formula contains F/P;
- HRMS delta above profile tolerance;
- EA difference above `0.4%`;
- HRMS used as purity proof;
- spectrum range narrower than profile requires;
- missing compound number/structure label on spectra;
- spectra not in same order as compounds/manuscript for Tetrahedron-like profile;
- missing HPLC/purity for bioactive compounds;
- missing reason when required characterization cannot be obtained.

### 5. MNova / спектры

Сейчас в программе уже есть поля `mnova_graphics_profile_1h`, `mnova_graphics_profile_13c`, `x_range_ppm_1h`, `x_range_ppm_13c`. Это хороший фундамент. Нужно расширить:

- профильные `.mngp` для `acs`, `nature`, `rsc`, `wiley`;
- windows по ядрам, не только `1H/13C`;
- автоматический inset/expanded-region suggestions;
- landscape A4 page mode for strict profiles;
- label template: compound number, nuclide, solvent, frequency.

### 6. ChemDraw / структуры

Полностью автоматически менять стиль ChemDraw надежно можно только если есть исходный `.cdx/.cdxml` и понятный pipeline. Поэтому MVP:

- хранить `chemical_structure_style` и ссылку на template/config;
- проверять, что в support есть структура/compound number;
- экспортировать предупреждение: "Apply ACS 1996/Wiley/Nature ChemDraw template before final submission";
- позже добавить `cdxml` normalizer для bond length/font/line width, если структура приходит в CDXML.

## Статус первой волны

1. Реализованы каталог, наследование и dropdown в GUI.
2. Профиль применяется к NMR windows, `template_docx`, `.mngp` и appendix layout.
3. Manifest хранит выбранный профиль, источники, версию и overrides.
4. `check_support` выполняет доступные profile-aware проверки NMR, HRMS и EA.
5. Все журналы из первой и второй запланированных волн включены сразу.
6. Добавлены тесты loader, ресурсов, request mapping, validation и Patch Reformat.

## Практический дефолт, если журнал не выбран

Для безопасного default-профиля:

```yaml
id: organic.default
nmr:
  ppm_ranges:
    "1H": [10.0, -1.0]
    "13C": [200.0, -10.0]
  precision:
    "1H_shift_decimals": 2
    "13C_shift_decimals": 1
mass_spec:
  hrms_tolerance:
    absolute_da_if_mz_lt_1000: 0.003
    fallback_ppm: 5
purity:
  elemental_analysis_tolerance_percent: 0.4
  hrms_counts_as_purity: false
required_for_new_compounds:
  - "1H NMR data"
  - "13C NMR data"
  - "1H spectrum image"
  - "13C spectrum image"
  - "HRMS or elemental analysis"
```

Это чуть строже текущего дефолта программы (`1H -1..12`, `13C -10..210`) и ближе к требованиям ACS/Nature/Communications Chemistry. Для журналов, где нужны более широкие окна, профиль сможет расширить диапазон.
