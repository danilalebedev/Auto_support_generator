# Единый DOCX-template для оформления SI

Оформление SI задается одним Word-файлом `SI_template.docx`.
Пользователь редактирует его как обычный будущий support: меняет шрифт,
жирность, курсив, интервалы, поля, нижние и верхние индексы прямо в Word.
Программа копирует это оформление и заменяет placeholder-ы на данные соединений.

## Правила placeholder-ов

Публичный формат единый: в placeholder-ах используются точки.

```text
{compound.name} ({compound.number})

{compound.preparation}

{reaction.loadings}

[{nmr.1h.label}] ({nmr.1h.conditions}) δ = {nmr.1h.peaks}.

[{nmr.13c.label}] ({nmr.13c.conditions}) δ = {nmr.13c.peaks}.

[{hrms.label}]: {hrms.adduct} calcd for {hrms.formula} {hrms.calculated}. Found {hrms.found}.

[{anal.label}] Calcd for {anal.formula}: {anal.calculated}. Found: {anal.found}.

[{ir.label}] ({ir.method}, cm-1): {ir.peaks}.
```

Если placeholder или группа placeholder-ов выделены жирным или курсивом, вставленный
текст наследует это форматирование. Квадратные скобки в `[{hrms.label}]` служат
только маркером форматируемой группы: в итоговом SI они удаляются.

## Reagent loadings

Отдельный `Compound_characterization` template больше не нужен. Текст загрузок
берется из того же `SI_template.docx`, из параграфа с loadings-placeholder-ами.

Пример:

```text
Alkene {Product.precursor_number} was obtained from bromide {Reagent_1.name} ({Reagent_1.mass.mg} mg, {Reagent_1.mmol} mmol), {Reagent_2.name} ({Reagent_2.mass.mg} mg, {Reagent_2.mmol} mmol), K2CO3 ({K2CO3.mass.mg} mg, {K2CO3.mmol} mmol), AcOH ({AcOH.uL} µL, {AcOH.mmol} mmol) and MeCN ({Solvent_MeCN.mL} mL) according to GP2. Yield {Product.yield.mg} mg ({Product.yield.percent}); {Product.appearance}; mp {Product.mp} °C. Rf = {Product.rf.value} ({Product.rf.system}).
```

В самом Word-шаблоне формулы можно форматировать нормально: например, в `K2CO3`
цифры `2` и `3` должны быть нижними индексами.

## Важные placeholder-ы

- `{compound.name}`, `{compound.number}`, `{compound.number.structure}`, `{compound.preparation}`;
- `{reaction.loadings}`;
- `{Product.number}`, `{Product.precursor_number}`;
- `{Reagent_1.name}`, `{Reagent_1.mass.mg}`, `{Reagent_1.mmol}`;
- `{Reagent_2.name}`, `{Reagent_2.mass.mg}`, `{Reagent_2.mmol}`;
- `{K2CO3.mass.mg}`, `{K2CO3.mmol}`;
- `{AcOH.uL}`, `{AcOH.mmol}`;
- `{Solvent_MeCN.mL}`;
- `{Product.yield.mg}`, `{Product.yield.percent}`;
- `{Product.appearance}`, `{Product.mp}`, `{Product.rf.value}`, `{Product.rf.system}`;
- `{nmr.1h.label}`, `{nmr.1h.conditions}`, `{nmr.1h.peaks}`;
- `{nmr.13c.label}`, `{nmr.13c.conditions}`, `{nmr.13c.peaks}`;
- `{compound.number.nmr.1h.picture}`, `{compound.number.nmr.13c.picture}`;
- `{hrms.label}`, `{hrms.adduct}`, `{hrms.formula}`, `{hrms.calculated}`, `{hrms.found}`;
- `{anal.label}`, `{anal.formula}`, `{anal.calculated}`, `{anal.found}`;
- `{ir.label}`, `{ir.method}`, `{ir.peaks}`.

Если ChemDraw недоступен для генерации `{name.Reagent.2}`, программа использует
fallback по формуле и пишет warning, но генерацию SI не останавливает.
