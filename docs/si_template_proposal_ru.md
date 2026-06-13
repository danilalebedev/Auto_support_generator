# Единый DOCX-template для оформления SI

## Цель

Текущие `style_config.yml` и `journal_profile` решают задачу, но для химика это неудобный технический слой. Более практичный интерфейс - один Word-файл `SI_template.docx`, где пользователь видит итоговое оформление и редактирует его как обычный документ.

Предлагаемый подход:

- формат, поля, шрифты, жирность, курсив и интервалы берутся из `SI_template.docx`;
- переменные задаются через `{placeholder}`;
- если placeholder или группа placeholder-ов выделены жирным/курсивом в шаблоне, вставленный текст наследует это оформление;
- квадратные скобки можно использовать как явный маркер форматируемой группы: `[{nmr.1h.label}]` вставляется без скобок, но с оформлением этой группы;
- текущие `style_config.yml` и `journal_profile` остаются временно как backward-compatible режим и позже заменяются готовыми издательскими шаблонами.

## Предлагаемая структура `SI_template.docx`

Удобнее всего сделать в DOCX таблицу из двух колонок:

| Block | Template |
|---|---|
| `compound.title` | `{compound.name} ({compound.number})` |
| `compound.description` | `{compound.preparation}` |
| `nmr.1h` | `[{nmr.1h.label}] ({nmr.1h.conditions}) δ = {nmr.1h.peaks}.` |
| `nmr.13c` | `[{nmr.13c.label}] ({nmr.13c.conditions}) δ = {nmr.13c.peaks}.` |
| `nmr.extra` | `{nmr.extra}` |
| `hrms` | `[{hrms.label}] m/z: {hrms.adduct} calcd for {hrms.formula} {hrms.calculated}. Found {hrms.found}.` |
| `elemental_analysis` | `[{anal.label}] Calcd for {anal.formula}: {anal.calculated}. Found: {anal.found}.` |
| `ir` | `[{ir.label}] ({ir.method}, cm-1): {ir.peaks}.` |
| `appendix.1h.title` | `{compound.name} ({compound.number})` + next line `[{nmr.1h.label}] ({nmr.1h.conditions})` |
| `appendix.13c.title` | `{compound.name} ({compound.number})` + next line `[{nmr.13c.label}] ({nmr.13c.conditions})` |

Причина выбора таблицы: ее легко редактировать в Word, легко парсить программно, и она не требует от пользователя YAML.

## Текущий шаблон оформления

Ниже шаблон, который соответствует текущей логике генератора для описания соединения:

```text
{compound.name} ({compound.number})

{compound.preparation}

[{nmr.1h.label}] ({nmr.1h.conditions}) δ = {nmr.1h.peaks}.

[{nmr.13c.label}] ({nmr.13c.conditions}) δ = {nmr.13c.peaks}.

{nmr.extra}

[{hrms.label}] m/z: {hrms.adduct} calcd for {hrms.formula} {hrms.calculated}. Found {hrms.found}.

[{anal.label}] Calcd for {anal.formula}: {anal.calculated}. Found: {anal.found}.

[{ir.label}] ({ir.method}, cm-1): {ir.peaks}.
```

В Word-шаблоне пользователь должен выделить `[{nmr.1h.label}]`, `[{nmr.13c.label}]`, `[{hrms.label}]`, `[{anal.label}]`, `[{ir.label}]` жирным. При рендере квадратные скобки будут удаляться, а вставленный label останется жирным.

## Шаблон для reagent loadings

Текущий `Compound_characterization template.docx` можно заменить или расширить так:

```text
Alkene {number_Product} was obtained from bromide {number_Reagent_1} ({mg_Reagent_1} mg, {mmol_Reagent_1} mmol), {name_Reagent_2} ({mg_Reagent_2} mg, {mmol_Reagent_2} mmol), K2CO3 ({mg_K2CO3} mg, {mmol_K2CO3} mmol), AcOH ({uL_AcOH} μL, {mmol_AcOH} mmol) and MeCN ({ml_Solvent_MeCN} mL) according to GP2. Yield {mg_yield_Product} mg ({percent_yield_Product}); {color}; mp {mp} °C. Rf = {Rf} ({system_Rf}).
```

Поддерживаемые важные поля:

- `{name_Reagent_1}`, `{name_Reagent_2}`, `{name_Product}` - номенклатурные названия, если ChemDraw смог их сгенерировать;
- `{mg_Reagent_1}`, `{mmol_Reagent_1}`;
- `{mg_Reagent_2}`, `{mmol_Reagent_2}`;
- `{mg_K2CO3}`, `{mmol_K2CO3}`;
- `{uL_AcOH}`, `{mmol_AcOH}`;
- `{ml_Solvent_MeCN}`;
- `{mg_yield_Product}`, `{percent_yield_Product}`;
- `{color}`, `{mp}`, `{Rf}`, `{system_Rf}`.

Если ChemDraw недоступен, `{name_Reagent_2}` должен падать обратно на формулу, а генерация должна выдавать warning, но не останавливаться.

## План внедрения

1. Расширить текущий template renderer: сейчас он вставляет только plain text из `Compound_characterization template.docx`; нужно сохранять run-level форматирование Word.
2. Добавить парсер block-таблицы `SI_template.docx`.
3. Перевести рендер compound description, NMR, HRMS, elemental analysis, IR и spectra appendix на block templates.
4. Оставить `style_config.yml` и `journal_profile` как deprecated fallback.
5. Добавить готовые `SI_template.docx` для default/ACS/RSC/Wiley.
